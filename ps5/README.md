# Lumen OS on PlayStation 5

A USB image of Lumen OS for jailbroken PS5 consoles, booted by the
[ps5-linux](https://github.com/ps5-linux) loader. It runs the same console
shell, power-on screen and setup as the ISO, on the ps5-linux kernel.

> **Experimental.** Linux on firmware 13.60 is brand new (soniciso's loader,
> October 2026). Expect rough edges: USB I/O problems are being worked on,
> there is no standby, Wi-Fi works only on Marvell chips (Ethernet works on
> every model) and some TVs show a black screen until `cmdline.txt` is
> tweaked (see [Troubleshooting](#troubleshooting)).

## What works where

| Firmware | Loader | Models |
| --- | --- | --- |
| 13.60 | [soniciso1/ps5-linux-loader](https://github.com/soniciso1/ps5-linux-loader/releases) `v13.60` | Phat, Slim, Pro (one ELF for all) |
| 3.00 – 7.61 | [ps5-linux/ps5-linux-loader](https://github.com/ps5-linux/ps5-linux-loader/releases) | Phat, Slim |

8.00 – 13.50 are not supported by any loader yet. Linux doesn't replace the
PS5 system software: every time the console is turned on it starts PS5 system
software, and you run the jailbreak and the loader again to get back into
Lumen.

## You need

- A jailbroken PS5 on a supported firmware whose jailbreak gives you an ELF
  loader on port 9021 (on 13.60, the Relapse browser jailbreak does).
- A USB drive of **64 GB or more**. An external USB SSD is much faster.
- A PC on the same network as the PS5.
- A controller, keyboard or mouse for setup. A DualSense pairs over
  Bluetooth on the first screen (step 6), or works right away on a USB cable.

## 1. Get the image

1. Open the repository's **Actions** tab, pick the latest green
   **Build PS5 image** run and download the **lumen-ps5** artifact.
2. Unzip it. You get `lumen-ps5.img.xz` and `SHA256SUMS`.

To build it yourself on Arch Linux (needs about 60 GB free):

```sh
git clone https://github.com/ps5-linux/ps5-linux-image && cd ps5-linux-image
./build_image.sh --kernel-only --distro arch        # needs Docker
cd .. && sudo ./ps5/build.sh ps5-linux-image/linux-bin out
```

## 2. Flash the USB drive

This erases the whole drive.

- **Windows or macOS:** open [Balena Etcher](https://etcher.balena.io/),
  choose `lumen-ps5.img.xz` (no need to unpack it), pick the USB drive and
  click **Flash**.
- **Linux:** find the drive with `lsblk`, then
  `xz -dc lumen-ps5.img.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync`

The drive gets two partitions: a small FAT32 one called `boot` (the kernel,
`cmdline.txt` and `vram.txt`) and the Lumen system. The system grows to fill
the drive on the first boot.

## 3. Set up the PS5 (once)

1. **Settings > System > Power Saving > Features Available in Rest Mode >
   Supply Power to USB Ports: Always.** Without this the console won't
   start Linux.
2. **Settings > System > HDMI > Enable HDMI Device Link: Off.**
3. Recommended: turn off automatic system software updates, so the console
   stays on 13.60.

## 4. Get the loader

Download `ps5-linux-loader.elf` from the
[soniciso1/ps5-linux-loader v13.60 release](https://github.com/soniciso1/ps5-linux-loader/releases)
(on 3.00 – 7.61, use the upstream release instead). The release notes list an
MD5 checksum to compare against.

## 5. Boot Lumen

1. Plug the USB drive into the **rear USB-A** port or the **front USB-C**
   port. Not the front USB-A port: it's USB 2.0.
2. Turn the PS5 on and run your 13.60 jailbreak as usual, up to the point
   where the ELF loader is listening on **port 9021**. **Don't load etaHEN or
   kstuff.** The loader freezes with them.
3. Send the loader from your PC, replacing `PS5IP` with the console's IP
   address (shown by the jailbreak or under Settings > Network):
   - Linux or macOS: `socat -t 99999999 - TCP:PS5IP:9021 < ps5-linux-loader.elf`
   - Windows: use any PS5 payload sender, port 9021.
4. The console goes into rest mode by itself. **Wait until the orange light
   stops blinking and stays solid.**
5. Press the power button. The light turns **white** and Lumen starts on the
   TV. If the PS5 system software comes back instead, you pressed the button
   too early or the rest-mode USB setting isn't on.

## 6. First boot

Lumen first asks you to **connect your controller**. A DualSense paired
with the PS5 system software isn't paired with Linux, so **hold PS + Create
until the light bar flashes**. Lumen pairs it, shows "Controller connected"
and moves on by itself. A controller on a USB cable, or one paired with
Lumen before, skips this screen. Xbox and 8BitDo controllers work the same
way with their pairing button; Enter on a keyboard skips it.

Then comes Lumen's power-on screen:

- **Set up Lumen OS** picks language, region, keyboard and your profile
  (name, avatar, password or PIN). There's no disk step: Lumen already runs
  from the USB drive. At the end, choose **Go to sign-in**.
- **Try it first** opens the console shell right away. You can run setup
  later from the dock.

Don't restart from Lumen. A restart drops the PS5 back into its own system
software. To get back into Lumen, repeat step 5. To stop, turn Lumen off
from the shell, or hold the power button.

## Tips

- **Faster CPU/GPU and fan control:** build
  [ps5-linux-tools](https://github.com/ps5-linux/ps5-linux-tools) on the
  console, then `sudo ./ps5_control --fan on` and
  `sudo ./ps5_control --boost on` (about 3.5 GHz CPU, 2.23 GHz GPU).
- **Game graphics glitches:** set the environment variable
  `RADV_DEBUG=nohiz` for that game.
- **Kernel updates:** don't install Arch's `linux` package. Install a newer
  `linux-ps5-*.pkg.tar.zst` with `sudo pacman -U`. It copies the new kernel to
  the `boot` partition by itself.
- **Video memory:** `vram.txt` on the `boot` partition sets it (default
  `0x20000000`, 512 MB, which lets the GPU borrow more as needed).

## Troubleshooting

**Logs:** every minute Lumen copies its logs to a `lumen-logs` folder on the
USB drive's `boot` partition. Plug the drive into a PC after a try and send
`status.txt`, `journal.txt` and any `installer-session.log` or
`calamares.log` along with your report.

The light is white but the screen stays black. Open the `boot` partition of
the USB drive on a PC and edit `cmdline.txt` (one line):

1. Remove `video=DP-1:1920x1080@60`.
2. Or add `amdgpu.force_1080p=1` at the end.
3. Turn HDCP on or off in the PS5's settings and try again.
4. Try another TV, monitor or capture card. Some HDMI displays don't work
   above 1080p yet.

Other things:

- **The console freezes instead of going to rest mode:** etaHEN or kstuff is
  loaded. Reboot and run the jailbreak without them.
- **A "repairing" screen after turning the PS5 back on:** harmless.
- **No Wi-Fi:** only Marvell Wi-Fi chips are supported so far. Use Ethernet
  or a USB Wi-Fi adapter.
- **The shell starts in a plain window instead of fullscreen gamescope:**
  gamescope couldn't take the display. Its settings for the PS5 are in
  `/etc/lumen/session.conf`.

Help and reports for the loader and kernel: the ps5-linux
[Discord](https://discord.gg/PeMGVB7BAm).

## How the image is put together

`ps5/build.sh` runs on Arch Linux as root. It:

1. builds the ISO's own packages (shell, gogdl, Calamares and the other AUR
   packages) with `LUMEN_REPO_ONLY=1 iso/build.sh`;
2. `pacstrap`s a root file system from `ps5/packages.x86_64`,
   `iso/packages.x86_64` and `installer/packages.x86_64` (without GRUB);
3. installs the `linux-ps5` kernel package in place of `linux`, with an
   initramfs that loads `amdgpu` early;
4. copies `installer/airootfs` and then `ps5/rootfs` over it. The PS5
   overlay holds the setup sequence without the disk step (Calamares runs on
   the running system, `dont-chroot`), the first-boot greetd config, the
   gamescope settings and first-boot services;
5. writes the `boot` FAT32 and `lumen` ext4 partitions into
   `lumen-ps5.img` and compresses it.

The kernel comes from
[ps5-linux-image](https://github.com/ps5-linux/ps5-linux-image)'s
`build_image.sh --kernel-only --distro arch`, at the commit pinned in
`.github/workflows/build-ps5.yml`. The CI caches it per commit.

First boot runs as a temporary `player` account with the setup marker
`/var/lib/lumen/setup-pending`. Setup creates the real profile and switches
greetd to the sign-in screen, then `lumen-finish-setup.service` removes
`player` and the installer.
