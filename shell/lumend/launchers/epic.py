"""Epic Games Store through legendary, run with Proton via umu."""

import json
import os
import subprocess
import time

from .. import jobs
from ..util import ApiError, data_dir, games_dir, have, load_json, run, save_json
from . import proton
from .base import Launcher


def _image(meta, *kinds):
    for kind in kinds:
        for img in (meta or {}).get("keyImages", []):
            if img.get("type") == kind and img.get("url"):
                return img["url"]
    return None


class Epic(Launcher):
    id = "epic"
    name = "Epic Games"
    login = {
        "type": "code",
        "url": "https://legendary.gl/epiclogin",
        "help": "Sign in to Epic on the page that opens. It then shows a block of text "
                "with \"authorizationCode\". Enter that code here.",
    }

    def available(self):
        return have("legendary")

    def status(self):
        if not self.available():
            return {"connected": False, "user": None}
        try:
            data = json.loads(run(["legendary", "status", "--json", "--offline"], timeout=20) or "{}")
        except ValueError:
            data = {}
        account = data.get("account")
        connected = bool(account) and not account.startswith("<")
        return {"connected": connected, "user": account if connected else None}

    def connect(self, payload):
        code = (payload.get("code") or "").strip().strip('"')
        if not code:
            raise ApiError("Enter the authorization code from the Epic page.")
        try:
            run(["legendary", "auth", "--code", code], timeout=60, check=True)
        except RuntimeError as exc:
            raise ApiError(f"Epic sign-in failed: {exc}") from exc
        self._cache_path().unlink(missing_ok=True)
        return self.describe()

    def disconnect(self):
        run(["legendary", "auth", "--delete"], timeout=20)
        self._cache_path().unlink(missing_ok=True)
        return self.describe()

    def _cache_path(self):
        return data_dir() / "epic-library.json"

    def _owned(self):
        cache = load_json(self._cache_path(), {})
        if cache.get("time", 0) > time.time() - 1800:
            return cache["games"]
        try:
            games = json.loads(run(["legendary", "list", "--json"], timeout=120) or "[]")
        except ValueError:
            games = []
        if games:
            save_json(self._cache_path(), {"time": time.time(), "games": games})
            return games
        return cache.get("games", [])

    def _installed(self):
        try:
            return {g["app_name"]: g for g in json.loads(
                run(["legendary", "list-installed", "--json"], timeout=30) or "[]")}
        except ValueError:
            return {}

    def games(self):
        if not self.available() or not self.status()["connected"]:
            return []
        installed = self._installed()
        out = []
        for g in self._owned():
            meta = g.get("metadata", {})
            # DLC and add-ons show up as their own entries; skip them.
            if meta.get("mainGameItem") or g.get("is_dlc"):
                continue
            app = g["app_name"]
            out.append({
                "id": f"epic:{app}",
                "title": g.get("app_title") or meta.get("title") or app,
                "source": "epic",
                "kind": "game",
                "installed": app in installed,
                "last_played": None,
                "art": {
                    "cover": _image(meta, "DieselGameBoxTall", "OfferImageTall"),
                    "hero": _image(meta, "DieselGameBox", "OfferImageWide"),
                    "icon": _image(meta, "Thumbnail", "DieselGameBoxLogo"),
                },
            })
        return out

    def install(self, game_id):
        if not self.available():
            raise ApiError("legendary isn't installed.")
        base = games_dir() / "Epic"
        base.mkdir(parents=True, exist_ok=True)
        cmd = ["legendary", "install", game_id, "-y", "--base-path", str(base), "--platform", "Windows"]
        return jobs.start(f"Installing {game_id}", cmd, item_id=f"epic:{game_id}",
                          on_done=lambda job: self._after_install(job, game_id))

    def _after_install(self, job, game_id):
        # Make the Proton prefix (and fetch GE-Proton) now, not at first launch.
        prep = proton.prepare_prefix_cmd()
        if job["state"] == "done" and prep:
            jobs.start("Setting up Proton", prep, env=proton.env_for("egs", game_id),
                       item_id=f"epic:{game_id}")

    def uninstall(self, game_id):
        run(["legendary", "uninstall", game_id, "-y"], timeout=300)

    def launch(self, game_id):
        wrapper = proton.runner()
        if wrapper is None:
            raise ApiError("Neither umu-launcher nor Wine is installed.")
        cmd = ["legendary", "launch", game_id, "--no-wine", "--wrapper", " ".join(wrapper)]
        return subprocess.Popen(cmd, env=proton.env_for("egs", game_id), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=os.path.expanduser("~"))
