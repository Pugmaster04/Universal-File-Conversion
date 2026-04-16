#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ARCH="$(uname -m)"
case "$ARCH" in
  amd64|x86_64)
    ARCH="x86_64"
    DEB_ARCH="amd64"
    ;;
  aarch64|arm64)
    ARCH="arm64"
    DEB_ARCH="arm64"
    ;;
  *)
    DEB_ARCH="$ARCH"
    ;;
esac
PACKAGE_VERSION="$(python3 - <<'PY'
import pathlib
import re

text = pathlib.Path("modular_file_utility_suite.py").read_text(encoding="utf-8")
match = re.search(r'^APP_VERSION = "([^"]+)"', text, re.MULTILINE)
if not match:
    raise SystemExit("APP_VERSION not found in modular_file_utility_suite.py")
print(match.group(1))
PY
)"
PACKAGE_BASENAME="UniversalConversionHub_UCH_linux_${ARCH}"
PACKAGE_DIR="release_bins/${PACKAGE_BASENAME}"
PACKAGE_ARCHIVE="release_bins/${PACKAGE_BASENAME}.tar.gz"
DEB_PACKAGE_NAME="universal-conversion-hub-uch"
DEB_PACKAGE="release_bins/${DEB_PACKAGE_NAME}_${PACKAGE_VERSION}_${DEB_ARCH}.deb"
DEB_ROOT="build/linux-deb/${DEB_PACKAGE_NAME}"
DEB_APP_ROOT="${DEB_ROOT}/opt/${DEB_PACKAGE_NAME}"
DEB_DESKTOP_FILE="${DEB_ROOT}/usr/share/applications/${DEB_PACKAGE_NAME}.desktop"
DEB_ICON_FILE="${DEB_ROOT}/usr/share/pixmaps/${DEB_PACKAGE_NAME}.png"

echo "[1/6] Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[2/6] Building app binary..."
python3 -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH.spec

echo "[3/6] Building updater binary..."
python3 -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH_Updater.spec

echo "[4/6] Staging binaries..."
mkdir -p release_bins
rm -f "release_bins/UniversalConversionHub_HCB" "release_bins/UniversalConversionHub_HCB_Updater" \
      "release_bins/UniversalFileUtilitySuite" "release_bins/UniversalFileUtilitySuite_Updater" \
      "$PACKAGE_ARCHIVE" "$DEB_PACKAGE" release_bins/*.deb
rm -rf "$PACKAGE_DIR"
if [[ -f "dist/UniversalConversionHub_UCH" ]]; then
  cp -f "dist/UniversalConversionHub_UCH" "release_bins/UniversalConversionHub_UCH"
  chmod +x "release_bins/UniversalConversionHub_UCH"
fi
if [[ -f "dist/UniversalConversionHub_UCH_Updater" ]]; then
  cp -f "dist/UniversalConversionHub_UCH_Updater" "release_bins/UniversalConversionHub_UCH_Updater"
  chmod +x "release_bins/UniversalConversionHub_UCH_Updater"
fi

echo "[5/6] Creating Linux tar.gz package..."
mkdir -p "$PACKAGE_DIR"
cp -f "dist/UniversalConversionHub_UCH" "$PACKAGE_DIR/UniversalConversionHub_UCH"
cp -f "dist/UniversalConversionHub_UCH_Updater" "$PACKAGE_DIR/UniversalConversionHub_UCH_Updater"
cp -f "README.md" "$PACKAGE_DIR/README.md"
cp -f "PROJECT_PLAN.md" "$PACKAGE_DIR/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "$PACKAGE_DIR/update_manifest.example.json"
chmod +x "$PACKAGE_DIR/UniversalConversionHub_UCH" "$PACKAGE_DIR/UniversalConversionHub_UCH_Updater"
tar -czf "$PACKAGE_ARCHIVE" -C release_bins "$PACKAGE_BASENAME"

echo "[6/6] Creating Debian package..."
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_APP_ROOT" "${DEB_ROOT}/DEBIAN" "${DEB_ROOT}/usr/bin" "$(dirname "$DEB_DESKTOP_FILE")" "$(dirname "$DEB_ICON_FILE")"
cp -f "dist/UniversalConversionHub_UCH" "$DEB_APP_ROOT/UniversalConversionHub_UCH"
cp -f "dist/UniversalConversionHub_UCH_Updater" "$DEB_APP_ROOT/UniversalConversionHub_UCH_Updater"
cp -f "README.md" "$DEB_APP_ROOT/README.md"
cp -f "PROJECT_PLAN.md" "$DEB_APP_ROOT/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "$DEB_APP_ROOT/update_manifest.example.json"
cp -f "assets/universal_file_utility_suite_preview.png" "$DEB_ICON_FILE"
chmod 755 "$DEB_APP_ROOT/UniversalConversionHub_UCH" "$DEB_APP_ROOT/UniversalConversionHub_UCH_Updater"
cat > "${DEB_ROOT}/DEBIAN/control" <<EOF
Package: ${DEB_PACKAGE_NAME}
Version: ${PACKAGE_VERSION}
Section: utils
Priority: optional
Architecture: ${DEB_ARCH}
Maintainer: Pugmaster04 <noreply@users.noreply.github.com>
Depends: xdg-utils
Suggests: ffmpeg, pandoc, libreoffice, p7zip-full, imagemagick, aria2
Description: Universal Conversion Hub (UCH)
 Modular desktop utility for conversion, extraction, archives, media workflows,
 storage analysis, and aria2-based downloads.
EOF
cat > "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch" <<'EOF'
#!/bin/sh
exec /opt/universal-conversion-hub-uch/UniversalConversionHub_UCH "$@"
EOF
cat > "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch-updater" <<'EOF'
#!/bin/sh
exec /opt/universal-conversion-hub-uch/UniversalConversionHub_UCH_Updater "$@"
EOF
chmod 755 "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch" "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch-updater"
cat > "$DEB_DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Universal Conversion Hub (UCH)
Comment=Universal file conversion and utility workspace
Exec=universal-conversion-hub-uch
Icon=${DEB_PACKAGE_NAME}
Terminal=false
Categories=Utility;AudioVideo;Graphics;
StartupNotify=true
EOF
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB_PACKAGE"

echo "Done."
echo "App binary:      $ROOT/dist/UniversalConversionHub_UCH"
echo "Updater binary:  $ROOT/dist/UniversalConversionHub_UCH_Updater"
echo "Staged output:   $ROOT/release_bins"
echo "Linux package:   $ROOT/$PACKAGE_ARCHIVE"
echo "Debian package:  $ROOT/$DEB_PACKAGE"
