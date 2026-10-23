#!/usr/bin/env bash
# Runs inside an archlinux container (see .github/workflows/build-ps5.yml):
# the same build user setup as build-iso.sh, then ps5/build.sh with the
# linux-ps5 kernel package from the workflow's kernel job.
set -euxo pipefail

src="${1:-/src}"
kernel="${2:-/src/kernel}"

pacman-key --init
pacman-key --populate archlinux
grep -q '^\[multilib\]' /etc/pacman.conf ||
	printf '\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n' >> /etc/pacman.conf
grep -q '^DisableSandbox' /etc/pacman.conf || sed -i '/^\[options\]/a DisableSandbox' /etc/pacman.conf
pacman -Syu --noconfirm --needed archiso base-devel git sudo \
	arch-install-scripts e2fsprogs dosfstools mtools gptfdisk xz

id builder >/dev/null 2>&1 || useradd -m builder
echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder
sed -i 's/^OPTIONS=(\(.*\)debug/OPTIONS=(\1!debug/' /etc/makepkg.conf
echo "MAKEFLAGS=\"-j$(nproc)\"" >> /etc/makepkg.conf

git config --global --add safe.directory "$src"
SUDO_USER=builder WORK_DIR=/tmp/lumen-ps5 "$src/ps5/build.sh" "$kernel" "$src/out"

# The kernel and its NTSYNC-MODULE marker become the [lumen-ps5] pacman repo,
# which PS5 consoles update their kernel from (see session/lumen-update-system;
# publish-repo.sh uploads it to the "lumen-ps5-repo" release).
repo="$src/out/ps5-repo"
rm -rf "$repo"
mkdir -p "$repo"
cp "$kernel"/linux-ps5-*.pkg.tar.zst /tmp/lumen-ps5/lumen-ps5-ntsync/lumen-ps5-ntsync-*.pkg.tar.zst "$repo/"
repo-add -q "$repo/lumen-ps5.db.tar.gz" "$repo"/*.pkg.tar.zst
for f in lumen-ps5.db lumen-ps5.files; do
	cp --remove-destination "$(readlink -f "$repo/$f")" "$repo/$f"
done
