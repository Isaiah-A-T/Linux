"""Screenshots and clips from a controller button, even while a game runs.

The shell can't see the controller while a game has focus, so lumend reads
the controllers itself from /dev/input (read only, nothing is grabbed, so
games still get every press):

  Guide + RB        screenshot
  Guide + LB        save the last 30 seconds as a clip
  Share (tap)       screenshot          (Xbox Series and other pads with one)
  Share (hold)      save a clip

Screenshots come from gamescope (the same request Steam uses), clips from
gpu-screen-recorder running in replay mode, which keeps the last N seconds
in memory and writes them out when it gets SIGUSR1.
"""

import array
import fcntl
import glob
import os
import selectors
import shutil
import signal
import struct
import subprocess
import threading
import time
from pathlib import Path

from . import jobs
from .util import ApiError, data_dir, have, load_json, mock_enabled, run, save_json

EV_KEY = 0x01
BTN_SOUTH = 0x130
BTN_TL = 0x136
BTN_TR = 0x137
BTN_MODE = 0x13C
KEY_RECORD = 167

EVENT = struct.Struct("llHHi")
HOLD = 0.6        # seconds on Share that count as "hold" (clip) not "tap"
DEBOUNCE = 1.0
CLIP_LENGTHS = [15, 30, 60, 120]


def _ioc_read(nr, size):
    return (2 << 30) | (size << 16) | (ord("E") << 8) | nr


def _has_bit(bits, n):
    return bool(bits[n // 8] & (1 << (n % 8)))


# --- Where things go ---------------------------------------------------------


def shots_dir():
    pics = Path(os.environ.get("XDG_PICTURES_DIR") or os.path.expanduser("~/Pictures"))
    return pics / "Screenshots"


def clips_dir():
    videos = Path(os.environ.get("XDG_VIDEOS_DIR") or os.path.expanduser("~/Videos"))
    return videos / "Clips"


def _runtime_dir():
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def gamescope_display():
    """gamescope's X display. lumen-ui runs inside gamescope and writes it down."""
    try:
        return (_runtime_dir() / "lumen" / "gamescope-display").read_text().strip() or None
    except OSError:
        return None


def stamp():
    return time.strftime("%Y-%m-%d %H-%M-%S")


# --- Settings ----------------------------------------------------------------


def _settings_path():
    return data_dir() / "capture.json"


def settings():
    s = load_json(_settings_path(), {})
    length = s.get("clip_length", 30)
    return {
        "clips": s.get("clips", True),
        "clip_length": length if length in CLIP_LENGTHS else 30,
    }


def status():
    s = settings()
    if mock_enabled():
        return {**s, "clip_lengths": CLIP_LENGTHS, "screenshots_available": True,
                "clips_available": True, "recording": s["clips"], "controllers": 1}
    return {
        **s,
        "clip_lengths": CLIP_LENGTHS,
        "screenshots_available": gamescope_display() is not None,
        "clips_available": have("gpu-screen-recorder"),
        "recording": _recorder.running(),
        "controllers": _watcher.count(),
    }


def update_settings(payload):
    s = load_json(_settings_path(), {})
    if isinstance(payload.get("clips"), bool):
        s["clips"] = payload["clips"]
    if payload.get("clip_length") in CLIP_LENGTHS:
        s["clip_length"] = payload["clip_length"]
    save_json(_settings_path(), s)
    if not mock_enabled():
        _recorder.restart()
    return status()


# --- Screenshots -------------------------------------------------------------


def screenshot():
    """Ask gamescope for a screenshot and file it under ~/Pictures/Screenshots."""
    if mock_enabled():
        return jobs.note("Screenshot saved", "Saved to Album")
    display = gamescope_display()
    if not display or not have("xprop"):
        raise ApiError("Screenshots need the gamescope session.")
    asked = time.time()
    # gamescope writes /tmp/gamescope.png when this root property is set.
    # 2 = the full composition, overlays included.
    run(["xprop", "-display", display, "-root", "-f", "GAMESCOPECTRL_REQUEST_SCREENSHOT",
         "32c", "-set", "GAMESCOPECTRL_REQUEST_SCREENSHOT", "2"], timeout=5)
    shot = _wait_for_new(lambda: glob.glob("/tmp/gamescope*.png"), asked, 5.0)
    if not shot:
        return jobs.note("Screenshot failed", "gamescope didn't save one")
    shots_dir().mkdir(parents=True, exist_ok=True)
    dest = shots_dir() / f"Screenshot {stamp()}.png"
    shutil.move(shot, dest)
    return jobs.note("Screenshot saved", "Saved to Album")


def _wait_for_new(list_files, since, timeout):
    """The newest file from list_files() written after `since` and done growing."""
    end = time.time() + timeout
    while time.time() < end:
        fresh = []
        for f in list_files():
            try:
                st = os.stat(f)
            except OSError:
                continue
            if st.st_mtime >= since - 0.5 and st.st_size > 0:
                fresh.append((st.st_mtime, f, st.st_size))
        if fresh:
            _, path, size = max(fresh)
            time.sleep(0.3)
            try:
                if os.path.getsize(path) == size:
                    return path
            except OSError:
                pass
        time.sleep(0.15)
    return None


# --- Clips ---------------------------------------------------------------------


class Recorder:
    """gpu-screen-recorder in replay mode, restarted if it exits."""

    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.failures = 0

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def wanted(self):
        return settings()["clips"] and have("gpu-screen-recorder") and gamescope_display() is not None

    def command(self):
        clips_dir().mkdir(parents=True, exist_ok=True)
        return ["gpu-screen-recorder", "-w", "screen", "-f", "60", "-c", "mp4",
                "-a", "default_output", "-r", str(settings()["clip_length"]),
                "-o", str(clips_dir())]

    def ensure(self):
        with self.lock:
            if self.running():
                return
            if not self.wanted() or self.failures >= 5:
                return
            if self.proc is not None:
                self.failures += 1
            try:
                self.proc = subprocess.Popen(self.command(), stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                self.proc = None
                self.failures = 5

    def stop(self):
        with self.lock:
            if self.running():
                self.proc.send_signal(signal.SIGINT)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None

    def restart(self):
        self.stop()
        self.failures = 0
        self.ensure()

    def save(self):
        if not self.running():
            return None
        asked = time.time()
        self.proc.send_signal(signal.SIGUSR1)
        return _wait_for_new(lambda: glob.glob(str(clips_dir() / "*.mp4")), asked, 20.0)


_recorder = Recorder()


def clip():
    if mock_enabled():
        return jobs.note("Clip saved", f"The last {settings()['clip_length']} seconds are in Album")
    if not settings()["clips"]:
        raise ApiError("Clip recording is off. Turn it on in Settings › Saves & captures.")
    _recorder.ensure()
    path = _recorder.save()
    if not path:
        return jobs.note("Clip failed", "The recorder isn't running")
    dest = Path(path).with_name(f"Clip {stamp()}.mp4")
    os.replace(path, dest)
    return jobs.note("Clip saved", f"The last {settings()['clip_length']} seconds are in Album")


# --- Controller buttons --------------------------------------------------------


class Watcher:
    """Reads every controller's evdev node and turns button combos into captures."""

    def __init__(self, on_shot, on_clip):
        self.on_shot = on_shot
        self.on_clip = on_clip
        self.sel = selectors.DefaultSelector()
        self.devices = {}  # path -> state dict
        self.last_fire = 0.0

    def count(self):
        return len(self.devices)

    def scan(self):
        for path in glob.glob("/dev/input/event*"):
            if path in self.devices:
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            if not self._is_pad(fd):
                os.close(fd)
                continue
            st = {"fd": fd, "held": set(), "share_down": None}
            self.devices[path] = st
            self.sel.register(fd, selectors.EVENT_READ, path)

    @staticmethod
    def _is_pad(fd):
        bits = array.array("B", bytes(96))
        try:
            fcntl.ioctl(fd, _ioc_read(0x20 + EV_KEY, len(bits)), bits, True)
        except OSError:
            return False
        return _has_bit(bits, BTN_SOUTH) and (_has_bit(bits, BTN_MODE) or _has_bit(bits, KEY_RECORD))

    def drop(self, path):
        st = self.devices.pop(path, None)
        if st:
            self.sel.unregister(st["fd"])
            os.close(st["fd"])

    def fire(self, fn):
        now = time.monotonic()
        if now - self.last_fire < DEBOUNCE:
            return
        self.last_fire = now
        threading.Thread(target=self._safe, args=(fn,), daemon=True).start()

    @staticmethod
    def _safe(fn):
        try:
            fn()
        except Exception as exc:  # a failed capture must not stop the watcher
            jobs.note("Capture failed", str(exc))

    def handle(self, st, code, value):
        """One key event from one controller."""
        held = st["held"]
        if value == 1:
            held.add(code)
            if BTN_MODE in held and code == BTN_TR:
                self.fire(self.on_shot)
            elif BTN_MODE in held and code == BTN_TL:
                self.fire(self.on_clip)
            elif code == KEY_RECORD:
                st["share_down"] = time.monotonic()
        elif value == 0:
            held.discard(code)
            if code == KEY_RECORD and st["share_down"] is not None:
                long = time.monotonic() - st["share_down"] >= HOLD
                st["share_down"] = None
                self.fire(self.on_clip if long else self.on_shot)

    def read(self, path):
        st = self.devices[path]
        try:
            data = os.read(st["fd"], EVENT.size * 64)
        except BlockingIOError:
            return
        except OSError:  # unplugged
            self.drop(path)
            return
        for i in range(0, len(data) - EVENT.size + 1, EVENT.size):
            _, _, etype, code, value = EVENT.unpack_from(data, i)
            if etype == EV_KEY:
                self.handle(st, code, value)

    def loop(self):
        next_scan = 0.0
        while True:
            if time.monotonic() >= next_scan:
                self.scan()
                _recorder.ensure()
                next_scan = time.monotonic() + 3
            if not self.devices:
                time.sleep(1)
                continue
            for key, _ in self.sel.select(timeout=1):
                self.read(key.data)


_watcher = Watcher(screenshot, clip)


def start():
    """Start watching controllers and keeping the clip recorder running."""
    if mock_enabled():
        return
    threading.Thread(target=_watcher.loop, daemon=True, name="capture").start()
