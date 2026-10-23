#!/bin/bash
# Prepare the ps5-linux kernel source for ps5-linux-image's build_image.sh,
# with Lumen's extra patches and config on top, so the kernel works on
# both PS5 Wi-Fi/Bluetooth chips:
#   Marvell IW620 (1b4b:2b56)  moal driver, built by ps5-linux-image
#   MediaTek MT7921 (14c3:7961, BT 0e8d:3603)  mt7921e and btusb, below
#
# Usage: ps5/kernel/prepare.sh <ps5-linux-image checkout>
# Then run ./build_image.sh --kernel-only --distro arch in that checkout:
# it finds work/linux already prepared and only compiles and packages it.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
image=$(cd "$1" && pwd)
patches_dir=$image/work/ps5-linux-patches
linux=$image/work/linux

# The same patch set and kernel version build_image.sh would pick.
patches_ref=$(sed -nE 's/^PATCHES_REF="([^"]+)".*/\1/p' "$image/build_image.sh" | head -1)
[[ -n "$patches_ref" ]] || { echo "no PATCHES_REF in build_image.sh" >&2; exit 1; }

rm -rf "$patches_dir" "$linux"
mkdir -p "$patches_dir"
git -C "$patches_dir" init -q
git -C "$patches_dir" fetch -q --depth 1 https://github.com/ps5-linux/ps5-linux-patches.git "$patches_ref"
git -C "$patches_dir" reset -q --hard FETCH_HEAD

branch="v$(sed -nE 's/^# Linux\/[^ ]+ ([0-9]+\.[0-9]+(\.[0-9]+)?) .*/\1/p' "$patches_dir/.config" | head -1)"
echo "==> Linux $branch with ps5-linux-patches $patches_ref"
git clone -q --branch "$branch" --depth 1 \
	https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git "$linux"

for p in "$patches_dir"/*.patch; do
	git -C "$linux" apply --exclude=Makefile "$p"
done
for p in "$here"/patches/*.patch; do
	echo "==> $(basename "$p")"
	git -C "$linux" apply "$p"
done

cp "$patches_dir/.config" "$linux/.config"
# MediaTek MT7921 Wi-Fi: everything it needs is already a module, only the
# PCIe front end is switched off.
sed -i 's/^# CONFIG_MT7921E is not set$/CONFIG_MT7921E=m/' "$linux/.config"
grep -q '^CONFIG_MT7921E=m$' "$linux/.config"
