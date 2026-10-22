#!/usr/bin/env bash
# Upload the [lumen] pacman repo (out/repo, from build-iso.sh) to a GitHub
# release. Installed systems use it as their Lumen repo; see
# session/lumen-update-system.
#
#   GH_TOKEN=... publish-repo.sh <repo dir> [release tag]
set -euo pipefail

dir="$1"
tag="${2:-lumen-repo}"
cd "$dir"

if ! gh release view "$tag" >/dev/null 2>&1; then
	gh release create "$tag" --prerelease --latest=false --title "Lumen package repo" \
		--notes "The [lumen] pacman repo that Lumen OS updates from (Settings › System update). CI replaces these files on every push to main."
fi

# Packages first and the database last, so a system that updates mid-upload
# never sees a database that lists files not uploaded yet.
gh release upload "$tag" --clobber ./*.pkg.tar.zst
gh release upload "$tag" --clobber lumen.db lumen.db.tar.gz lumen.files lumen.files.tar.gz

# Drop packages the new database no longer lists.
gh release view "$tag" --json assets -q '.assets[].name' | while read -r asset; do
	if [[ ! -e "$asset" ]]; then gh release delete-asset "$tag" "$asset" -y; fi
done
