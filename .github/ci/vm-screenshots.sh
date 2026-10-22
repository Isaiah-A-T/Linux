#!/usr/bin/env bash
# Boot the ISO in QEMU twice (as shipped, and straight into the shell) and
# take screenshots through the QEMU monitor.
#
#   .github/ci/vm-screenshots.sh lumen.iso out-dir
set -euo pipefail

iso="$1"
out="$2"
mkdir -p "$out"
work="$(mktemp -d)"

# Boot the ISO's kernel directly with the same command line its boot menu
# uses, so we can add options without driving the menu.
bsdtar -xf "$iso" -C "$work" arch/boot/x86_64 boot syslinux loader 2>/dev/null || true
kernel=$(find "$work" -name 'vmlinuz-linux' | head -n1)
initrd=$(find "$work" -name 'initramfs-linux.img' | head -n1)
cmdline=$(grep -rhoE 'archisobasedir=[^"]*' "$work" | head -n1 | sed 's/ *$//')
echo "kernel=$kernel initrd=$initrd cmdline=$cmdline"
[[ -n "$kernel" && -n "$initrd" && -n "$cmdline" ]]

accel=(-accel tcg)
[[ -w /dev/kvm ]] && accel=(-enable-kvm -cpu host)

boot() {
	local name="$1" extra="$2"
	shift 2
	local mon="$work/$name.mon"
	qemu-system-x86_64 "${accel[@]}" -m 6144 -smp 4 \
		-cdrom "$iso" -kernel "$kernel" -initrd "$initrd" \
		-append "$cmdline console=tty0 console=ttyS0,115200 $extra" \
		-device virtio-vga -display none \
		-device qemu-xhci -device usb-tablet \
		-monitor "unix:$mon,server,nowait" \
		-serial "file:$out/$name-serial.log" &
	local qemu=$!
	local elapsed=0
	# Remaining args: seconds at which to take a screenshot.
	for at in "$@"; do
		sleep $((at - elapsed))
		elapsed=$at
		echo "screendump $out/$name-$(printf %03d "$at")s.png -f png" |
			socat - "UNIX-CONNECT:$mon" >/dev/null || true
	done
	echo quit | socat - "UNIX-CONNECT:$mon" >/dev/null || true
	wait "$qemu" || true
}

# First boot as a player would see it: the installer's power-on screen.
boot installer "" 45 90 150 240
# Second boot straight into the Lumen shell.
boot shell "lumen.skip_installer" 45 90 150 240

ls -l "$out"
