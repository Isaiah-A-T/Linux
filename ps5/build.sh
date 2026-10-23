#!/usr/bin/env bash
# Build the Lumen OS USB image for the PlayStation 5, booted by the
# ps5-linux loader. See ps5/README.md.
#
#   sudo ./ps5/build.sh <dir with linux-ps5-*.pkg.tar.zst> [out-dir]
#
# The image is a GPT disk with the layout the loader expects:
#   p1  ext4   "lumen"  root file system, grown to fill the drive on first boot
#   p2  FAT32  "boot"   bzImage, initrd.img, cmdline.txt, vram.txt
# It reuses the ISO's packages (iso/build.sh builds them into a local repo)
# and swaps the stock kernel for the ps5-linux kernel package.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(dirname "$here")"
kernel_dir="${1:?usage: build.sh <linux-ps5 package dir> [out-dir]}"
out="${2:-$repo_root/out}"
work="${WORK_DIR:-/tmp/lumen-ps5}"
root="$work/root"
pkgwork="$work/pkgs"
localrepo="$pkgwork/localrepo"

[[ $EUID -eq 0 ]] || { echo "run as root (pacstrap needs it)" >&2; exit 1; }
pacman -Qq arch-install-scripts e2fsprogs dosfstools mtools gptfdisk xz >/dev/null

kernel_pkg=$(compgen -G "$kernel_dir/linux-ps5-*.pkg.tar.zst" | head -n1) ||
	{ echo "no linux-ps5-*.pkg.tar.zst in $kernel_dir" >&2; exit 1; }
kernel_dir="$(cd "$kernel_dir" && pwd)"
mkdir -p "$out"
out="$(cd "$out" && pwd)"

list() { cat "$@" | grep -v '^\s*#' | sed -e 's/#.*//' -e 's/[[:space:]]//g' -e '/^$/d'; }

# --- Packages -------------------------------------------------------------
# The shell, gogdl, Calamares and the other AUR packages, built exactly as
# for the ISO. Kept between runs (delete $work/pkgs to rebuild).
if [[ ! -f "$localrepo/lumen.db.tar.gz" ]]; then
	WORK_DIR="$pkgwork" LUMEN_REPO_ONLY=1 "$repo_root/iso/build.sh" "$out"
fi

conf="$work/pacman.conf"
cp "$here/pacman.conf" "$conf"
# pacman's download sandbox (Landlock) doesn't work inside containers.
sed -i '/^\[options\]/a DisableSandbox' "$conf"
printf '\n[lumen]\nSigLevel = Optional TrustAll\nServer = file://%s\n' "$localrepo" >> "$conf"

mapfile -t pkgs < <(
	list "$here/packages.x86_64" "$repo_root/iso/packages.x86_64"
	# The bootloader is the PS5 loader; Calamares doesn't install one here.
	list "$repo_root/installer/packages.x86_64" | grep -vxE 'grub|efibootmgr|os-prober'
	# AUR list entries come from the official repos or from [lumen].
	list "$repo_root/iso/aur-packages.txt" "$repo_root/installer/aur-packages.txt"
	for f in "$localrepo"/*.pkg.tar.zst; do
		basename "$f" | sed -E 's/-[^-]+-[^-]+-[^-]+\.pkg\.tar\.zst$//'
	done
)
mapfile -t pkgs < <(printf '%s\n' "${pkgs[@]}" | sort -u)

# --- Root file system -----------------------------------------------------
if mountpoint -q "$root"; then umount -R "$root"; fi
rm -rf "$root"
mkdir -p "$root"
# -G: don't copy the build host's keyring; lumen-keyring.service makes a
# fresh one on first boot.
pacstrap -C "$conf" -G "$root" "${pkgs[@]}"

# Initramfs: no autodetect (it would detect the build host), and amdgpu
# early so the display comes up.
sed -i \
	-e 's/^MODULES=.*/MODULES=(amdgpu)/' \
	-e 's/^HOOKS=.*/HOOKS=(base udev modconf kms keyboard keymap block filesystems fsck)/' \
	"$root/etc/mkinitcpio.conf"
echo "KEYMAP=us" > "$root/etc/vconsole.conf"

# The target's pacman.conf: the same repos, without the build-time [lumen].
install -Dm644 "$here/pacman.conf" "$root/etc/pacman.conf"

# The ps5-linux kernel replaces linux and linux-api-headers (it provides
# both); --ask 4 answers "remove the conflicting package" with yes.
# lumen-ps5-ntsync takes over linux's NTSYNC-MODULE for ntsync-autoload.
# (Not via /tmp: arch-chroot mounts a fresh tmpfs there.)
ntsync_dir="$work/lumen-ps5-ntsync"
rm -rf "$ntsync_dir"
cp -a "$here/pkgbuilds/lumen-ps5-ntsync" "$ntsync_dir"
chown -R "${SUDO_USER:-nobody}" "$ntsync_dir"
(cd "$ntsync_dir" && sudo -u "${SUDO_USER:-nobody}" makepkg --nodeps --noconfirm)
ntsync_pkg=$(compgen -G "$ntsync_dir/lumen-ps5-ntsync-*.pkg.tar.zst" | head -n1)
cp "$kernel_pkg" "$ntsync_pkg" "$root/var/cache/pacman/pkg/"
arch-chroot "$root" pacman -U --noconfirm --ask 4 \
	"/var/cache/pacman/pkg/$(basename "$kernel_pkg")" \
	"/var/cache/pacman/pkg/$(basename "$ntsync_pkg")"
kver=$(ls -1 "$root/usr/lib/modules" | grep -v '^extramodules' | sort -V | tail -n1)
# The package's install script builds the initramfs; make sure it exists.
[[ -s "$root/boot/initrd.img-$kver" ]] ||
	arch-chroot "$root" mkinitcpio -k "$kver" -g "/boot/initrd.img-$kver" || true
[[ -s "$root/boot/initrd.img-$kver" && -s "$root/boot/vmlinuz-$kver" ]] ||
	{ echo "kernel $kver: missing vmlinuz or initrd" >&2; exit 1; }

# Overlays: the installer's files (power-on screen, Calamares theme), then
# the PS5 changes on top.
cp -a "$repo_root/installer/airootfs/." "$root/"
cp -a "$here/rootfs/." "$root/"
while read -r path perms _; do
	[[ -z "$path" || "$path" == \#* ]] && continue
	chmod "${perms##*:}" "$root$path"
done < "$repo_root/installer/file-permissions.txt"
chmod 755 "$root/usr/lib/lumen-ps5/"* "$root/usr/share/lumen-installer/ps5-setup-done"


echo lumen > "$root/etc/hostname"
sed -i 's/^#\(en_US.UTF-8 UTF-8\)/\1/' "$root/etc/locale.gen"
echo "LANG=en_US.UTF-8" > "$root/etc/locale.conf"
arch-chroot "$root" locale-gen
cat > "$root/etc/fstab" <<'FSTAB'
# <file system>  <dir>      <type>  <options>                           <dump> <pass>
LABEL=lumen      /          ext4    rw,relatime                         0      1
LABEL=boot       /boot/efi  vfat    rw,relatime,fmask=0022,dmask=0022   0      2
FSTAB
# Kernel updates (pacman -U linux-ps5-*.pkg.tar.zst) copy bzImage and
# initrd.img here, onto the FAT partition the loader reads.
mkdir -p "$root/boot/efi"

# The temporary account that runs the power-on screen and setup on first
# boot; lumen-finish-setup.service removes it afterwards.
arch-chroot "$root" useradd -m -G wheel,video,input,audio -s /bin/bash -c "Player" player
arch-chroot "$root" passwd -d player
echo 'player ALL=(ALL:ALL) NOPASSWD: ALL' > "$root/etc/sudoers.d/10-setup"
chmod 440 "$root/etc/sudoers.d/10-setup"
arch-chroot "$root" passwd -l root
mkdir -p "$root/var/lib/lumen"
touch "$root/var/lib/lumen/setup-pending"

arch-chroot "$root" systemctl enable \
	greetd.service NetworkManager.service bluetooth.service systemd-timesyncd.service \
	lumen-grow-rootfs.service lumen-keyring.service lumen-finish-setup.service
# Optional units: snapd from the AUR, Wi-Fi firmware staging from linux-ps5,
# and the services behind per-game Game settings.
for unit in snapd.socket ps5-stage-firmware.service inputplumber.service power-profiles-daemon.service; do
	arch-chroot "$root" systemctl enable "$unit" 2>/dev/null || echo "not enabling $unit"
done

# A fresh machine id on first boot, and no build leftovers.
: > "$root/etc/machine-id"
rm -rf "$root/var/cache/pacman/pkg/"* "$root/var/log/"*.log "$root/root/.bash_history"

# --- Boot partition -------------------------------------------------------
bootdir="$work/boot"
rm -rf "$bootdir"
mkdir -p "$bootdir"
cp "$root/boot/vmlinuz-$kver" "$bootdir/bzImage"
cp "$root/boot/initrd.img-$kver" "$bootdir/initrd.img"
cp "$here/boot-cmdline.txt" "$bootdir/cmdline.txt"
cp "$here/boot-vram.txt" "$bootdir/vram.txt"

boot_img="$work/boot.img"
rm -f "$boot_img"
mkfs.vfat -C -F 32 -n boot "$boot_img" $((499 * 1024))
mcopy -s -i "$boot_img" "$bootdir"/* ::/

# --- Root partition -------------------------------------------------------
# Room for the files plus 15% and 2 GiB; it grows to fill the drive later.
used_mb=$(du -sm "$root" | cut -f1)
root_mb=$(( used_mb * 115 / 100 + 2048 ))
root_img="$work/root.img"
rm -f "$root_img"
truncate -s "${root_mb}M" "$root_img"
mkfs.ext4 -q -L lumen -m 1 -d "$root" "$root_img"

# --- Disk image -----------------------------------------------------------
# Sectors: boot 1 MiB..500 MiB, root from 500 MiB, 1 MiB spare at the end
# for the backup GPT.
img="$out/lumen-ps5.img"
rm -f "$img" "$img.xz"
truncate -s $(( 500 + root_mb + 1 ))M "$img"
root_start=$(( 500 * 2048 ))
sgdisk -o \
	-n 1:"$root_start":$(( root_start + root_mb * 2048 - 1 )) -t 1:8300 -c 1:lumen \
	-n 2:2048:$(( root_start - 1 )) -t 2:ef00 -c 2:boot \
	"$img"
dd if="$boot_img" of="$img" bs=1M seek=1 conv=notrunc,sparse status=none
dd if="$root_img" of="$img" bs=1M seek=500 conv=notrunc,sparse status=none
rm -f "$boot_img" "$root_img"

xz -T0 -3 "$img"
echo "Image written to $img.xz (kernel $kver)"
