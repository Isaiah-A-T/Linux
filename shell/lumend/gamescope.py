"""Choose what gamescope shows: the shell or a game.

gamescope lists the windows it can show in the GAMESCOPE_FOCUSABLE_WINDOWS
root property, as (window, app id, pid) triples, and shows the window named
in GAMESCOPECTRL_BASELAYER_WINDOW when that is set. We read and set both with
xprop on gamescope's Xwayland display. Under cage (no gamescope) none of this
exists and every call here quietly does nothing.
"""

import os
import re
import subprocess

from .util import display_env, have

_FOCUSABLE = "GAMESCOPE_FOCUSABLE_WINDOWS"
_BASELAYER = "GAMESCOPECTRL_BASELAYER_WINDOW"


def _xprop(*args):
    env = display_env()
    if not have("xprop") or not env.get("DISPLAY"):
        return None
    try:
        proc = subprocess.run(["xprop", "-root", *args], capture_output=True, text=True, timeout=3,
                              env={**os.environ, **env})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def parse_windows(text):
    """'GAMESCOPE_FOCUSABLE_WINDOWS = 1, 2, 3, ...' -> [(window, appid, pid)]."""
    nums = [int(n) for n in re.findall(r"\d+", (text or "").partition("=")[2])]
    return [tuple(nums[i:i + 3]) for i in range(0, len(nums) - 2, 3)]


def windows():
    return parse_windows(_xprop("-notype", _FOCUSABLE))


def _show_window(window):
    return _xprop("-f", _BASELAYER, "32c", "-set", _BASELAYER, str(window)) is not None


def show(pids):
    """Bring the newest window owned by one of pids to the front."""
    pids = set(pids)
    found = [w for w, _appid, pid in windows() if pid in pids]
    return _show_window(found[-1]) if found else False


def release():
    """Let gamescope pick the window itself again (normally the newest)."""
    return _xprop("-remove", _BASELAYER) is not None


def shown():
    out = _xprop("-notype", _BASELAYER) or ""
    nums = re.findall(r"\d+", out.partition("=")[2])
    return int(nums[0]) if nums else None


def _is_shell(pid, port):
    try:
        cmdline = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="replace")
    except OSError:
        return False
    return f"127.0.0.1:{port}/" in cmdline and "chromium" in cmdline


def show_shell():
    port = os.environ.get("LUMEN_PORT", "7777")
    for window, _appid, pid in windows():
        if _is_shell(pid, port):
            return _show_window(window)
    return False
