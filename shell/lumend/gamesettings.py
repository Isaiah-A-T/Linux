"""Per-game settings: controller remapping and performance profiles.

Each game can have its own frame rate cap, power mode and button layout. They
are applied when the game starts and put back when you return to the shell.

* FPS cap: gamescope's GAMESCOPE_FPS_LIMIT root window property (what
  SteamOS sets), which works for every game including Steam's. Epic, GOG and
  app launches also get DXVK_FRAME_RATE and VKD3D_FRAME_RATE, so the cap
  holds when the session falls back to cage.
* Power mode: power-profiles-daemon (performance, balanced, power-saver).
* Buttons: an InputPlumber device profile loaded on every controller it
  manages. Games, Steam and the shell all see the remapped virtual pad.
"""

import os
import re
import threading

from .util import ApiError, data_dir, have, load_json, mock_enabled, run, save_json

FPS_CAPS = [30, 40, 45, 60, 90, 120]

POWER_MODES = {
    "default": ("Default", "Use the system's own setting", None),
    "performance": ("Performance", "Highest clocks, loudest fans", "performance"),
    "balanced": ("Balanced", "Good speed with less heat", "balanced"),
    "battery": ("Quiet and battery saver", "Lower clocks, quieter fans, longer battery", "power-saver"),
}

# Buttons as the shell names them, in the order the remap page lists them,
# with InputPlumber's name for each (its event, then the capability name).
BUTTONS = {
    "a": ("A", "button", "South"),
    "b": ("B", "button", "East"),
    "x": ("X", "button", "West"),
    "y": ("Y", "button", "North"),
    "lb": ("LB", "button", "LeftBumper"),
    "rb": ("RB", "button", "RightBumper"),
    "lt": ("LT", "trigger", "LeftTrigger"),
    "rt": ("RT", "trigger", "RightTrigger"),
    "view": ("View", "button", "Select"),
    "menu": ("Menu", "button", "Start"),
    "ls": ("Left stick click", "button", "LeftStick"),
    "rs": ("Right stick click", "button", "RightStick"),
    "up": ("D-pad up", "button", "DPadUp"),
    "down": ("D-pad down", "button", "DPadDown"),
    "left": ("D-pad left", "button", "DPadLeft"),
    "right": ("D-pad right", "button", "DPadRight"),
}
# A button can also be turned off.
OFF = "off"

PRESETS = {
    "swap-ab": ("Swap A and B", "Nintendo-style confirm and back", {"a": "b", "b": "a"}),
    "swap-xy": ("Swap X and Y", "", {"x": "y", "y": "x"}),
    "swap-bumpers": ("Bumpers and triggers swapped", "LB is LT, RB is RT", {"lb": "lt", "lt": "lb", "rb": "rt", "rt": "rb"}),
}

DEFAULTS = {"fps": None, "power": "default", "remap": {}}

_lock = threading.Lock()
# What apply() changed, so restore() knows what to put back.
_active = {"id": None, "power": None, "fps": False, "remap": False}


def _path():
    return data_dir() / "game-settings.json"


def _all():
    return load_json(_path(), {})


def clean(settings):
    """A stored profile with anything unknown dropped."""
    s = {**DEFAULTS, **(settings or {})}
    return {
        "fps": s["fps"] if s.get("fps") in FPS_CAPS else None,
        "power": s["power"] if s.get("power") in POWER_MODES else "default",
        "remap": {k: v for k, v in (s.get("remap") or {}).items()
                  if k in BUTTONS and (v in BUTTONS or v == OFF) and v != k},
    }


def is_default(settings):
    return clean(settings) == DEFAULTS


def support():
    """What this system can apply. The UI greys out the rest and says why."""
    if mock_enabled():
        return {"fps": True, "power": True, "remap": True}
    return {"fps": have("xprop"), "power": have("powerprofilesctl"), "remap": have("busctl") and _inputplumber_running()}


def _inputplumber_running():
    return bool(run(["busctl", "--system", "status", "org.shadowblip.InputPlumber"], timeout=5).strip())


def get(item_id):
    return {
        "id": item_id,
        "settings": clean(_all().get(item_id)),
        "support": support(),
        "options": {
            "fps": FPS_CAPS,
            "power": [{"id": k, "label": l, "detail": d} for k, (l, d, _) in POWER_MODES.items()],
            "buttons": [{"id": k, "label": l} for k, (l, _, _) in BUTTONS.items()],
            "presets": [{"id": k, "label": l, "detail": d, "remap": m} for k, (l, d, m) in PRESETS.items()],
        },
    }


def update(item_id, payload):
    if not item_id:
        raise ApiError("Which game?")
    stored = _all()
    current = clean(stored.get(item_id))
    if "fps" in payload:
        if payload["fps"] is not None and payload["fps"] not in FPS_CAPS:
            raise ApiError("Pick one of the listed frame rates.")
        current["fps"] = payload["fps"]
    if "power" in payload:
        if payload["power"] not in POWER_MODES:
            raise ApiError("Unknown power mode.")
        current["power"] = payload["power"]
    if "remap" in payload:
        current["remap"] = payload["remap"] or {}
    current = clean(current)
    if is_default(current):
        stored.pop(item_id, None)
    else:
        stored[item_id] = current
    save_json(_path(), stored)
    return get(item_id)


# --- Applying ----------------------------------------------------------------

def launch_env(item_id):
    """Extra environment for launches we start ourselves (not Steam's)."""
    s = clean(_all().get(item_id))
    if not s["fps"]:
        return {}
    return {"DXVK_FRAME_RATE": str(s["fps"]), "VKD3D_FRAME_RATE": str(s["fps"])}


def apply(item_id):
    """Switch the system to a game's profile just before it starts."""
    s = clean(_all().get(item_id))
    with _lock:
        _restore_locked()
        _active["id"] = item_id
        if mock_enabled():
            _active.update(fps=bool(s["fps"]), remap=bool(s["remap"]))
            return s
        profile = POWER_MODES[s["power"]][2]
        if profile and have("powerprofilesctl"):
            before = run(["powerprofilesctl", "get"], timeout=5).strip()
            if before and before != profile and _set_power(profile):
                _active["power"] = before
        if s["fps"] and _set_fps(s["fps"]):
            _active["fps"] = True
        if s["remap"] and _load_controls(profile_yaml(item_id, s["remap"]), item_id):
            _active["remap"] = True
    return s


def restore():
    """Back in the shell: undo whatever apply() changed."""
    with _lock:
        changed = _restore_locked()
    return {"ok": True, "restored": changed}


def _restore_locked():
    changed = _active["id"] is not None
    if not mock_enabled():
        if _active["power"]:
            _set_power(_active["power"])
        if _active["fps"]:
            _set_fps(0)
        if _active["remap"]:
            _load_controls(profile_yaml(None, {}), None)
    _active.update(id=None, power=None, fps=False, remap=False)
    return changed


def restore_when_done(proc, item_id):
    """Put things back when a game we started ourselves exits."""
    if proc is None:
        return

    def wait():
        proc.wait()
        with _lock:
            if _active["id"] == item_id:
                _restore_locked()

    threading.Thread(target=wait, daemon=True).start()


def active():
    return _active["id"]


def _set_power(profile):
    try:
        run(["powerprofilesctl", "set", profile], timeout=10, check=True)
        return True
    except RuntimeError:
        return False


def _display():
    # lumend starts before gamescope, so it may not have DISPLAY yet.
    return os.environ.get("DISPLAY") or os.environ.get("LUMEN_DISPLAY") or ":0"


def _set_fps(fps):
    if not have("xprop"):
        return False
    cmd = ["xprop", "-root", "-f", "GAMESCOPE_FPS_LIMIT", "32c", "-set", "GAMESCOPE_FPS_LIMIT", str(fps)]
    try:
        run(cmd, timeout=5, check=True, env={"DISPLAY": _display()})
        return True
    except RuntimeError:
        return False


# --- InputPlumber ------------------------------------------------------------

def _event(name):
    _, kind, cap = BUTTONS[name]
    if kind == "trigger":
        return f"      - gamepad:\n          trigger:\n            name: {cap}\n"
    return f"      - gamepad:\n          button: {cap}\n"


def profile_yaml(item_id, remap):
    """An InputPlumber DeviceProfile. Buttons not listed pass through."""
    lines = ["version: 1\n", "kind: DeviceProfile\n",
             f"name: Lumen {_yaml_str(item_id or 'default')}\n", "mapping:"]
    if not remap:
        lines.append(" []\n")
        return "".join(lines)
    lines.append("\n")
    for src in BUTTONS:  # stable order
        if src not in remap:
            continue
        dst = remap[src]
        lines.append(f"  - name: {_yaml_str(src + ' to ' + dst)}\n    source_events:\n")
        lines.append(_event(src))
        if dst == OFF:
            lines.append("    target_events: []\n")
        else:
            lines.append("    target_events:\n")
            lines.append(_event(dst))
    return "".join(lines)


def _yaml_str(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def prepare():
    """At session start: let InputPlumber take over every controller.

    By default it only manages handheld built-in pads. Plain USB and Bluetooth
    controllers need ManageAllDevices, and their virtual pads take a moment to
    appear, so this runs well before the first game starts.
    """
    if mock_enabled() or not have("busctl"):
        return
    run(["busctl", "--system", "set-property", "org.shadowblip.InputPlumber",
         "/org/shadowblip/InputPlumber/Manager", "org.shadowblip.InputManager",
         "ManageAllDevices", "b", "true"], timeout=10)


def _composite_devices():
    out = run(["busctl", "--system", "--list", "tree", "org.shadowblip.InputPlumber"], timeout=5)
    return [p for p in out.split() if re.fullmatch(r"/org/shadowblip/InputPlumber/CompositeDevice\d+", p)]


def _load_controls(yaml_text, item_id):
    if not have("busctl"):
        return False
    folder = data_dir() / "controls"
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", item_id or "default")
    path = folder / f"{safe}.yaml"
    path.write_text(yaml_text)
    # InputPlumber runs as root and reads the file itself.
    path.chmod(0o644)
    ok = False
    for dev in _composite_devices():
        try:
            run(["busctl", "--system", "call", "org.shadowblip.InputPlumber", dev,
                 "org.shadowblip.Input.CompositeDevice", "LoadProfilePath", "s", str(path)],
                timeout=5, check=True)
            ok = True
        except RuntimeError:
            continue
    return ok
