"""Run Windows games from Epic and GOG with Proton (through umu) or Wine."""

import os
import re
import shutil

from ..util import games_dir


def prefix_for(store, game_id):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(game_id))
    path = games_dir() / "Prefixes" / f"{store}-{safe}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def env_for(store, game_id):
    """Environment for umu-run: per-game prefix and the latest GE-Proton.

    umu downloads GE-Proton on first use when PROTONPATH=GE-Proton, so every
    Epic/GOG install comes with a working Proton without a separate step.
    STORE lets umu-protonfixes apply the right per-game fixes.
    """
    return {
        **os.environ,
        "WINEPREFIX": str(prefix_for(store, game_id)),
        "GAMEID": f"umu-{game_id}" if store == "egs" else f"umu-gog-{game_id}",
        "STORE": store,
        "PROTONPATH": os.environ.get("LUMEN_PROTON", "GE-Proton"),
    }


def runner():
    """The wrapper command placed before a game's .exe."""
    if shutil.which("umu-run"):
        return ["umu-run"]
    if shutil.which("wine"):
        return ["wine"]
    return None


def prepare_prefix_cmd():
    """Command that creates the Wine prefix and fetches Proton ahead of play."""
    if shutil.which("umu-run"):
        return ["umu-run", ""]
    if shutil.which("wineboot"):
        return ["wineboot", "--init"]
    return None
