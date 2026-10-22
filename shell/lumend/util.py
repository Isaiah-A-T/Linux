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
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, env=full_env, input=input
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"{cmd[0]} failed")
    return proc.stdout


def data_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    # Mock mode keeps its fake recents and settings away from real ones.
    path = Path(base) / ("lumen-mock" if mock_enabled() else "lumen")
    path.mkdir(parents=True, exist_ok=True)
    return path


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
