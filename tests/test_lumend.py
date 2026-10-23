import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("XDG_DATA_HOME", tempfile.mkdtemp())

from lumend import art, capture, fun, gamescope, jobs, pads, recents, resume, saves, store, system, update  # noqa: E402
from lumend.launchers import gog, steam, vdf  # noqa: E402


class VdfTest(unittest.TestCase):
    def test_nested_and_escapes(self):
        text = '''
        // comment
        "libraryfolders"
        {
            "0" { "path" "/home/p/.local/share/Steam" "apps" { "620" "123" } }
            "1" { "path" "/mnt/games/Steam\\\\Lib" }
        }'''
        data = vdf.loads(text)["libraryfolders"]
        self.assertEqual(data["0"]["apps"]["620"], "123")
        self.assertEqual(data["1"]["path"], "/mnt/games/Steam\\Lib")


class SteamTest(unittest.TestCase):
    def test_installed_games_skips_tools_and_reads_progress(self):
        with tempfile.TemporaryDirectory() as d:
            apps = Path(d) / "steamapps"
            apps.mkdir()
            (apps / "appmanifest_620.acf").write_text(
                '"AppState" { "appid" "620" "name" "Portal 2" "StateFlags" "4" "LastPlayed" "100" }')
            (apps / "appmanifest_1493710.acf").write_text(
                '"AppState" { "appid" "1493710" "name" "Proton Experimental" "StateFlags" "4" }')
            (apps / "appmanifest_570.acf").write_text(
                '"AppState" { "appid" "570" "name" "Dota 2" "StateFlags" "1026" '
                '"BytesToDownload" "200" "BytesDownloaded" "50" }')
            games = steam.installed_games(Path(d))
        self.assertEqual(set(games), {"620", "570"})
        self.assertTrue(games["620"]["installed"])
        self.assertEqual(games["620"]["last_played"], 100)
        self.assertFalse(games["570"]["installed"])
        self.assertEqual(games["570"]["progress"], 25.0)


class SteamPlayTest(unittest.TestCase):
    CONFIG = ('"InstallConfigStore" { "Software" { "valve" { "Steam" { "AutoUpdateWindowEnabled" "0" '
              '"CompatToolMapping" { "620" { "name" "proton_9" "config" "" "priority" "250" } } } } } }')

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "config.vdf").write_text(self.CONFIG)
        tool = self.root / "compatibilitytools.d" / "GE-Proton10-4"
        tool.mkdir(parents=True)
        (tool / "compatibilitytool.vdf").write_text(
            '"compatibilitytools" { "compat_tools" { "GE-Proton10-4" { "display_name" "GE-Proton 10-4" } } }')
        patches = [mock.patch.object(steam, "running", return_value=False),
                   mock.patch.object(steam, "steam_root", return_value=self.root),
                   mock.patch.object(steam, "ratings", return_value={"protondb": "gold", "deck": "verified"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.dir.cleanup()

    def mapping(self):
        cfg = vdf.load(self.root / "config" / "config.vdf")
        return cfg["InstallConfigStore"]["Software"]["valve"]["Steam"]

    def test_dumps_round_trips(self):
        data = {"a": {"b": 'say "hi"', "c": {"d": "C:\\Games"}}}
        self.assertEqual(vdf.loads(vdf.dumps(data)), data)

    def test_enables_proton_for_all_titles_once_and_keeps_other_settings(self):
        self.assertTrue(steam.enable_steam_play(self.root))
        node = self.mapping()
        self.assertEqual(node["CompatToolMapping"]["0"]["name"], "proton_experimental")
        self.assertEqual(node["CompatToolMapping"]["620"]["name"], "proton_9")
        self.assertEqual(node["AutoUpdateWindowEnabled"], "0")
        self.assertTrue((self.root / "config" / "config.vdf.lumen-bak").exists())
        self.assertFalse(steam.enable_steam_play(self.root))

    def test_leaves_config_alone_while_steam_runs(self):
        with mock.patch.object(steam, "running", return_value=True):
            self.assertFalse(steam.enable_steam_play(self.root))
        self.assertNotIn("0", self.mapping()["CompatToolMapping"])

    def test_pick_and_clear_proton_per_game(self):
        s = steam.Steam()
        info = s.compat("620")
        self.assertEqual(info["tool"], "proton_9")
        self.assertIn({"id": "GE-Proton10-4", "name": "GE-Proton 10-4"}, info["tools"])
        self.assertEqual(s.set_compat("1145360", "GE-Proton10-4")["tool"], "GE-Proton10-4")
        self.assertEqual(self.mapping()["CompatToolMapping"]["1145360"]["priority"], "250")
        self.assertEqual(s.set_compat("620", "")["tool"], "")
        self.assertNotIn("620", self.mapping()["CompatToolMapping"])
        with self.assertRaises(steam.ApiError):
            s.set_compat("620", "made-up-proton")


class GogTest(unittest.TestCase):
    def test_extract_code(self):
        url = "https://embed.gog.com/on_login_success?origin=client&code=abc123"
        self.assertEqual(gog.extract_code(url), "abc123")
        self.assertEqual(gog.extract_code("  xyz "), "xyz")

    def test_primary_task(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "goggame-42.info").write_text(json.dumps({"playTasks": [
                {"type": "URLTask", "link": "x"},
                {"type": "FileTask", "path": "bin\\Game.exe", "isPrimary": True},
            ]}))
            self.assertEqual(gog.primary_task(d, "42")["path"], "bin\\Game.exe")


class WifiTest(unittest.TestCase):
    def test_parse_wifi_list_dedupes_and_unescapes(self):
        out = "\n".join([
            " :Cafe\\:Guest:40:WPA2",
            "*:Home:70:WPA2",
            " :Home:90:WPA2",
            " ::80:WPA2",
            " :Open Net:55:",
        ])
        nets = system.parse_wifi_list(out)
        self.assertEqual([n["ssid"] for n in nets], ["Home", "Open Net", "Cafe:Guest"])
        self.assertTrue(nets[0]["connected"])
        self.assertFalse(nets[1]["secure"])

    def test_parse_volume(self):
        self.assertEqual(system.parse_wpctl_volume("Volume: 0.45 [MUTED]"), {"volume": 45, "muted": True})


class StoreTest(unittest.TestCase):
    def test_merge_prefers_flatpak_and_records_alternative(self):
        flat = [{"source": "flatpak", "id": "org.videolan.VLC", "title": "VLC"}]
        snap = [{"source": "snap", "id": "vlc", "title": "vlc"},
                {"source": "snap", "id": "code", "title": "Visual Studio Code"}]
        merged = store.merge(flat, snap)
        self.assertEqual([c["id"] for c in merged], ["org.videolan.VLC", "code"])
        self.assertEqual(merged[0]["also"], [{"source": "snap", "id": "vlc"}])

    def test_strip_html(self):
        self.assertEqual(store.strip_html("<p>Hi &amp; bye</p><ul><li>One</li></ul>"), "Hi & bye\n• One")

    def test_install_rejects_bad_ids(self):
        with self.assertRaises(Exception):
            store.install("flatpak", "foo; rm -rf /")


class UpdateTest(unittest.TestCase):
    def test_parse_pending(self):
        text = "linux 6.17.3.arch1-1 -> 6.17.5.arch1-1\nsteam 1.0.0.83-1 -> 1.0.0.84-1 [ignored]\n:: junk\n"
        pending = update.parse_pending(text)
        self.assertEqual([p["name"] for p in pending], ["linux", "steam"])
        self.assertEqual(pending[0]["new"], "6.17.5.arch1-1")
        self.assertTrue(pending[1]["ignored"])

    def test_pacman_progress_counts_install_lines_only(self):
        self.assertEqual(update.parse_pacman_progress("(10/40) upgrading mesa"), 0.25)
        self.assertEqual(update.parse_pacman_progress("( 3/12) installing lumen"), 0.25)
        self.assertIsNone(update.parse_pacman_progress("(10/40) checking keys in keyring"))
        self.assertIsNone(update.parse_pacman_progress(":: Starting full system upgrade..."))

    def test_last_upgrade_reads_the_latest_entry(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write("[2026-10-01T10:00:00+0000] [PACMAN] starting full system upgrade\n"
                    "[2026-10-01T10:05:00+0000] [ALPM] upgraded mesa (1 -> 2)\n"
                    "[2026-10-20T08:30:00+0000] [PACMAN] starting full system upgrade\n")
        try:
            self.assertEqual(update.last_upgrade(f.name), 1792485000.0)
        finally:
            os.unlink(f.name)
        self.assertIsNone(update.last_upgrade("/nonexistent/pacman.log"))

    def test_steps_run_in_order_and_failures_do_not_stop_later_steps(self):
        steps = [
            ("one", ["sh", "-c", "echo '(1/2) upgrading a'; echo '(2/2) upgrading b'"], 3, update.parse_pacman_progress),
            ("two", ["sh", "-c", "echo 50%; exit 3"], 1, jobs.percent),
            ("three", ["true"], 1, None),
        ]
        seen = {}
        job = jobs.start_steps("t", steps, on_done=lambda j: seen.update(state=j["state"]))
        for _ in range(100):
            current = next(j for j in jobs.all_jobs() if j["id"] == job["id"])
            if current["state"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual(current["state"], "failed")
        self.assertEqual(current["codes"], [0, 3, 0])
        self.assertEqual(current["message"], "two failed")
        self.assertEqual(current["progress"], 100.0)
        self.assertEqual(seen["state"], "running")  # the hook runs before the job finishes


class AutoUpdateTest(unittest.TestCase):
    def test_parse_auto_status(self):
        st = update.parse_auto_status("state=waiting\ntime=1792485000\ncount=12\n"
                                      "message=Will install after you finish playing\n")
        self.assertEqual(st["state"], "waiting")
        self.assertEqual(st["time"], 1792485000)
        self.assertEqual(st["count"], 12)
        self.assertEqual(st["message"], "Will install after you finish playing")
        self.assertEqual(update.parse_auto_status("count=x")["count"], 0)

    def test_auto_mode_defaults_to_install(self):
        self.assertEqual(update.auto_mode("/nonexistent/update.conf"), "install")
        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
            f.write('LUMEN_REPO_URL=https://example.com\nAUTO_UPDATE="download"\n')
        try:
            self.assertEqual(update.auto_mode(f.name), "download")
        finally:
            os.unlink(f.name)

    def test_local_version_does_not_match_longer_names(self):
        with tempfile.TemporaryDirectory() as d:
            for entry in ("lumen-0.1.0.r20261022.163000-1", "lumen-ps5-ntsync-1-1", "linux-ps5-6.15.4-1"):
                os.mkdir(os.path.join(d, entry))
            with mock.patch.object(update, "PACMAN_LOCAL", d):
                self.assertEqual(update._local_version("lumen"), "0.1.0.r20261022.163000-1")
                self.assertEqual(update._local_version("linux-ps5"), "6.15.4-1")
                self.assertIsNone(update._local_version("linux"))
                self.assertTrue(update.is_ps5())

    def test_a_busy_state_without_the_lock_is_stale(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("state=installing\ntime=1\ncount=3\nmessage=\n")
        try:
            with mock.patch.object(update, "AUTO_STATUS", f.name), \
                    mock.patch.object(update, "LOCK", "/nonexistent/lock"), \
                    mock.patch.object(update, "AUTO_CONF", "/nonexistent/update.conf"):
                st = update.auto_status()
        finally:
            os.unlink(f.name)
        self.assertFalse(st["running"])
        self.assertEqual(st["state"], "")
        self.assertEqual(st["mode"], "install")

    def test_held_lock_means_running(self):
        import fcntl
        with tempfile.NamedTemporaryFile("w", delete=False) as lock, \
                tempfile.NamedTemporaryFile("w", delete=False) as status:
            status.write("state=downloading\ntime=1\ncount=3\nmessage=\n")
        holder = open(lock.name, "w")
        fcntl.flock(holder, fcntl.LOCK_EX)
        try:
            with mock.patch.object(update, "AUTO_STATUS", status.name), \
                    mock.patch.object(update, "LOCK", lock.name), \
                    mock.patch.object(update, "reboot_needed", lambda: False):
                self.assertTrue(update.auto_status()["running"])
                bg = update.background_jobs()
        finally:
            holder.close()
            os.unlink(lock.name)
            os.unlink(status.name)
        self.assertEqual(len(bg), 1)
        self.assertEqual(bg[0]["state"], "running")
        self.assertEqual(bg[0]["message"], "Downloading 3 updates")


class RecentsTest(unittest.TestCase):
    def test_home_is_capped_at_15_and_ordered(self):
        now = time.time()
        items = [{"id": f"steam:{i}", "title": str(i), "installed": True, "last_played": now - i}
                 for i in range(30)]
        with mock.patch.object(recents, "load", return_value=[{"id": "steam:29", "last_played": now + 5}]):
            home = recents.home_items(items)
        self.assertEqual(len(home), recents.HOME_LIMIT)
        self.assertEqual(home[0]["id"], "steam:29")
        self.assertEqual(home[1]["id"], "steam:0")

    def test_uninstalled_items_stay_off_home(self):
        items = [{"id": "a", "installed": False, "last_played": 10}, {"id": "b", "installed": True, "last_played": 5}]
        with mock.patch.object(recents, "load", return_value=[{"id": "a", "last_played": 20}]):
            self.assertEqual([i["id"] for i in recents.home_items(items)], ["b"])


class QuickResumeTest(unittest.TestCase):
    def setUp(self):
        resume._entries.clear()
        resume._front["id"] = None
        self.sent = []
        # pid: (ppid, sid, state). 100 is a game whose wineserver (102)
        # left the tree but kept the session; 200 is Steam's reaper for 620.
        self.procs = {100: (1, 100, "S"), 101: (100, 100, "S"), 102: (1, 100, "S"), 103: (101, 100, "Z"),
                      200: (50, 50, "S"), 201: (200, 50, "S"), 300: (1, 300, "S"), 400: (1, 400, "S"),
                      500: (1, 500, "S")}
        patches = [
            mock.patch.object(resume, "processes", lambda: self.procs),
            mock.patch.object(resume, "_cmdline", lambda pid: [b"/x/reaper", b"SteamLaunch", b"AppId=620"] if pid == 200 else []),
            mock.patch.object(resume.os, "kill", lambda pid, sig: self.sent.append((pid, sig))),
            mock.patch.object(resume.threading, "Thread", mock.MagicMock()),
            mock.patch.object(resume, "gamescope", mock.MagicMock()),
            mock.patch.dict(os.environ, {"LUMEN_MOCK": "0"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def game(self, item_id, pid, source="epic"):
        item = {"id": item_id, "title": item_id, "kind": "game", "source": source, "art": {}}
        return resume.started(item, mock.Mock(pid=pid) if pid else None)

    def test_members_follow_session_and_tree_and_skip_zombies(self):
        self.assertEqual(resume.members({"pid": 100, "sid": 100}, self.procs), {100, 101, 102})

    def test_steam_games_are_found_through_the_reaper(self):
        self.game("steam:620", None, source="steam")
        self.assertEqual(resume.members(resume.get("steam:620"), self.procs), {200, 201})

    def test_starting_another_game_pauses_the_one_on_screen(self):
        self.game("epic:a", 100)
        self.game("epic:b", 300)
        st = resume.status()
        self.assertEqual(st["front"], "epic:b")
        self.assertEqual({i["id"]: i["state"] for i in st["items"]}, {"epic:a": "paused", "epic:b": "running"})
        self.assertEqual(sorted(p for p, sig in self.sent if sig == resume.signal.SIGSTOP), [100, 101, 102])

    def test_resume_continues_the_game(self):
        self.game("epic:a", 100)
        resume.go_home()
        self.sent.clear()
        resume.resume("epic:a")
        self.assertEqual(resume.status()["front"], "epic:a")
        self.assertEqual(sorted(p for p, sig in self.sent if sig == resume.signal.SIGCONT), [100, 101, 102])

    def test_oldest_paused_game_is_closed_past_the_limit(self):
        for item_id, pid in (("epic:a", 100), ("epic:b", 300), ("epic:c", 400), ("epic:d", 500)):
            closed = self.game(item_id, pid)
        self.assertEqual(closed, ["epic:a"])
        self.assertIsNone(resume.get("epic:a"))
        self.assertEqual(len(resume.status()["items"]), resume.LIMIT)

    def test_game_started_after_cloud_saves_is_attached_late(self):
        self.game("epic:a", None)
        self.assertIsNotNone(resume.get("epic:a"))  # kept while saves download
        resume.go_home()
        resume.attach("epic:a", mock.Mock(pid=100))
        self.assertEqual(resume.members(resume.get("epic:a"), self.procs), {100, 101, 102})
        self.assertEqual(sorted(p for p, sig in self.sent if sig == resume.signal.SIGSTOP), [100, 101, 102])

    def test_games_that_quit_are_forgotten(self):
        self.game("epic:a", 300)
        del self.procs[300]
        self.assertEqual(resume.status(), {"front": None, "limit": resume.LIMIT, "items": []})

    def test_apps_keep_running_when_you_go_home(self):
        resume.started({"id": "app:x", "title": "X", "kind": "app", "source": "app"}, mock.Mock(pid=300))
        resume.go_home()
        self.assertEqual(resume.status()["items"][0]["state"], "running")
        self.assertEqual(self.sent, [])


class GuideTest(unittest.TestCase):
    def test_capability_bitmap(self):
        bits = 64 * 5
        guide = 1 << pads.BTN_MODE
        words = [f"{guide >> (64 * i) & (2 ** 64 - 1):x}" for i in reversed(range(bits // 64))]
        self.assertTrue(pads.has_guide(" ".join(words)))
        # A keyboard: plenty of keys, no gamepad buttons.
        self.assertFalse(pads.has_guide("fffffffffffffffe"))
        self.assertFalse(pads.has_guide("0"))

    def test_guide_fires_on_release_but_not_in_combinations(self):
        hits = []
        w = pads.GuideWatcher(lambda: hits.append(1))
        w.feed(3, pads.EV_KEY, pads.BTN_MODE, 1)
        w.feed(3, pads.EV_KEY, pads.BTN_MODE, 0)
        self.assertEqual(hits, [1])
        w.feed(3, pads.EV_KEY, pads.BTN_MODE, 1)
        w.feed(3, pads.EV_KEY, 0x134, 1)  # Y
        w.feed(3, pads.EV_KEY, pads.BTN_MODE, 0)
        self.assertEqual(hits, [1])

    def test_gamescope_window_list(self):
        text = "GAMESCOPE_FOCUSABLE_WINDOWS = 4194307, 769, 1200, 6291458, 0, 3400\n"
        self.assertEqual(gamescope.parse_windows(text), [(4194307, 769, 1200), (6291458, 0, 3400)])
        self.assertEqual(gamescope.parse_windows(""), [])


class GreetdTest(unittest.TestCase):
    """Run users.login against a fake greetd speaking the real wire format."""

    def _serve(self, script):
        import socket
        import struct
        import threading
        path = os.path.join(tempfile.mkdtemp(), "greetd.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        srv.listen(1)
        seen = []

        def run():
            conn, _ = srv.accept()
            for reply in script:
                size = struct.unpack("=I", conn.recv(4))[0]
                seen.append(json.loads(conn.recv(size)))
                body = json.dumps(reply).encode()
                conn.sendall(struct.pack("=I", len(body)) + body)
            conn.close()

        threading.Thread(target=run, daemon=True).start()
        return path, seen

    def test_password_login_starts_session(self):
        from lumend import users
        path, seen = self._serve([
            {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"},
            {"type": "success"},
            {"type": "success"},
        ])
        with mock.patch.dict(os.environ, {"GREETD_SOCK": path, "LUMEN_MOCK": "0"}):
            self.assertEqual(users.login("fenta", "hunter2"), {"ok": True})
        self.assertEqual(seen[0], {"type": "create_session", "username": "fenta"})
        self.assertEqual(seen[1]["response"], "hunter2")
        self.assertEqual(seen[2]["cmd"], ["lumen-session"])

    def test_wrong_password_cancels(self):
        from lumend import users
        from lumend.util import ApiError
        path, seen = self._serve([
            {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"},
            {"type": "error", "error_type": "auth_error", "description": "nope"},
            {"type": "success"},
        ])
        with mock.patch.dict(os.environ, {"GREETD_SOCK": path, "LUMEN_MOCK": "0"}):
            with self.assertRaises(ApiError):
                users.login("fenta", "bad")
        self.assertEqual(seen[-1], {"type": "cancel_session"})


class ArtTest(unittest.TestCase):
    def test_matches_store_titles_to_steam(self):
        results = [{"id": 11, "name": "Portal Knights"}, {"id": 870780, "name": "Control Ultimate Edition"},
                   {"id": 292030, "name": "The Witcher® 3: Wild Hunt"}]
        self.assertEqual(art.best_match("Control", results), "870780")
        self.assertEqual(art.best_match("The Witcher 3: Wild Hunt - Game of the Year Edition", results), "292030")
        self.assertIsNone(art.best_match("Portal", results))
        self.assertEqual(art.best_match("The Witcher 3", results), "292030")
        self.assertEqual(art.best_match("Disco Elysium", [{"id": 632470, "name": "Disco Elysium - The Final Cut"}]), "632470")
        self.assertIsNone(art.best_match("Portal", [{"id": 620, "name": "Portal 2"}]))

    def test_games_get_steam_art_and_apps_keep_icons(self):
        items = [
            {"id": "steam:620", "title": "Portal 2", "kind": "game", "art": {}},
            {"id": "gog:1", "title": "Frostpunk", "kind": "game",
             "art": {"cover": "https://images.gog-statics.com/a.jpg"}},
            {"id": "app:vlc", "title": "VLC", "kind": "app", "art": {"icon": "/api/icon?path=x"}},
        ]
        with mock.patch.object(art, "load_json", return_value={
                art.normalize("Frostpunk"): {"appid": "323190", "background": None, "time": time.time()}}):
            art.enrich(items, lookups=False)
        portal, frostpunk, vlc = items
        self.assertIn("620%2Flibrary_600x900", portal["art"]["cover"])
        self.assertIn("323190%2Flibrary_hero", frostpunk["art"]["hero"])
        self.assertIn("gog-statics", frostpunk["art"]["cover"])  # store art is the fallback
        self.assertIn("placeholder-art", frostpunk["art"]["cover"])
        self.assertEqual(vlc["art"], {"icon": "/api/icon?path=x"})

    def test_only_image_cdns_are_fetched(self):
        self.assertTrue(art.allowed("https://shared.steamstatic.com/x.jpg"))
        self.assertFalse(art.allowed("http://cdn.cloudflare.steamstatic.com/x.jpg"))
        self.assertFalse(art.allowed("https://evilsteamstatic.com/x.jpg"))
        self.assertFalse(art.allowed("https://127.0.0.1/x.jpg"))


class CaptureTest(unittest.TestCase):
    def watcher(self):
        fired = []
        w = capture.Watcher(lambda: None, lambda: None)
        w.fire = lambda fn: fired.append("shot" if fn is w.on_shot else "clip")
        return w, {"held": set(), "share_down": None}, fired

    def test_guide_combos(self):
        w, st, fired = self.watcher()
        w.handle(st, capture.BTN_MODE, 1)
        w.handle(st, capture.BTN_TR, 1)
        w.handle(st, capture.BTN_TR, 0)
        w.handle(st, capture.BTN_TL, 1)
        self.assertEqual(fired, ["shot", "clip"])

    def test_bumpers_alone_do_nothing(self):
        w, st, fired = self.watcher()
        w.handle(st, capture.BTN_TR, 1)
        w.handle(st, capture.BTN_TL, 1)
        self.assertEqual(fired, [])

    def test_share_tap_and_hold(self):
        w, st, fired = self.watcher()
        w.handle(st, capture.KEY_RECORD, 1)
        w.handle(st, capture.KEY_RECORD, 0)
        w.handle(st, capture.KEY_RECORD, 1)
        st["share_down"] -= capture.HOLD + 0.1
        w.handle(st, capture.KEY_RECORD, 0)
        self.assertEqual(fired, ["shot", "clip"])

    def test_album_serves_only_captures(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"XDG_PICTURES_DIR": d, "XDG_VIDEOS_DIR": d}):
                shots, clips = capture.shots_dir(), capture.clips_dir()
                shots.mkdir(parents=True)
                clips.mkdir(parents=True)
                self.assertTrue(fun.album_allowed(str(shots / "a.png")))
                self.assertTrue(fun.album_allowed(str(clips / "a.mp4")))
                self.assertFalse(fun.album_allowed(str(shots / "a.mp4")))
                self.assertFalse(fun.album_allowed(str(clips / "../../etc.png")))


class SavesTest(unittest.TestCase):
    def test_gog_locations_resolve_inside_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            game, prefix = Path(d) / "game", Path(d) / "pfx"
            game.mkdir()
            (prefix / "drive_c/users/steamuser").mkdir(parents=True)
            (game / "goggame-7.info").write_text(json.dumps({"clientId": "c1"}))
            config = {"content": {"Windows": {"cloudStorage": {"enabled": True, "locations": [
                {"name": "saves", "location": "<?SAVED_GAMES?>\\Studio\\Game"},
                {"name": "cfg", "location": "<?INSTALL?>/cfg"},
                {"name": "odd", "location": "<?SOMETHING_ELSE?>/x"},
            ]}}}}
            resp = mock.MagicMock()
            resp.__enter__.return_value = resp
            with mock.patch("urllib.request.urlopen", return_value=resp), \
                    mock.patch("json.load", return_value=config):
                locs = saves.gog_locations(game, "7", prefix)
        self.assertEqual(locs, [
            {"name": "saves", "path": f"{prefix}/drive_c/users/steamuser/Saved Games/Studio/Game"},
            {"name": "cfg", "path": f"{game}/cfg"},
        ])

    def test_prefix_idle_returns_when_nothing_runs_there(self):
        saves.wait_prefix_idle("/nonexistent/prefix", poll=0.01)

    def test_play_syncs_down_runs_then_up(self):
        order = []
        proc = mock.MagicMock()
        proc.wait.side_effect = lambda: order.append("exit")

        def start():
            order.append("start")
            return proc

        def sync(direction):
            order.append(direction)
            return True

        with mock.patch.object(saves, "wait_prefix_idle"):
            saves.play("epic:x", "X", "/p", start, sync)
            for t in threading.enumerate():
                if t.name == "saves:epic:x":
                    t.join(5)
        self.assertEqual(order, ["down", "start", "exit", "up"])
        self.assertTrue(saves.last_sync("epic:x")["ok"])


if __name__ == "__main__":
    unittest.main()
