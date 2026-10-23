#!/usr/bin/env bash
# Upload a pacman repo to a GitHub release: [lumen] (out/repo, from
# build-iso.sh) or the PS5 kernel's [lumen-ps5] (out/ps5-repo, from
# build-ps5.sh). Installed systems update from them, by hand and
# automatically; see session/lumen-update-system.
#
#   GH_TOKEN=... publish-repo.sh <repo dir> [release tag] [repo name]
set -euo pipefail

dir="$1"
tag="${2:-lumen-repo}"
name="${3:-lumen}"
cd "$dir"

if ! gh release view "$tag" >/dev/null 2>&1; then
	gh release create "$tag" --prerelease --latest=false --title "Lumen package repo [$name]" \
		--notes "The [$name] pacman repo that Lumen OS updates from (Settings › System update, and automatic updates). CI replaces these files on every push to main."
fi

# Packages first and the database last, so a system that updates mid-upload
# never sees a database that lists files not uploaded yet.
gh release upload "$tag" --clobber ./*.pkg.tar.zst
gh release upload "$tag" --clobber "$name.db" "$name.db.tar.gz" "$name.files" "$name.files.tar.gz"

# Drop packages the new database no longer lists.
gh release view "$tag" --json assets -q '.assets[].name' | while read -r asset; do
	if [[ ! -e "$asset" ]]; then gh release delete-asset "$tag" "$asset" -y; fi
done
