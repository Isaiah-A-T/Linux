# Lumen OS Setup

The installer for the Lumen OS live ISO. It is [Calamares](https://calamares.io)
with a custom QML theme that looks and behaves like the console shell's first
start: the aurora backdrop, glass panels, blade-in page changes, the on-screen
keyboard and controller hints along the bottom.

## What the player sees

1. **Power-on screen** (`usr/share/lumen-installer/start.qml`). The Lumen mark
   and a greeting cycling through languages, then *Press A to begin*. It
   offers **Set up Lumen OS**, **Try it first** (the normal shell, with an
   *Install* entry in the dock) and **Turn off**.
2. **Setup** (Calamares, fullscreen): language, region and time zone, keyboard,
   disk, profile (avatar, name, password or PIN), summary, install with a tips
   slideshow, and finish.

Everything works with a controller:

| Pad | Does |
| --- | --- |
| A | select, type on the on-screen keyboard |
| B | back, close the keyboard |
| X / Y | delete / space on the keyboard |
| Menu | next step, keyboard done |
| View | previous step |
| LB / RB | shift / symbols on the keyboard, move between controls on the disk page |
| LT / RT | page up / down in long lists |
| Right stick, R3 | pointer and click (for the disk page) |

`lumen-padmap` turns the pad into a keyboard and mouse while setup runs, so
Calamares' widget-based disk page works as well.

## Layout

```
installer/
  packages.x86_64        live ISO packages (read by iso/build.sh)
  aur-packages.txt       AUR builds: ckbcomp, calamares
  file-permissions.txt   executables, for profiledef.sh
  airootfs/              copied over the archiso profile
    etc/calamares/
      settings.conf      step sequence
      modules/*.conf     module settings
      branding/lumen/    QML pages, components/, images/, slideshow
    usr/bin/
      lumen-installer-session   live entry point (run by lumen-session)
      lumen-installer           starts Calamares as root
      lumen-padmap              controller to keyboard/mouse
    usr/share/lumen-installer/
      start.qml          power-on screen
      target-setup       live image -> installed system (in the chroot)
      apply-avatar       copies the chosen avatar into the new system
  preview/               renders every screen to PNG without Calamares
```

## How it installs

The live root (`/run/archiso/airootfs`) is copied to the new disk, then
`target-setup` makes it an ordinary installed system: it restores the kernel,
writes a standard mkinitcpio preset, removes the live account setup,
autologin and archiso units, locks root, sets up the pacman keyring, writes the
greetd config that starts at the sign-in screen, and removes the installer.
Calamares then creates the profile, installs GRUB (EFI id `Lumen`) and builds
the initramfs.

The avatar picked on the profile page is copied to
`/var/lib/AccountsService/icons/<user>` and `~/.face`, where the sign-in
screen finds it. Choosing the first option keeps the default: the name's
initial on the profile colour.

## Previewing the screens

The pages can be rendered without Calamares or an Arch system, with mocked
Calamares objects:

```sh
python -m venv .venv && .venv/bin/pip install PySide6
.venv/bin/python installer/preview/preview.py installer/preview/out
```

This writes one PNG per screen at 1920x1080.
