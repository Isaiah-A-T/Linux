"""Quick Settings: Wi-Fi, Bluetooth, volume, brightness, battery and power.

Each function talks to the stock Arch tools (nmcli, bluetoothctl, wpctl,
brightnessctl, systemctl). In mock mode they use an in-memory fake instead.
"""

import glob
import os
import re

from . import mock
from .util import ApiError, have, mock_enabled, run


def _split_terse(line):
    """Split one line of `nmcli -t` output; ':' inside a field is escaped."""
    fields, cur, i = [], "", 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            cur += line[i + 1]
            i += 2
            continue
        if ch == ":":
            fields.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    fields.append(cur)
    return fields


# --- Wi-Fi -----------------------------------------------------------------

def parse_wifi_list(text):
    """Turn `nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY dev wifi list` into dicts.

    Hidden networks are dropped and each SSID is kept once, strongest first.
    """
    best = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        in_use, ssid, signal, security = (_split_terse(line) + ["", "", "", ""])[:4]
        if not ssid:
            continue
        net = {
            "ssid": ssid,
            "signal": int(signal or 0),
            "secure": bool(security and security != "--"),
            "connected": in_use == "*",
        }
        old = best.get(ssid)
        if old is None or net["connected"] or (not old["connected"] and net["signal"] > old["signal"]):
            best[ssid] = net
    return sorted(best.values(), key=lambda n: (not n["connected"], -n["signal"]))


def wifi_state(rescan=False):
    if mock_enabled():
        return mock.state["wifi"]
    enabled = run(["nmcli", "-t", "-f", "WIFI", "general"]).strip() == "enabled"
    networks = []
    if enabled:
        out = run(
            ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
             "--rescan", "yes" if rescan else "auto"],
            timeout=30,
        )
        networks = parse_wifi_list(out)
    return {"enabled": enabled, "available": have("nmcli"), "networks": networks}


def wifi_set_enabled(on):
    if mock_enabled():
        mock.state["wifi"]["enabled"] = bool(on)
        return wifi_state()
    run(["nmcli", "radio", "wifi", "on" if on else "off"], check=True)
    return wifi_state()


def wifi_connect(ssid, password=None):
    if mock_enabled():
        for net in mock.state["wifi"]["networks"]:
            net["connected"] = net["ssid"] == ssid
        return wifi_state()
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    try:
        run(cmd, timeout=45, check=True)
    except RuntimeError as exc:
        raise ApiError(f"Couldn't join {ssid}: {exc}") from exc
    return wifi_state()


def wifi_disconnect(ssid):
    if mock_enabled():
        for net in mock.state["wifi"]["networks"]:
            if net["ssid"] == ssid:
                net["connected"] = False
        return wifi_state()
    run(["nmcli", "connection", "down", "id", ssid])
    return wifi_state()


# --- Bluetooth -------------------------------------------------------------

_DEVICE = re.compile(r"^Device ([0-9A-F:]{17}) (.+)$", re.M)


def _bt_devices(*filters):
    return {mac: name for mac, name in _DEVICE.findall(run(["bluetoothctl", "devices", *filters], timeout=3))}


def bluetooth_state():
    if mock_enabled():
        return mock.state["bluetooth"]
    if not have("bluetoothctl"):
        return {"available": False, "enabled": False, "devices": []}
    # With no adapter or no bluetoothd this times out and returns "".
    show = run(["bluetoothctl", "show"], timeout=3)
    if "Controller" not in show:
        return {"available": False, "enabled": False, "devices": []}
    powered = "Powered: yes" in show
    devices = []
    if powered:
        paired = _bt_devices("Paired")
        connected = _bt_devices("Connected")
        for mac, name in _bt_devices().items():
            devices.append({
                "address": mac,
                "name": name,
                "paired": mac in paired,
                "connected": mac in connected,
            })
    devices.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return {"available": True, "enabled": powered, "devices": devices}


def bluetooth_set_enabled(on):
    if mock_enabled():
        mock.state["bluetooth"]["enabled"] = bool(on)
        return bluetooth_state()
    run(["bluetoothctl", "power", "on" if on else "off"], check=True)
    return bluetooth_state()


def bluetooth_scan(seconds=8):
    if not mock_enabled():
        run(["bluetoothctl", "--timeout", str(seconds), "scan", "on"], timeout=seconds + 5)
    return bluetooth_state()


def bluetooth_connect(address):
    if mock_enabled():
        for dev in mock.state["bluetooth"]["devices"]:
            if dev["address"] == address:
                dev["paired"] = dev["connected"] = True
        return bluetooth_state()
    if address not in _bt_devices("Paired"):
        run(["bluetoothctl", "--timeout", "20", "pair", address], timeout=30)
        run(["bluetoothctl", "trust", address])
    out = run(["bluetoothctl", "--timeout", "15", "connect", address], timeout=25)
    if "successful" not in out:
        raise ApiError("Couldn't connect. Put the device in pairing mode and try again.")
    return bluetooth_state()


def bluetooth_disconnect(address, forget=False):
    if mock_enabled():
        for dev in mock.state["bluetooth"]["devices"]:
            if dev["address"] == address:
                dev["connected"] = False
                if forget:
                    dev["paired"] = False
        return bluetooth_state()
    run(["bluetoothctl", "remove" if forget else "disconnect", address], timeout=15)
    return bluetooth_state()


# --- Audio, brightness, battery -------------------------------------------

def parse_wpctl_volume(text):
    match = re.search(r"Volume:\s*([\d.]+)", text)
    return {
        "volume": round(float(match.group(1)) * 100) if match else 0,
        "muted": "[MUTED]" in text,
    }


def audio_state():
    if mock_enabled():
        return mock.state["audio"]
    return parse_wpctl_volume(run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]))


def audio_set(volume=None, muted=None):
    if mock_enabled():
        if volume is not None:
            mock.state["audio"]["volume"] = int(volume)
        if muted is not None:
            mock.state["audio"]["muted"] = bool(muted)
        return audio_state()
    if volume is not None:
        level = max(0, min(100, int(volume))) / 100
        run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{level:.2f}"])
    if muted is not None:
        run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if muted else "0"])
    return audio_state()


def brightness_state():
    if mock_enabled():
        return mock.state["brightness"]
    out = run(["brightnessctl", "-m", "info"])
    # device,class,current,percent,max
    parts = out.strip().split(",")
    if len(parts) >= 4 and parts[3].endswith("%"):
        return {"available": True, "level": int(parts[3].rstrip("%"))}
    return {"available": False, "level": 100}


def brightness_set(level):
    if mock_enabled():
        mock.state["brightness"]["level"] = int(level)
        return brightness_state()
    run(["brightnessctl", "set", f"{max(5, min(100, int(level)))}%"])
    return brightness_state()


def battery_state(root="/sys/class/power_supply"):
    if mock_enabled():
        return mock.state["battery"]
    for bat in sorted(glob.glob(os.path.join(root, "BAT*"))):
        try:
            with open(os.path.join(bat, "capacity")) as f:
                level = int(f.read().strip())
            with open(os.path.join(bat, "status")) as f:
                status = f.read().strip()
        except (OSError, ValueError):
            continue
        return {"present": True, "level": level, "charging": status in ("Charging", "Full")}
    return {"present": False, "level": 100, "charging": False}


def airplane_set(on):
    if mock_enabled():
        mock.state["airplane"] = bool(on)
        mock.state["wifi"]["enabled"] = not on
        mock.state["bluetooth"]["enabled"] = not on
    else:
        run(["nmcli", "radio", "all", "off" if on else "on"])
        run(["bluetoothctl", "power", "off" if on else "on"])
    return quick_settings()


def quick_settings():
    wifi = wifi_state()
    bt = bluetooth_state()
    return {
        "wifi": wifi,
        "bluetooth": bt,
        "audio": audio_state(),
        "brightness": brightness_state(),
        "battery": battery_state(),
        "airplane": mock.state["airplane"] if mock_enabled() else (not wifi["enabled"] and not bt["enabled"]),
    }


# --- Power -----------------------------------------------------------------

POWER_ACTIONS = {
    "suspend": ["systemctl", "suspend"],
    "reboot": ["systemctl", "reboot"],
    "poweroff": ["systemctl", "poweroff"],
}


def power(action):
    if action == "signout":
        if not mock_enabled():
            session = os.environ.get("XDG_SESSION_ID")
            run(["loginctl", "terminate-session", session] if session else ["loginctl", "terminate-user", os.environ.get("USER", "")])
        return {"ok": True}
    if action not in POWER_ACTIONS:
        raise ApiError(f"Unknown power action {action}")
    if not mock_enabled():
        run(POWER_ACTIONS[action])
    return {"ok": True}
