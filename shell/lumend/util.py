"""Helpers shared by the lumend modules."""

import json
import os
import shutil
import subprocess
from pathlib import Path


def mock_enabled():
    return os.environ.get("LUMEN_MOCK") == "1"


def have(cmd):
    return shutil.which(cmd) is not None


def run(cmd, timeout=15, check=False, env=None, input=None):
    """Run a command and return its stdout as text ("" if it is missing)."""
    if not have(cmd[0]):
        return ""
    full_env = None
    if env:
        full_env = {**os.environ, **env}
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=full_env, input=input
        )
    except subprocess.TimeoutExpired:
        # bluetoothctl waits forever when bluetoothd isn't running.
        if check:
            raise RuntimeError(f"{cmd[0]} timed out")
        return ""
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"{cmd[0]} failed")
    return proc.stdout


def data_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    # Mock mode keeps its fake recents and settings away from real ones.
    path = Path(base) / ("lumen-mock" if mock_enabled() else "lumen")
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_dir():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/lumen-{os.getuid()}"
    path = Path(base) / "lumen"
    path.mkdir(parents=True, exist_ok=True)
    return path


_DISPLAY_KEYS = ("DISPLAY", "WAYLAND_DISPLAY", "GAMESCOPE_WAYLAND_DISPLAY")


def display_env():
    """The display the shell is on, as written by lumen-ui.

    lumend starts before gamescope, so its own environment has no DISPLAY.
    lumen-ui runs inside gamescope and records gamescope's displays for us.
    """
    env = {k: os.environ[k] for k in _DISPLAY_KEYS if os.environ.get(k)}
    try:
        lines = (runtime_dir() / "display.env").read_text().splitlines()
    except OSError:
        return env
    for line in lines:
        key, _, value = line.partition("=")
        if key in _DISPLAY_KEYS and value:
            env[key] = value
    return env


def session_env(extra=None):
    """Environment for anything lumend starts on screen (games and apps)."""
    return {**os.environ, **display_env(), **(extra or {})}


def games_dir():
    path = Path(os.environ.get("LUMEN_GAMES_DIR") or os.path.expanduser("~/Games"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def save_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2))
    tmp.replace(path)


class ApiError(Exception):
    """An error the UI should show to the user."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status
