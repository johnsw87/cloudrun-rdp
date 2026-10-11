#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Patches Xpra 6.x XpraDesktopServer so that RandR 1.6 Xdummy virtual monitors
# (VFB-0 / DUMMY0) are resized together with the X11 root screen via
# RandRBindings().set_crtc_config() on initial client connection and browser
# viewport resize.

import pathlib
import py_compile
import sys

DESKTOP_SERVER_PATH = pathlib.Path(
    "/usr/lib/python3/dist-packages/xpra/x11/desktop/desktop_server.py"
)
DESKTOP_MODEL_PATH = pathlib.Path(
    "/usr/lib/python3/dist-packages/xpra/x11/desktop/desktop_model.py"
)

SET_SCREEN_SIZE_METHOD = """    def set_screen_size(self, desired_w: int, desired_h: int) -> tuple[int, int]:
        from xpra.x11.subsystem.display import get_root_size
        if not self.randr:
            return get_root_size()
        with xsync:
            randr = RandRBindings()
            dummy16 = randr.is_dummy16()
            monitors = randr.get_monitor_properties() if dummy16 else {}
        if dummy16 and len(monitors) == 1:
            with xsync:
                if randr.set_crtc_config({0: {
                    "name": "VFB-0",
                    "primary": True,
                    "geometry": (0, 0, desired_w, desired_h),
                    "automatic": True,
                }}):
                    root_w, root_h = randr.get_screen_size()
                    screenlog.info(
                        "server virtual display and VFB-0 monitor now set to %ix%i",
                        root_w,
                        root_h,
                    )
                    for window in tuple(self._id_to_window.values()):
                        if hasattr(window, "_screen_size_changed"):
                            window._screen_size_changed()
                    return root_w, root_h
        return super().set_screen_size(desired_w, desired_h)

"""


def patch_desktop_server(path: pathlib.Path) -> None:
  content = path.read_text(encoding="utf-8")
  if "def set_screen_size(" in content:
    print(f"set_screen_size already present in {path}, skipping")
    return
  anchor = "    def resize(self, w: int, h: int) -> None:\n"
  if anchor not in content:
    raise RuntimeError(f"Could not find resize() anchor in {path}")
  patched = content.replace(anchor, SET_SCREEN_SIZE_METHOD + anchor, 1)
  path.write_text(patched, encoding="utf-8")
  py_compile.compile(str(path), doraise=True)
  print(f"Successfully patched {path}")


def patch_desktop_model(path: pathlib.Path) -> None:
  content = path.read_text(encoding="utf-8")
  old_check = (
      "            with xsync:\n"
      "                ow, oh = RandR.get_screen_size()\n"
      "            if ow == rw and oh == rh:\n"
      "                return\n"
  )
  new_check = (
      "            with xsync:\n"
      "                ow, oh = RandR.get_screen_size()\n"
      "                is_d16 = RandR.is_dummy16()\n"
      "            if ow == rw and oh == rh and not is_d16:\n"
      "                return\n"
  )
  if old_check in content:
    patched = content.replace(old_check, new_check, 1)
    path.write_text(patched, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    print(f"Successfully patched {path}")
  else:
    print(f"desktop_model check already updated or differs in {path}, skipping")


def main() -> int:
  server_path = (
      pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DESKTOP_SERVER_PATH
  )
  model_path = (
      pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DESKTOP_MODEL_PATH
  )
  patch_desktop_server(server_path)
  patch_desktop_model(model_path)
  return 0


if __name__ == "__main__":
  sys.exit(main())
