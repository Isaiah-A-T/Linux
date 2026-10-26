#!/usr/bin/env bash
# Attach the PC ISO and the PS5 image from two finished CI runs to a
# GitHub release. Files over GitHub's 2 GiB asset limit are split into
# numbered .partNN pieces; rejoin with `cat <file>.part* > <file>`.
#
#   GH_TOKEN=... upload-release.sh <release tag> <ISO run id> <PS5 run id>
set -euo pipefail

tag="$1"
iso_run="$2"
ps5_run="$3"
limit=$((2 * 1024 * 1024 * 1024))

work="$(mktemp -d)"
gh run download "$iso_run" -n lumen-iso -D "$work/iso"
gh run download "$ps5_run" -n lumen-ps5 -D "$work/ps5"

out="$work/out"
mkdir -p "$out"
mv "$work"/iso/*.iso "$work"/ps5/*.img.xz "$out"/
cd "$out"

# The checksums cover the whole files, so they also check a rejoined split.
cat "$work/iso/SHA256SUMS" "$work/ps5/SHA256SUMS" > SHA256SUMS
sha256sum -c SHA256SUMS

for f in *.iso *.img.xz; do
	if (( $(stat -c %s "$f") > limit )); then
		split -b 1900M -d -a 2 "$f" "$f.part"
		rm "$f"
	fi
done
ls -l

gh release upload "$tag" --clobber ./*
