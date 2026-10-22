#!/usr/bin/env bash
# Build the Lumen OS live ISO on an Arch Linux host.
#
#   sudo ./iso/build.sh [out-dir]
#
# Starts from the stock archiso "releng" profile, layers iso/airootfs on top,
# builds the packages that are not in the official repos into a local repo,
# and runs mkarchiso.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(dirname "$here")"
work="${WORK_DIR:-/tmp/lumen-iso}"
out="${1:-$repo_root/out}"
profile="$work/profile"
localrepo="$work/localrepo"
builder="${SUDO_USER:-nobody}"

[[ $EUID -eq 0 ]] || { echo "run as root (mkarchiso needs it)" >&2; exit 1; }
pacman -Qq archiso base-devel git >/dev/null

rm -rf "$work"
mkdir -p "$work" "$localrepo" "$out"
cp -a /usr/share/archiso/configs/releng "$profile"

# --- Local packages -------------------------------------------------------
# makepkg refuses to run as root, so build as the invoking user.
build_pkg() {
	local dir="$1"
	chown -R "$builder" "$dir"
	(cd "$dir" && sudo -u "$builder" env PKGDEST="$localrepo" LUMEN_SRC="$repo_root" \
		makepkg "${2:---syncdeps}" --nocheck --noconfirm --clean --cleanbuild)
}

pkgdir_tmp="$work/pkgbuilds"
mkdir -p "$pkgdir_tmp"
chown "$builder" "$localrepo" "$pkgdir_tmp"

# Our own packages (the shell itself and gogdl). lumen is arch=any and only
# copies files, so its runtime dependencies don't need to be on the build host.
for p in "$here"/pkgbuilds/*/; do
	name="$(basename "$p")"
	cp -a "$p" "$pkgdir_tmp/$name"
	if [[ "$name" == lumen ]]; then
		build_pkg "$pkgdir_tmp/$name" --nodeps
	else
		build_pkg "$pkgdir_tmp/$name" --syncdeps
	fi
done

# AUR packages, unless the official repos already carry them. Lists are read
# in order and each build is installed on the host, so a package can depend on
# an AUR package listed above it. installer/aur-packages.txt belongs to the
# installer.
aur_lists=("$here/aur-packages.txt")
[[ -f "$repo_root/installer/aur-packages.txt" ]] && aur_lists+=("$repo_root/installer/aur-packages.txt")
extra_official=()
while read -r pkg; do
	pkg="${pkg%%#*}"
	pkg="${pkg//[[:space:]]/}"
	[[ -z "$pkg" ]] && continue
	if pacman -Si "$pkg" >/dev/null 2>&1; then
		extra_official+=("$pkg")
		continue
	fi
	[[ -d "$pkgdir_tmp/aur-$pkg" ]] && continue
	sudo -u "$builder" git clone --depth 1 "https://aur.archlinux.org/$pkg.git" "$pkgdir_tmp/aur-$pkg"
	# Only build-time dependencies go on the build host; runtime ones (for
	# umu-launcher that is most of Steam's runtime) are resolved when the ISO's
	# root filesystem is installed.
	mapfile -t needed < <(sed -n -E 's/^\s*(makedepends|checkdepends) = //p' \
		"$pkgdir_tmp/aur-$pkg/.SRCINFO")
	if (( ${#needed[@]} )); then
		mapfile -t missing < <(pacman -T "${needed[@]}" || true)
		if (( ${#missing[@]} )); then
			pacman -S --noconfirm --needed --asdeps "${missing[@]}"
		fi
	fi
	build_pkg "$pkgdir_tmp/aur-$pkg" --nodeps
	# Install it on the host so later AUR builds can use it at build time.
	built=$(compgen -G "$localrepo/$pkg-[0-9]*.pkg.tar.zst" || true)
	if [[ -n "$built" ]]; then
		pacman -Udd --noconfirm --needed --asdeps $built
	fi
done < <(cat "${aur_lists[@]}")

repo-add "$localrepo/lumen.db.tar.gz" "$localrepo"/*.pkg.tar.zst

# --- Profile --------------------------------------------------------------
# pacman.conf: enable multilib (Steam, 32-bit Vulkan) and the local repo.
grep -q '^\[multilib\]' "$profile/pacman.conf" ||
	printf '\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n' >> "$profile/pacman.conf"
printf '\n[lumen]\nSigLevel = Optional TrustAll\nServer = file://%s\n' "$localrepo" >> "$profile/pacman.conf"

{
	echo
	echo "# --- Lumen OS ---"
	grep -v '^\s*#' "$here/packages.x86_64" | sed '/^\s*$/d'
	# The installer ships its own live-ISO package list.
	if [[ -f "$repo_root/installer/packages.x86_64" ]]; then
		grep -v '^\s*#' "$repo_root/installer/packages.x86_64" | sed '/^\s*$/d'
	fi
	printf '%s\n' "${extra_official[@]}"
	# Everything we built locally.
	for f in "$localrepo"/*.pkg.tar.zst; do
		basename "$f" | sed -E 's/-[^-]+-[^-]+-[^-]+\.pkg\.tar\.zst$//'
	done
} >> "$profile/packages.x86_64"

# releng autologs root into a shell and uses systemd-networkd. We boot into
# greetd and use NetworkManager instead.
rm -f "$profile/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf"
rm -f "$profile/airootfs/etc/systemd/system/multi-user.target.wants/systemd-networkd.service"
rm -f "$profile/airootfs/etc/systemd/system/multi-user.target.wants/iwd.service"
rm -rf "$profile/airootfs/etc/systemd/network"

cp -a "$here/airootfs/." "$profile/airootfs/"
if [[ -d "$repo_root/installer/airootfs" ]]; then
	cp -a "$repo_root/installer/airootfs/." "$profile/airootfs/"
fi

sed -i \
	-e 's/^iso_name=.*/iso_name="lumen"/' \
	-e 's/^iso_label=.*/iso_label="LUMEN_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"/' \
	-e 's/^iso_publisher=.*/iso_publisher="Lumen OS"/' \
	-e 's/^iso_application=.*/iso_application="Lumen OS live"/' \
	"$profile/profiledef.sh"
# archiso copies overlay files as 0644; list the executables here. The
# installer keeps its own list in installer/file-permissions.txt
# ("<path> <uid:gid:mode>" per line, # comments).
{
	echo 'file_permissions+=('
	echo '  ["/usr/local/bin/lumen-live-setup"]="0:0:755"'
	if [[ -f "$repo_root/installer/file-permissions.txt" ]]; then
		while read -r path perms _; do
			[[ -z "$path" || "$path" == \#* ]] && continue
			printf '  ["%s"]="%s"\n' "$path" "$perms"
		done < "$repo_root/installer/file-permissions.txt"
	fi
	echo ')'
} >> "$profile/profiledef.sh"

mkarchiso -v -w "$work/mkarchiso" -o "$out" "$profile"
echo "ISO written to $out"
