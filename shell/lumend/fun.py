"""The "fun" side of the top bar: music, screenshot album, theme."""

import os
from pathlib import Path

from . import mock
from .util import ApiError, data_dir, load_json, mock_enabled, run, save_json

ACCENTS = {
    "Mint": "#3ee6a0", "Azure": "#4da3ff", "Rose": "#ff6b8b",
    "Amber": "#ffb547", "Violet": "#b48cff", "Ice": "#36d6e7",
}
WALLPAPERS = ["aurora", "nebula", "grid", "dusk"]


def album_dirs():
    pics = Path(os.environ.get("XDG_PICTURES_DIR") or os.path.expanduser("~/Pictures"))
    return [pics / "Screenshots", Path("/tmp")]


def album():
    if mock_enabled():
        return {"shots": [
            {"path": f"/api/mock-art/shot:{t}.svg?shape=hero", "title": t}
            for t in ("Hades", "Celeste", "Cyberpunk 2077", "Elden Ring", "Hollow Knight", "Valheim")
        ]}
    shots = []
    for d in album_dirs():
        if not d.is_dir():
            continue
        pattern = "gamescope_*.png" if str(d) == "/tmp" else "*.png"
        shots += sorted(d.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"shots": [{"path": f"/api/shot?path={p}", "title": p.stem} for p in shots[:60]]}


def album_allowed(path):
    p = Path(path).resolve()
    return p.suffix == ".png" and any(
        p.is_relative_to(d.resolve()) for d in album_dirs() if d.exists())


def media():
    if mock_enabled():
        return mock.state["media"]
    fmt = "{{status}}\t{{title}}\t{{artist}}\t{{playerName}}"
    out = run(["playerctl", "metadata", "--format", fmt]).strip()
    if not out:
        return {"available": False}
    status, title, artist, player = (out.split("\t") + ["", "", "", ""])[:4]
    return {"available": True, "playing": status == "Playing", "title": title,
            "artist": artist, "player": player}


def media_action(action):
    if action not in ("play-pause", "next", "previous"):
        raise ApiError("Unknown media action.")
    if mock_enabled():
        if action == "play-pause":
            mock.state["media"]["playing"] = not mock.state["media"]["playing"]
        return media()
    run(["playerctl", action])
    return media()


def _settings_path():
    return data_dir() / "settings.json"


def settings():
    s = load_json(_settings_path(), {})
    return {
        "accent": s.get("accent", ACCENTS["Mint"]),
        "wallpaper": s.get("wallpaper", "aurora"),
        "accents": ACCENTS,
        "wallpapers": WALLPAPERS,
    }


def update_settings(payload):
    s = load_json(_settings_path(), {})
    if payload.get("accent") in ACCENTS.values():
        s["accent"] = payload["accent"]
    if payload.get("wallpaper") in WALLPAPERS:
        s["wallpaper"] = payload["wallpaper"]
    save_json(_settings_path(), s)
    return settings()
