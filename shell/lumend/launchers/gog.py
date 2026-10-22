"""GOG through gogdl (Heroic's downloader), run with Proton via umu."""

import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .. import jobs
from ..util import ApiError, data_dir, games_dir, have, load_json, run, save_json
from . import proton
from .base import Launcher

CLIENT_ID = "46899977096215655"
LOGIN_URL = (
    "https://auth.gog.com/auth?client_id=46899977096215655"
    "&redirect_uri=https%3A%2F%2Fembed.gog.com%2Fon_login_success%3Forigin%3Dclient"
    "&response_type=code&layout=client2"
)


def extract_code(text):
    """Accept either the bare code or the whole on_login_success URL."""
    text = (text or "").strip()
    if "code=" in text:
        query = urllib.parse.urlparse(text).query or text.split("?", 1)[-1]
        return urllib.parse.parse_qs(query).get("code", [""])[0]
    return text


def find_game_dir(base, game_id):
    for info in Path(base).glob(f"*/goggame-{game_id}.info"):
        return info.parent
    return None


def primary_task(game_dir, game_id):
    info = json.loads((Path(game_dir) / f"goggame-{game_id}.info").read_text())
    tasks = info.get("playTasks", [])
    for task in tasks:
        if task.get("isPrimary") and task.get("type") == "FileTask":
            return task
    for task in tasks:
        if task.get("type") == "FileTask":
            return task
    return None


class GOG(Launcher):
    id = "gog"
    name = "GOG"
    login = {
        "type": "code",
        "url": LOGIN_URL,
        "help": "Sign in to GOG on the page that opens. When it shows a blank page, "
                "copy the address (it contains code=...) and enter it here.",
    }

    def _auth(self):
        return str(data_dir() / "gog-auth.json")

    def _installed_path(self):
        return data_dir() / "gog-installed.json"

    def available(self):
        return have("gogdl")

    def _gogdl(self, *args, timeout=60, check=False):
        return run(["gogdl", "--auth-config-path", self._auth(), *args], timeout=timeout, check=check)

    def _token(self):
        # "auth" without a code refreshes and prints the stored credentials.
        try:
            creds = json.loads(self._gogdl("auth") or "{}")
        except ValueError:
            return None
        return creds.get("access_token")

    def _api(self, url):
        token = self._token()
        if not token:
            raise ApiError("GOG isn't connected.")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)

    def status(self):
        auth = load_json(self._auth(), {})
        creds = auth.get(CLIENT_ID)
        if not creds:
            return {"connected": False, "user": None}
        return {"connected": True, "user": load_json(data_dir() / "gog-user.json", {}).get("username")}

    def connect(self, payload):
        code = extract_code(payload.get("code"))
        if not code:
            raise ApiError("Enter the code (or the whole address) from the GOG page.")
        try:
            self._gogdl("auth", "--code", code, check=True)
        except RuntimeError as exc:
            raise ApiError(f"GOG sign-in failed: {exc}") from exc
        try:
            me = self._api("https://embed.gog.com/userData.json")
            save_json(data_dir() / "gog-user.json", {"username": me.get("username")})
        except (OSError, ValueError, ApiError):
            pass
        return self.describe()

    def disconnect(self):
        for p in (Path(self._auth()), data_dir() / "gog-user.json", data_dir() / "gog-library.json"):
            p.unlink(missing_ok=True)
        return self.describe()

    def _owned(self):
        cache = load_json(data_dir() / "gog-library.json", {})
        if cache.get("time", 0) > time.time() - 1800:
            return cache["games"]
        games, page, pages = [], 1, 1
        try:
            while page <= pages:
                data = self._api(f"https://embed.gog.com/account/getFilteredProducts?mediaType=1&page={page}")
                pages = data.get("totalPages", 1)
                for p in data.get("products", []):
                    image = p.get("image", "")
                    if image.startswith("//"):
                        image = "https:" + image
                    games.append({"id": str(p["id"]), "title": p.get("title", ""), "image": image})
                page += 1
        except (OSError, ValueError):
            return cache.get("games", [])
        save_json(data_dir() / "gog-library.json", {"time": time.time(), "games": games})
        return games

    def games(self):
        if not self.status()["connected"]:
            return []
        installed = load_json(self._installed_path(), {})
        out = []
        for g in self._owned():
            img = g["image"]
            out.append({
                "id": f"gog:{g['id']}",
                "title": g["title"],
                "source": "gog",
                "kind": "game",
                "installed": g["id"] in installed,
                "last_played": None,
                "art": {
                    # GOG image ids take a size suffix.
                    "cover": f"{img}_bg_crop_1366x655.jpg" if img else None,
                    "hero": f"{img}_bg_crop_1366x655.jpg" if img else None,
                    "icon": f"{img}_196.jpg" if img else None,
                },
            })
        return out

    def install(self, game_id):
        if not self.available():
            raise ApiError("gogdl isn't installed.")
        if not re.fullmatch(r"\d+", game_id):
            raise ApiError("Unknown GOG game.")
        base = games_dir() / "GOG"
        base.mkdir(parents=True, exist_ok=True)
        cmd = ["gogdl", "--auth-config-path", self._auth(), "download", game_id,
               "--platform", "windows", "--path", str(base)]
        return jobs.start(f"Installing {game_id}", cmd, item_id=f"gog:{game_id}",
                          on_done=lambda job: self._after_install(job, game_id, base))

    def _after_install(self, job, game_id, base):
        if job["state"] != "done":
            return
        game_dir = find_game_dir(base, game_id)
        if game_dir:
            installed = load_json(self._installed_path(), {})
            installed[game_id] = str(game_dir)
            save_json(self._installed_path(), installed)
        prep = proton.prepare_prefix_cmd()
        if prep:
            jobs.start("Setting up Proton", prep, env=proton.env_for("gog", game_id),
                       item_id=f"gog:{game_id}")

    def uninstall(self, game_id):
        installed = load_json(self._installed_path(), {})
        path = installed.pop(game_id, None)
        if path and Path(path).is_relative_to(games_dir()):
            subprocess.run(["rm", "-rf", "--", path], check=False)
        save_json(self._installed_path(), installed)

    def launch(self, game_id):
        game_dir = load_json(self._installed_path(), {}).get(game_id)
        if not game_dir:
            raise ApiError("This game isn't installed.")
        task = primary_task(game_dir, game_id)
        if not task:
            raise ApiError("Couldn't find how to start this game.")
        wrapper = proton.runner()
        if wrapper is None:
            raise ApiError("Neither umu-launcher nor Wine is installed.")
        exe = Path(game_dir) / task["path"].replace("\\", "/")
        cwd = Path(game_dir) / task.get("workingDir", "").replace("\\", "/")
        args = task.get("arguments", "").split() if task.get("arguments") else []
        subprocess.Popen([*wrapper, str(exe), *args], cwd=str(cwd), env=proton.env_for("gog", game_id),
                         start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
