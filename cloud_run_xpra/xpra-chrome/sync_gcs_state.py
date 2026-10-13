#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Manages persistent user & browser state on a Cloud Run GCS Fuse volume mount.
#
# Architecture:
# 1. User data folders (~/Downloads, ~/Documents, ~/Desktop, ~/Workspace) are
#    symlinked directly to the GCS Fuse mount (/mnt/state/...) so user files and
#    downloads persist immediately without consuming container memory.
# 2. Latency- and lock-sensitive application configs (~/.config/google-chrome,
#    ~/.config/gcloud, ~/.config/xfce4, ~/.ssh, ~/.bash_history) run in fast
#    local container memory and are restored on startup + incrementally synced
#    to GCS Fuse (using in-memory SHA-256 deduplication so unchanged files never
#    trigger GCS writes, and skipping ephemeral browser caches/sockets/locks).

import hashlib
import json
import os
import shutil
import signal
import stat
import sys
import tempfile
import time

MOUNT_PATH = os.environ.get("GCS_STATE_MOUNT_PATH", "/mnt/state")
HOME_DIR = os.environ.get("HOME", "/home/user")
RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR", "/tmp/runtime-user")
PROFILE_KEY = os.environ.get("GCS_STATE_PROFILE") or os.environ.get("K_SERVICE") or "default"
SYNC_INTERVAL = int(os.environ.get("GCS_STATE_SYNC_INTERVAL", "15"))
INDEX_PATH = os.path.join(RUNTIME_DIR, "gcs_state_index.json")

# Maximum size of an individual config/profile file to sync (32 MiB)
MAX_SYNC_FILE_BYTES = 32 * 1024 * 1024

# Direct GCS Fuse symlinked directories inside $HOME
DIRECT_SYMLINK_DIRS = [
    "Downloads",
    "Documents",
    "Desktop",
    "Workspace",
]

# Ephemeral cache/lock directories to exclude from config sync
EXCLUDED_DIR_NAMES = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "GrShaderCache",
    "ShaderCache",
    "DawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "GraphiteDawnCache",
    "Crashpad",
    "BrowserMetrics",
    "Safe Browsing",
    "Safe Browsing Network",
    "Service Worker",
    "CacheStorage",
    "ScriptCache",
    "blob_storage",
    "component_crx_cache",
    "optimization_guide_model_store",
    "Subresource Filter",
    "GCM Store",
    "Sessions",  # Chrome binary SNSS tab/window state (optional, keep Preferences/Bookmarks/Cookies)
    "logs",
    "__pycache__",
}

# Ephemeral lock/journal files to exclude from config sync
EXCLUDED_FILE_NAMES = {
    "SingletonLock",
    "SingletonSocket",
    "SingletonCookie",
    "lockfile",
    "BrowserMetrics-spare.pma",
}

EXCLUDED_SUFFIXES = (
    ".lock",
    ".tmp",
    "-journal",
    "-wal",
    "-shm",
    ".pma",
)

# Restrict ~/.config/google-chrome sync to user profile state (skipping ~450 Chrome Component Updater files)
CHROME_ALLOWED_TOP_DIRS = {"Default"}
CHROME_ALLOWED_TOP_FILES = {"Local State", "First Run"}
CHROME_ALLOWED_DEFAULT_DIRS = {
    "Network",
    "Local Storage",
    "Session Storage",
    "Extensions",
    "Local Extension Settings",
    "Sync Extension Settings",
    "Managed Extension Settings",
    "IndexedDB",
}


def filter_walk_entries(target_name: str, rel_dir: str, dirs: list, files: list, root: str) -> tuple[list, list]:
    dirs = [d for d in dirs if d not in EXCLUDED_DIR_NAMES and not os.path.islink(os.path.join(root, d))]
    files = [f for f in files if not should_exclude_file(f)]
    if target_name == "chrome":
        if rel_dir == ".":
            dirs = [d for d in dirs if d in CHROME_ALLOWED_TOP_DIRS]
            files = [f for f in files if f in CHROME_ALLOWED_TOP_FILES]
        elif rel_dir == "Default":
            dirs = [d for d in dirs if d in CHROME_ALLOWED_DEFAULT_DIRS]
    return dirs, files


def log(msg: str) -> None:
    print(f"[gcs-state] {msg}", flush=True)


def is_state_mount_ready(mount_path: str = MOUNT_PATH) -> bool:
    return os.path.isdir(mount_path) and os.access(mount_path, os.W_OK)


def get_sync_targets(home_dir: str = HOME_DIR, mount_path: str = MOUNT_PATH, profile_key: str = PROFILE_KEY):
    return [
        (
            "chrome",
            "dir",
            os.path.join(home_dir, ".config", "google-chrome"),
            os.path.join(mount_path, "profiles", profile_key, "google-chrome"),
        ),
        (
            "gcloud",
            "dir",
            os.path.join(home_dir, ".config", "gcloud"),
            os.path.join(mount_path, "shared", "gcloud"),
        ),
        (
            "ssh",
            "dir",
            os.path.join(home_dir, ".ssh"),
            os.path.join(mount_path, "shared", "ssh"),
        ),
        (
            "xfce4",
            "dir",
            os.path.join(home_dir, ".config", "xfce4"),
            os.path.join(mount_path, "shared", "xfce4"),
        ),
        (
            "bash_history",
            "file",
            os.path.join(home_dir, ".bash_history"),
            os.path.join(mount_path, "shared", "bash_history"),
        ),
    ]


def should_exclude_file(filename: str) -> bool:
    if filename in EXCLUDED_FILE_NAMES:
        return True
    if filename.startswith(".org.chromium.") or filename.startswith("Singleton"):
        return True
    if filename.endswith(EXCLUDED_SUFFIXES):
        return True
    return False


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_index(index_path: str = INDEX_PATH) -> dict:
    try:
        if os.path.isfile(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_index(index: dict, index_path: str = INDEX_PATH) -> None:
    try:
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f)
    except Exception as e:
        log(f"Warning: failed to write state index: {e}")


def setup_direct_symlinks(home_dir: str = HOME_DIR, mount_path: str = MOUNT_PATH) -> None:
    for folder in DIRECT_SYMLINK_DIRS:
        gcs_folder = os.path.join(mount_path, folder)
        local_folder = os.path.join(home_dir, folder)
        try:
            os.makedirs(gcs_folder, exist_ok=True)
            if os.path.islink(local_folder):
                if os.readlink(local_folder) == gcs_folder:
                    continue
                os.unlink(local_folder)
            elif os.path.isdir(local_folder):
                # Migrate any pre-existing files into the GCS folder before replacing with a symlink
                for entry in os.listdir(local_folder):
                    src_entry = os.path.join(local_folder, entry)
                    dst_entry = os.path.join(gcs_folder, entry)
                    if not os.path.exists(dst_entry):
                        shutil.move(src_entry, dst_entry)
                shutil.rmtree(local_folder, ignore_errors=True)
            elif os.path.exists(local_folder):
                os.unlink(local_folder)
            os.symlink(gcs_folder, local_folder)
        except Exception as e:
            log(f"Warning: could not symlink {local_folder} -> {gcs_folder}: {e}")


def sanitize_chrome_profile(chrome_dir: str) -> None:
    if not os.path.isdir(chrome_dir):
        return
    # Remove any stale Singleton locks
    for entry in os.listdir(chrome_dir):
        if entry.startswith("Singleton") or entry == "lockfile":
            try:
                os.unlink(os.path.join(chrome_dir, entry))
            except OSError:
                pass

    # Mark Chrome exit_type as Normal in Default/Preferences so the crash bubble is suppressed
    prefs_path = os.path.join(chrome_dir, "Default", "Preferences")
    if os.path.isfile(prefs_path):
        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
            profile = prefs.get("profile")
            if isinstance(profile, dict):
                profile["exit_type"] = "Normal"
                profile["exited_cleanly"] = True
                with open(prefs_path, "w", encoding="utf-8") as f:
                    json.dump(prefs, f)
        except Exception:
            pass


def fix_ssh_permissions(ssh_dir: str) -> None:
    if not os.path.isdir(ssh_dir):
        return
    try:
        os.chmod(ssh_dir, 0o700)
        for root, dirs, files in os.walk(ssh_dir):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o700)
            for fname in files:
                fpath = os.path.join(root, fname)
                if fname.endswith(".pub") or fname in ("known_hosts", "authorized_keys"):
                    os.chmod(fpath, 0o644)
                else:
                    os.chmod(fpath, 0o600)
    except Exception as e:
        log(f"Warning: failed to set SSH permissions: {e}")


def init_state(home_dir: str = HOME_DIR, mount_path: str = MOUNT_PATH, profile_key: str = PROFILE_KEY, index_path: str = INDEX_PATH) -> None:
    if not is_state_mount_ready(mount_path):
        log(f"No writable volume mounted at {mount_path}; using ephemeral container storage.")
        return

    log(f"Initializing persistent state from {mount_path} (profile={profile_key})...")
    setup_direct_symlinks(home_dir, mount_path)

    index = {}
    restored_files = 0
    for name, kind, local_path, gcs_path in get_sync_targets(home_dir, mount_path, profile_key):
        if kind == "file":
            if os.path.isfile(gcs_path):
                try:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    shutil.copyfile(gcs_path, local_path)
                    st = os.stat(local_path)
                    index[f"{name}:."] = {
                        "mtime_ns": st.st_mtime_ns,
                        "size": st.st_size,
                        "sha256": compute_sha256(local_path),
                    }
                    restored_files += 1
                except Exception as e:
                    log(f"Warning: failed restoring file {gcs_path}: {e}")
            continue

        if not os.path.isdir(gcs_path):
            continue

        for root, dirs, files in os.walk(gcs_path):
            rel_dir = os.path.relpath(root, gcs_path)
            dirs[:], files = filter_walk_entries(name, rel_dir, dirs, files, root)
            target_dir = local_path if rel_dir == "." else os.path.join(local_path, rel_dir)
            os.makedirs(target_dir, exist_ok=True)

            for fname in files:
                src_file = os.path.join(root, fname)
                dst_file = os.path.join(target_dir, fname)
                rel_file = fname if rel_dir == "." else os.path.join(rel_dir, fname)
                try:
                    shutil.copyfile(src_file, dst_file)
                    st = os.stat(dst_file)
                    index[f"{name}:{rel_file}"] = {
                        "mtime_ns": st.st_mtime_ns,
                        "size": st.st_size,
                        "sha256": compute_sha256(dst_file),
                    }
                    restored_files += 1
                except Exception as e:
                    log(f"Warning: failed restoring {src_file}: {e}")

    sanitize_chrome_profile(os.path.join(home_dir, ".config", "google-chrome"))
    prefs_local = os.path.join(home_dir, ".config", "google-chrome", "Default", "Preferences")
    if os.path.isfile(prefs_local):
        st = os.stat(prefs_local)
        index[f"chrome:{os.path.join('Default', 'Preferences')}"] = {
            "mtime_ns": st.st_mtime_ns,
            "size": st.st_size,
            "sha256": compute_sha256(prefs_local),
        }
    fix_ssh_permissions(os.path.join(home_dir, ".ssh"))
    save_index(index, index_path)
    log(f"Restored {restored_files} state file(s) and linked {len(DIRECT_SYMLINK_DIRS)} user folders to {mount_path}.")


def sync_state(home_dir: str = HOME_DIR, mount_path: str = MOUNT_PATH, profile_key: str = PROFILE_KEY, index_path: str = INDEX_PATH) -> int:
    if not is_state_mount_ready(mount_path):
        return 0

    index = load_index(index_path)
    seen_keys = set()
    updated_count = 0

    for name, kind, local_path, gcs_path in get_sync_targets(home_dir, mount_path, profile_key):
        if kind == "file":
            key = f"{name}:."
            if os.path.isfile(local_path) and not os.path.islink(local_path):
                seen_keys.add(key)
                try:
                    st = os.stat(local_path)
                    if st.st_size <= MAX_SYNC_FILE_BYTES:
                        prev = index.get(key)
                        if not prev or prev.get("mtime_ns") != st.st_mtime_ns or prev.get("size") != st.st_size:
                            digest = compute_sha256(local_path)
                            if not prev or prev.get("sha256") != digest:
                                os.makedirs(os.path.dirname(gcs_path), exist_ok=True)
                                shutil.copyfile(local_path, gcs_path)
                                updated_count += 1
                            index[key] = {
                                "mtime_ns": st.st_mtime_ns,
                                "size": st.st_size,
                                "sha256": digest,
                            }
                except Exception as e:
                    log(f"Warning: failed syncing {local_path}: {e}")
            continue

        if not os.path.isdir(local_path):
            continue

        for root, dirs, files in os.walk(local_path):
            rel_dir = os.path.relpath(root, local_path)
            dirs[:], files = filter_walk_entries(name, rel_dir, dirs, files, root)

            for fname in files:
                src_file = os.path.join(root, fname)
                try:
                    st = os.lstat(src_file)
                except OSError:
                    continue
                # Skip symlinks, sockets, FIFOs, and oversized files
                if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_SYNC_FILE_BYTES:
                    continue

                rel_file = fname if rel_dir == "." else os.path.join(rel_dir, fname)
                key = f"{name}:{rel_file}"
                seen_keys.add(key)

                prev = index.get(key)
                if prev and prev.get("mtime_ns") == st.st_mtime_ns and prev.get("size") == st.st_size:
                    continue

                try:
                    digest = compute_sha256(src_file)
                    if not prev or prev.get("sha256") != digest:
                        dst_file = os.path.join(gcs_path, rel_file)
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copyfile(src_file, dst_file)
                        updated_count += 1
                    index[key] = {
                        "mtime_ns": st.st_mtime_ns,
                        "size": st.st_size,
                        "sha256": digest,
                    }
                except Exception as e:
                    log(f"Warning: failed syncing {src_file}: {e}")

    # Remove files deleted locally from GCS state
    target_map = {name: (kind, gcs_path) for name, kind, _, gcs_path in get_sync_targets(home_dir, mount_path, profile_key)}
    stale_keys = [k for k in index if k not in seen_keys]
    for key in stale_keys:
        name, rel_file = key.split(":", 1)
        if name in target_map:
            kind, gcs_path = target_map[name]
            stale_dst = gcs_path if kind == "file" else os.path.join(gcs_path, rel_file)
            try:
                if os.path.isfile(stale_dst):
                    os.unlink(stale_dst)
            except OSError:
                pass
        del index[key]

    save_index(index, index_path)
    return updated_count


def run_daemon() -> None:
    if not is_state_mount_ready(MOUNT_PATH):
        return
    running = True

    def handle_sig(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    while running:
        for _ in range(SYNC_INTERVAL * 2):
            if not running:
                break
            time.sleep(0.5)
        if running:
            sync_state()


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fake_home = os.path.join(tmp, "home")
        fake_mount = os.path.join(tmp, "mnt")
        fake_index = os.path.join(tmp, "index.json")
        os.makedirs(fake_home, exist_ok=True)
        os.makedirs(fake_mount, exist_ok=True)

        # Seed fake GCS state
        chrome_gcs = os.path.join(fake_mount, "profiles", "test-svc", "google-chrome", "Default")
        os.makedirs(chrome_gcs, exist_ok=True)
        with open(os.path.join(chrome_gcs, "Preferences"), "w", encoding="utf-8") as f:
            json.dump({"profile": {"exit_type": "Crashed", "exited_cleanly": False}}, f)
        with open(os.path.join(chrome_gcs, "Bookmarks"), "w", encoding="utf-8") as f:
            f.write('{"roots": {}}')

        ssh_gcs = os.path.join(fake_mount, "shared", "ssh")
        os.makedirs(ssh_gcs, exist_ok=True)
        with open(os.path.join(ssh_gcs, "id_ed25519"), "w", encoding="utf-8") as f:
            f.write("PRIVATE_KEY")

        # 1. Test init_state
        init_state(fake_home, fake_mount, "test-svc", fake_index)
        assert os.path.islink(os.path.join(fake_home, "Downloads"))
        assert os.path.isfile(os.path.join(fake_home, ".config", "google-chrome", "Default", "Bookmarks"))
        with open(os.path.join(fake_home, ".config", "google-chrome", "Default", "Preferences"), "r", encoding="utf-8") as f:
            prefs = json.load(f)
        assert prefs["profile"]["exit_type"] == "Normal"
        assert (os.stat(os.path.join(fake_home, ".ssh", "id_ed25519")).st_mode & 0o777) == 0o600

        # 2. Test no-op sync (0 writes when nothing changed)
        assert sync_state(fake_home, fake_mount, "test-svc", fake_index) == 0

        # 3. Test incremental sync when Bookmarks is modified and Cache is ignored
        cache_dir = os.path.join(fake_home, ".config", "google-chrome", "Default", "Cache")
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, "data_0"), "w", encoding="utf-8") as f:
            f.write("cached_blob")
        with open(os.path.join(fake_home, ".config", "google-chrome", "Default", "Bookmarks"), "w", encoding="utf-8") as f:
            f.write('{"roots": {"bookmark_bar": []}}')

        assert sync_state(fake_home, fake_mount, "test-svc", fake_index) == 1
        assert not os.path.exists(os.path.join(chrome_gcs, "Cache"))
        log("Self-test passed successfully.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "init":
        init_state()
    elif cmd == "sync":
        sync_state()
    elif cmd == "daemon":
        run_daemon()
    elif cmd == "--self-test":
        run_self_test()
    else:
        print(f"Usage: {sys.argv[0]} [init|sync|daemon|--self-test]", file=sys.stderr)
        sys.exit(1)
