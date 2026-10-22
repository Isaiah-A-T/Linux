#!/usr/bin/env bash
# Runs inside an archlinux container (see .github/workflows/build-iso.yml):
# sets up a build user and runs iso/build.sh.
set -euxo pipefail

src="${1:-/src}"

pacman-key --init
pacman-key --populate archlinux
# Multilib for Steam's 32-bit dependencies while resolving makedepends.
sed -i '/^#\[multilib\]/{s/^#//;n;s/^#//}' /etc/pacman.conf
pacman -Syu --noconfirm --needed archiso base-devel git sudo
pacman -Sl multilib | wc -l

# makepkg refuses root, so packages are built by "builder", which may install
# build dependencies with sudo.
id builder >/dev/null 2>&1 || useradd -m builder
echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder
# No -debug split packages; they would end up in the ISO's package list.
sed -i 's/^OPTIONS=(\(.*\)debug/OPTIONS=(\1!debug/' /etc/makepkg.conf
echo "MAKEFLAGS=\"-j$(nproc)\"" >> /etc/makepkg.conf

git config --global --add safe.directory "$src"
SUDO_USER=builder WORK_DIR=/tmp/lumen-iso "$src/iso/build.sh" "$src/out"
