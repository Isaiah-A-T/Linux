"""Watch controllers for the Guide button, whatever window has focus.

While a game is on screen the shell's Chromium window doesn't see the
controller, so lumend reads the evdev devices itself. logind gives the
signed-in user access to joysticks (the uaccess tag), so no extra
permissions are needed. Guide fires on release, and only when no other
button was pressed while it was held, so Guide + Y (screenshot) and similar
combinations are left alone.
"""

import glob
import os
import select
import struct
import threading
import time

EV_KEY = 1
BTN_MODE = 0x13C
_EVENT = struct.Struct("llHHi")
_LONG_BITS = struct.calcsize("l") * 8


def has_guide(caps):
    """caps is the text of /sys/class/input/eventN/device/capabilities/key."""
    value = 0
    for word in caps.split():
        value = (value << _LONG_BITS) | int(word, 16)
    return bool(value >> BTN_MODE & 1)


class GuideWatcher:
    def __init__(self, on_guide):
        self.on_guide = on_guide
        self.fds = {}  # path -> fd
        self.held = {}  # fd -> True while Guide is down and nothing else was pressed

    def _scan(self):
        for path in glob.glob("/dev/input/event*"):
            if path in self.fds:
                continue
            name = os.path.basename(path)
            try:
                with open(f"/sys/class/input/{name}/device/capabilities/key") as f:
                    if not has_guide(f.read()):
                        continue
                self.fds[path] = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except (OSError, ValueError):
                continue

    def _drop(self, path):
        fd = self.fds.pop(path)
        self.held.pop(fd, None)
        try:
            os.close(fd)
        except OSError:
            pass

    def feed(self, fd, etype, code, value):
        if etype != EV_KEY:
            return
        if code == BTN_MODE:
            if value == 1:
                self.held[fd] = True
            elif value == 0 and self.held.pop(fd, False):
                self.on_guide()
        elif value == 1 and fd in self.held:
            self.held[fd] = False  # a combination, not a Guide press

    def run(self):
        next_scan = 0
        while True:
            if time.monotonic() >= next_scan:
                self._scan()
                next_scan = time.monotonic() + 3
            by_fd = {fd: path for path, fd in self.fds.items()}
            if not by_fd:
                time.sleep(3)
                continue
            ready, _, _ = select.select(list(by_fd), [], [], 3)
            for fd in ready:
                try:
                    data = os.read(fd, _EVENT.size * 64)
                except BlockingIOError:
                    continue
                except OSError:  # unplugged
                    self._drop(by_fd[fd])
                    continue
                for i in range(0, len(data) - _EVENT.size + 1, _EVENT.size):
                    _sec, _usec, etype, code, value = _EVENT.unpack_from(data, i)
                    try:
                        self.feed(fd, etype, code, value)
                    except Exception:  # never let a callback kill the watcher
                        pass


def watch(on_guide):
    threading.Thread(target=GuideWatcher(on_guide).run, name="guide", daemon=True).start()
