# Lumen OS: architecture and roadmap

Lumen is an Arch-based distro that boots straight into a console-style,
fullscreen shell. It is driven by a controller first, with mouse and keyboard
working everywhere. The look takes the Xbox 360 "blade" dashboard and makes it
modern: dark glass panels that slide in from the edges, one accent colour, big
tiles, no desktop and no windows.

## How the pieces fit

```
 power on
   │
   ▼
 systemd ──► greetd ──► lumen-greeter (cage + Chromium kiosk)
                         │  PS5-style user tiles, PIN/password
                         │  talks to greetd over $GREETD_SOCK via lumend
                         ▼
               lumen-session (per user)
                 gamescope  ─┬─ Chromium kiosk  → shell UI (HTML/JS)
                             └─ games / apps launched by lumend
                                         ▲
                                         │ HTTP/JSON on 127.0.0.1
                                         ▼
                                lumend (Python daemon, per user)
                     ┌───────────┬───────────┬───────────┬───────────┐
                   system      library     store       accounts
                 nmcli,       Steam,      Flathub +   Steam / Epic
                 bluetoothctl Epic, GOG,  Snap APIs,  (legendary) /
                 wpctl, sysfs .desktop    flatpak/    GOG (gogdl)
                 systemctl    apps        snap CLI
```

* **iso/** is an archiso overlay. `iso/build.sh` copies the stock `releng`
  profile, layers our files on top, builds the AUR packages we need into a
  local repo, and runs `mkarchiso`.
* **session/** holds the scripts that start the greeter and the user session.
  gamescope is the compositor (same as SteamOS), so games get its scaling,
  frame limiting and VRR for free.
* **shell/lumend/** is the backend. It is plain Python 3 standard library so
  it runs on a fresh install with no pip step. Every OS action the UI can take
  goes through one small JSON API. `LUMEN_MOCK=1` serves fake data, which is
  how the UI is developed in an ordinary browser.
* **shell/ui/** is the front end: static HTML, CSS and ES modules, no build
  step. A single focus engine handles D-pad, stick, keyboard and mouse.

## Layout rules (no duplicate features)

Every feature has exactly one home.

| Place | What lives there |
| --- | --- |
| Top bar, left ("you") | Avatar and name (switch user, sign out), status icons for **Wi-Fi, Bluetooth, volume, battery** that open Quick Settings, and the Settings gear |
| Top bar, right ("fun") | Music player, screenshot Album, Achievements/stats, Themes, Notifications, clock |
| Home | The 15 most recent games and apps, then one "All software" tile that opens the Library |
| Bottom dock | Library, Store, Power |
| Library | Every game and app, filters per source, and **Accounts** (connect Steam, Epic, GOG) |
| Store | Flathub and Snap apps in one catalogue |
| Settings | Everything that is not used daily (display, storage, users, updates, about) |

Quick Settings is the one place for Wi-Fi, Bluetooth, volume, brightness and
airplane mode. Settings links to it instead of repeating those controls.

## Games from other launchers

* **Steam** runs its own client and Proton. Lumen reads installed games from
  `steamapps/appmanifest_*.acf` and hands launch and install to
  `steam -silent steam://rungameid/<id>` and `steam://install/<id>`. lumend
  sets Steam Play's default compat tool (`CompatToolMapping` "0" in
  `config/config.vdf`) to Proton Experimental while Steam is closed, and
  writes per-game Proton choices to the same table, closing Steam first
  because it rewrites that file on exit. Custom Protons are read from
  `compatibilitytools.d`.
* **Epic** uses `legendary`, **GOG** uses `gogdl`. Both list the owned
  library, download into `~/Games/<store>/`, and launch through `umu-run`
  with GE-Proton. Each game gets its own prefix in `~/Games/Prefixes/`.
  Wine is also installed for the rare title that runs better outside Proton.

## Quick Resume

lumend tracks every game and app it starts (`shell/lumend/resume.py`). Each
one is known by its process session (lumend starts it with
`start_new_session`), or for Steam games by Steam's `reaper ... AppId=<id>`
wrapper and everything below it.

* **Going Home.** lumend reads the controllers' evdev devices itself
  (`shell/lumend/pads.py`) because the shell's Chromium window doesn't get
  input while a game has focus. A Guide press pauses the game on screen
  (SIGSTOP on its whole process tree) and brings the shell back. While a game
  is on screen the shell ignores the controller.
* **What's on screen.** gamescope lists its windows with their pids in
  `GAMESCOPE_FOCUSABLE_WINDOWS` and shows the one named in
  `GAMESCOPECTRL_BASELAYER_WINDOW`. lumend sets that with `xprop`
  (`shell/lumend/gamescope.py`), and keeps it on the game's newest window
  while the game is up. lumen-ui writes gamescope's `DISPLAY` to
  `$XDG_RUNTIME_DIR/lumen/display.env`, since lumend starts before gamescope.
* **Resuming** sends SIGCONT and shows the game's window again. Three games
  stay paused at most; the one paused longest ago is closed to make room.
  Sleep pauses the game on screen first. Apps are tracked but never paused.

## Game art

Every game shows real cover art, and on Home and in the Library the
background changes to the focused game's artwork. Apps keep the normal
background. Steam games use their own Steam images. Epic, GOG and desktop
games are matched to Steam by title in the background (`shell/lumend/art.py`),
with the store's own images and then a generated cover as fallbacks. lumend
downloads each image once into `~/.cache/lumen/art`, so art keeps working
offline.

## Store

The Store searches Flathub (`flathub.org/api/v2`) and the Snap Store
(`api.snapcraft.io/v2`) at the same time and merges results into one list.
When an app exists in both, it shows once, and Flatpak is preferred because it
needs no extra daemon. The app page shows the icon, summary, description,
screenshots and which source it will install from.

## Milestones

1. **Boot to shell.** archiso overlay, gamescope session, lumend skeleton,
   Home with 15 recents, top bar, Quick Settings (Wi-Fi, Bluetooth, volume,
   battery, power), controller navigation.
2. **Login.** greetd greeter with PS5-style user tiles, avatars, optional PIN,
   new-user flow.
3. **Library and accounts.** Switch-style library grid, Steam/Epic/GOG account
   connection, install and launch through umu/Proton, regular desktop apps.
4. **Store.** Flathub + Snap search, app pages, install/remove, progress.
5. **Polish.** gamescope focus handling for launched apps, on-screen keyboard,
   screenshots and music widgets, theming, update channel, installer.
