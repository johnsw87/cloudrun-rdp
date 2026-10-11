#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Patches Xpra 6.x server audio subsystem and HTML5 client so that:
# 1. xpra/server/source/audio.py passes "volume", f"volume={VOLUME}" as separate
#    argv tokens to gst-launch-1.0 in new_stream_sound() (eliminating
#    "WARNING: erroneous pipeline: syntax error" in Cloud Run logs).
# 2. xpra/audio/pulseaudio/pactl_impl.py strips surrounding quotes from
#    PulseAudio device descriptions and classes on Ubuntu 24.04 (PulseAudio 16.1).
# 3. /usr/share/xpra/www/js/Client.js overrides XpraClient.prototype._audio_start_stream
#    to handle Chrome's Web Autoplay Policy gracefully: if initial audio playback
#    before a user gesture is blocked with NotAllowedError, it automatically
#    unlocks and starts the audio stream on the user's very first click or
#    keypress inside the remote desktop/browser, and ensures manual toolbar
#    speaker toggles work cleanly.

import gzip
import pathlib
import py_compile
import sys

SERVER_AUDIO_SOURCE_PATH = pathlib.Path(
    "/usr/lib/python3/dist-packages/xpra/server/source/audio.py"
)
PACTL_IMPL_PATH = pathlib.Path(
    "/usr/lib/python3/dist-packages/xpra/audio/pulseaudio/pactl_impl.py"
)
HTML5_CLIENT_JS_PATH = pathlib.Path("/usr/share/xpra/www/js/Client.js")


def patch_server_audio_source(path: pathlib.Path) -> None:
  if not path.exists():
    raise FileNotFoundError(f"Expected Xpra file not found: {path}")
  content = path.read_text(encoding="utf-8")
  old_snippet = '            "!", f"volume volume={VOLUME}",\n'
  new_snippet = '            "!", "volume", f"volume={VOLUME}",\n'
  if old_snippet in content:
    content = content.replace(old_snippet, new_snippet, 1)
    path.write_text(content, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    print(f"Patched gst-launch-1.0 volume args in {path}")
  elif new_snippet in content:
    print(f"gst-launch-1.0 volume args already patched in {path}")
  else:
    print(f"Note: volume snippet not found verbatim in {path}, continuing")


def patch_pactl_impl(path: pathlib.Path) -> None:
  if not path.exists():
    print(f"Note: {path} not found, skipping")
    return
  content = path.read_text(encoding="utf-8")
  changed = False
  if 'line.removeprefix("device-class = ")' in content:
    content = content.replace(
        'line.removeprefix("device-class = ")',
        'line.removeprefix("device.class = ").strip(\'"\')',
    )
    changed = True
  elif 'device_class = line.removeprefix("device.class = ")' in content:
    content = content.replace(
        'device_class = line.removeprefix("device.class = ")',
        'device_class = line.removeprefix("device.class = ").strip(\'"\')',
    )
    changed = True

  if 'device_description = line.removeprefix("device.description = ")' in content:
    content = content.replace(
        'device_description = line.removeprefix("device.description = ")',
        'device_description = line.removeprefix("device.description = ").strip(\'"\')',
    )
    changed = True

  if changed:
    path.write_text(content, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    print(f"Patched PulseAudio pactl parser in {path}")
  else:
    print(f"PulseAudio pactl parser already clean in {path}")


AUDIO_START_STREAM_OVERRIDE = """

// Cloud Run Xpra audio autoplay unlock & toolbar toggle fix
XpraClient.prototype._audio_start_stream = function() {
  this.debug("audio", "audio start of " + this.audio_framework + " " + this.audio_codec + " stream");
  if (this.audio_state === "playing") {
    return;
  }
  this.on_audio_state_change("waiting", this.audio_framework + " playing " + this.audio_codec + " stream");
  if (this.audio_framework === "mediasource") {
    if (!this.audio) {
      return;
    }
    var self = this;
    var play = this.audio.play();
    if (!play) {
      this.on_audio_state_change("error", "no promise");
      this.close_audio();
      return;
    }
    play.then(
      function(result) {
        self.debug("audio", "stream playing", result);
      },
      function(error) {
        if (error && (error.name === "NotAllowedError" || String(error).indexOf("NotAllowedError") >= 0)) {
          self.log("audio autoplay blocked until first user interaction; will auto-start on click/keypress");
          self.close_audio();
          if (!self._autoplay_unlock_registered) {
            self._autoplay_unlock_registered = true;
            var events = ["pointerdown", "mousedown", "keydown", "touchstart"];
            var unlock = function() {
              for (var i = 0; i < events.length; i++) {
                window.removeEventListener(events[i], unlock, true);
              }
              self._autoplay_unlock_registered = false;
              if (self.audio_context && self.audio_context.state === "suspended") {
                self.audio_context.resume().catch(function() {});
              }
              if (self.connected && self.audio_enabled && self.audio_state !== "playing") {
                self._sound_start_receiving();
              }
            };
            for (var i = 0; i < events.length; i++) {
              window.addEventListener(events[i], unlock, { once: true, capture: true });
            }
          }
          return;
        }
        self.on_audio_state_change("error", "stream failed:" + error);
        self.close_audio();
      }
    );
  } else if (this.audio_framework === "http-stream") {
    this.log("invalid start-of-stream data for http-stream framework");
  } else if (this.audio_framework === "aurora") {
    this.audio_aurora_ctx.play();
  } else {
    this.on_audio_state_change("error", "unknown framework " + this.audio_framework);
    this.close_audio();
  }
};
"""


def patch_html5_client_js(path: pathlib.Path) -> None:
  if not path.exists():
    raise FileNotFoundError(f"Expected Xpra HTML5 Client.js not found: {path}")
  content = path.read_text(encoding="utf-8")
  if "_autoplay_unlock_registered" in content:
    print(f"HTML5 Client.js already patched in {path}")
    return
  if "XpraClient" not in content or "_audio_start_stream" not in content:
    raise RuntimeError(f"Expected XpraClient._audio_start_stream not found in {path}")
  patched = content + AUDIO_START_STREAM_OVERRIDE
  path.write_text(patched, encoding="utf-8")

  # Remove pre-compressed brotli sidecar if present and update gzip sidecar
  br_path = path.with_suffix(path.suffix + ".br")
  if br_path.exists():
    br_path.unlink()
    print(f"Removed stale {br_path}")

  gz_path = path.with_suffix(path.suffix + ".gz")
  if gz_path.exists():
    with gzip.open(gz_path, "wb", compresslevel=9) as f:
      f.write(patched.encode("utf-8"))
    print(f"Updated pre-compressed {gz_path}")

  print(f"Successfully patched HTML5 audio autoplay & stream start in {path}")


def main() -> int:
  patch_server_audio_source(SERVER_AUDIO_SOURCE_PATH)
  patch_pactl_impl(PACTL_IMPL_PATH)
  patch_html5_client_js(HTML5_CLIENT_JS_PATH)
  return 0


if __name__ == "__main__":
  sys.exit(main())
