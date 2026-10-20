#!/bin/sh
set -eu
taskProject="$(cd "$(dirname "$0")" && pwd)"
taskPython="$taskProject/.venv-macos/bin/python"
taskVersion="$("$taskPython" -c "import json;print(json.load(open('$taskProject/package.json'))['version'])")"
taskName="VGN-X68-Custom-Firmware-$taskVersion-macOS"
cd "$taskProject"
"$taskPython" -m unittest discover -s tests -q
# Reuse a Developer ID identity so macOS privacy grants can survive updates.
# Release builds must supply the same identity each time. Never silently fall
# back to an ad-hoc signature when a requested identity is unavailable.
set --
if [ -n "${X68_CODESIGN_IDENTITY:-}" ]; then
    set -- --codesign-identity "$X68_CODESIGN_IDENTITY"
else
    echo 'Warning: ad-hoc build; Input Monitoring permission may need renewing after updates.' >&2
fi
# .app bundle. Only runtime files are bundled: our patches, fonts, pixel art and the knowledge doc.
# No VGN binary is included; the app fetches the official payload from VGN on first install.
"$taskPython" -m PyInstaller --noconfirm --clean --windowed --noupx --name "$taskName" \
    --icon assets/icon.png \
    --osx-bundle-identifier com.vgn-x68.custom-firmware \
    "$@" \
    --add-data 'firmware-patches:firmware-patches' \
    --add-data 'docs/AI-KNOWLEDGE.md:docs' \
    --add-data 'assets/fonts:assets/fonts' \
    --add-data 'assets/icon.png:assets' \
    --add-data 'assets/pixel/home-scene.png:assets/pixel' \
    --add-data 'assets/pixel/battery-scene.png:assets/pixel' \
    --add-data 'assets/pixel/bunny-sprite.png:assets/pixel' \
    --add-data 'assets/pixel/lcd-preview.png:assets/pixel' \
    --hidden-import tools.reflash_v0113 app.py
cd dist
rm -f "$taskName.zip"
ditto -c -k --keepParent "$taskName.app" "$taskName.zip"
shasum -a 256 "$taskName.zip" > SHA256SUMS-macOS.txt
cat SHA256SUMS-macOS.txt
