#!/usr/bin/env bash
# Runs inside an archlinux container (see .github/workflows/build-iso.yml):
# sets up a build user and runs iso/build.sh.
set -euxo pipefail

src="${1:-/src}"

pacman-key --init
pacman-key --populate archlinux
# Multilib for Steam's 32-bit dependencies while resolving makedepends.
grep -q '^\[multilib\]' /etc/pacman.conf ||
	printf '\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n' >> /etc/pacman.conf
pacman -Syu --noconfirm --needed archiso base-devel git sudo

# makepkg refuses root, so packages are built by "builder", which may install
# build dependencies with sudo.
id builder >/dev/null 2>&1 || useradd -m builder
echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder
# No -debug split packages; they would end up in the ISO's package list.
sed -i 's/^OPTIONS=(\(.*\)debug/OPTIONS=(\1!debug/' /etc/makepkg.conf
echo "MAKEFLAGS=\"-j$(nproc)\"" >> /etc/makepkg.conf

git config --global --add safe.directory "$src"
SUDO_USER=builder WORK_DIR=/tmp/lumen-iso "$src/iso/build.sh" "$src/out"

# The packages we built become the [lumen] pacman repo that installed systems
# update from (Settings › System update); publish-repo.sh uploads it to a
# GitHub release. Release asset names can't hold ':' (package epochs), so
# rename those and index the repo again under the new names.
repo="$src/out/repo"
rm -rf "$repo"
mkdir -p "$repo"
cp /tmp/lumen-iso/localrepo/*.pkg.tar.zst "$repo/"
for f in "$repo"/*:*; do
	if [[ -e "$f" ]]; then mv "$f" "${f//:/.}"; fi
done
repo-add -q "$repo/lumen.db.tar.gz" "$repo"/*.pkg.tar.zst
# pacman asks for lumen.db and lumen.files, which repo-add makes as symlinks.
for f in lumen.db lumen.files; do
	cp --remove-destination "$(readlink -f "$repo/$f")" "$repo/$f"
done
