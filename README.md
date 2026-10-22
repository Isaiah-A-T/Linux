# Lumen OS

An Arch-based Linux distro that boots straight into a console-style shell.
Think of the Xbox 360 blades, rebuilt for today: dark glass panels that slide
in from the edges, big tiles, one accent colour, and no desktop. It works with
a controller, a mouse, or a keyboard.

* **Home** shows your 15 most recent games and apps. Everything else is one
  press away in the Switch-style **Library**.
* **Library** brings Steam, Epic Games and GOG together with your regular
  apps. Connect accounts under Library › Accounts. Epic and GOG games download
  and run with GE-Proton through umu, each in its own Wine prefix. Steam games
  use Steam's own Proton.
* **Store** searches Flathub and the Snap Store at once and shows each app
  once, with its description and screenshots.
* **Top bar.** The left side is you: account, Quick Settings (Wi-Fi, Bluetooth,
  sound, brightness, battery) and Settings. The right side is for fun: music,
  screenshot album, themes and notifications.
* **Sign-in** is a PS5-style user picker running on greetd.
* Under the hood it runs on gamescope, like SteamOS.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the architecture and milestones.

## Try the shell in a browser

```sh
make dev        # serves fake data on http://127.0.0.1:7777/
```

Open `http://127.0.0.1:7777/` for the shell and
`http://127.0.0.1:7777/?mode=greeter` for the sign-in screen. Arrow keys move,
Enter selects, Esc goes back, F1 opens Quick Settings, `[` and `]` switch tabs.
A connected controller works too.

## Build the ISO

On an Arch Linux machine with `archiso`, `base-devel` and `git` installed:

```sh
sudo ./iso/build.sh          # the ISO lands in ./out
```

## Layout

| Path | What it is |
| --- | --- |
| `iso/` | archiso overlay, package lists and local PKGBUILDs |
| `session/` | greeter and session start scripts, systemd user unit, polkit rule |
| `shell/lumend/` | Python daemon (standard library only) with the JSON API |
| `shell/ui/` | The shell UI: HTML, CSS and ES modules, no build step |
| `installer/` | The first-start installer (built in its own branch) |
| `tests/` | `make test` |
