#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

APP_NAME="Universal Conversion Hub (UCH)"
APP_BINARY_NAME="UniversalConversionHub_UCH"
UPDATER_BINARY_NAME="UniversalConversionHub_UCH_Updater"
PACKAGE_NAME="universal-conversion-hub-uch"
DESKTOP_ID="io.github.Pugmaster04.UniversalConversionHub.desktop"
PACKAGING_ROOT="packaging/linux"
BUILD_ROOT="build/linux-packaging"
APPDIR_ROOT="${BUILD_ROOT}/AppDir"
DEB_ROOT="${BUILD_ROOT}/deb-root"
ICON_OUTPUT="${BUILD_ROOT}/${PACKAGE_NAME}.png"
DESKTOP_TEMPLATE="${PACKAGING_ROOT}/${PACKAGE_NAME}.desktop.in"
APPDATA_TEMPLATE="${PACKAGING_ROOT}/${PACKAGE_NAME}.appdata.xml"
APP_RUN_TEMPLATE="${PACKAGING_ROOT}/AppRun"
APPIMAGE_TOOL_DIR="${BUILD_ROOT}/tools"

ARCH="$(uname -m)"
case "$ARCH" in
  amd64|x86_64)
    ARCH="x86_64"
    DEB_ARCH="amd64"
    APPIMAGE_ARCH="x86_64"
    ;;
  aarch64|arm64)
    ARCH="arm64"
    DEB_ARCH="arm64"
    APPIMAGE_ARCH="aarch64"
    ;;
  *)
    echo "Unsupported Linux architecture for packaging: ${ARCH}" >&2
    exit 1
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

TAR_BASENAME="${APP_BINARY_NAME}_linux_${ARCH}"
TAR_DIR="release_bins/${TAR_BASENAME}"
TAR_PACKAGE="release_bins/${TAR_BASENAME}.tar.gz"
DEB_PACKAGE="release_bins/${PACKAGE_NAME}_${PACKAGE_VERSION}_${DEB_ARCH}.deb"
APPIMAGE_PACKAGE="release_bins/${APP_BINARY_NAME}_linux_${ARCH}.AppImage"
APPIMAGE_TOOL="${APPIMAGE_TOOL_DIR}/appimagetool-${APPIMAGE_ARCH}.AppImage"
APPIMAGE_TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${APPIMAGE_ARCH}.AppImage"

render_desktop_file() {
  local exec_target="$1"
  local output_path="$2"
  sed "s|__EXEC__|${exec_target}|g" "$DESKTOP_TEMPLATE" > "$output_path"
}

build_linux_icon() {
  python3 - <<'PY'
from pathlib import Path
import shutil

dst = Path("build/linux-packaging/universal-conversion-hub-uch.png")
dst.parent.mkdir(parents=True, exist_ok=True)
src_ico = Path("assets/universal_file_utility_suite.ico")
src_png = Path("assets/universal_file_utility_suite_preview.png")

try:
    from PIL import Image
    with Image.open(src_ico) as image:
        image = image.convert("RGBA")
        image.save(dst, format="PNG")
except Exception:
    shutil.copyfile(src_png, dst)
PY
}

download_appimagetool() {
  mkdir -p "$APPIMAGE_TOOL_DIR"
  if [[ ! -x "$APPIMAGE_TOOL" ]]; then
    echo "Downloading appimagetool for ${APPIMAGE_ARCH}..."
    curl -L "$APPIMAGE_TOOL_URL" -o "$APPIMAGE_TOOL"
    chmod +x "$APPIMAGE_TOOL"
  fi
}

echo "[1/7] Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[2/7] Building app binary..."
python3 -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH.spec

echo "[3/7] Building updater binary..."
python3 -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH_Updater.spec

echo "[4/7] Staging binaries..."
mkdir -p release_bins
rm -f \
  "release_bins/UniversalConversionHub_HCB" \
  "release_bins/UniversalConversionHub_HCB_Updater" \
  "release_bins/UniversalFileUtilitySuite" \
  "release_bins/UniversalFileUtilitySuite_Updater" \
  "$TAR_PACKAGE" \
  "$DEB_PACKAGE" \
  "$APPIMAGE_PACKAGE" \
  release_bins/*.deb \
  release_bins/*.AppImage
rm -rf "$TAR_DIR" "$APPDIR_ROOT" "$DEB_ROOT" "$BUILD_ROOT/deb-smoke"

cp -f "dist/${APP_BINARY_NAME}" "release_bins/${APP_BINARY_NAME}"
cp -f "dist/${UPDATER_BINARY_NAME}" "release_bins/${UPDATER_BINARY_NAME}"
chmod +x "release_bins/${APP_BINARY_NAME}" "release_bins/${UPDATER_BINARY_NAME}"

echo "[5/7] Creating Linux tar.gz package..."
mkdir -p "$TAR_DIR"
cp -f "dist/${APP_BINARY_NAME}" "$TAR_DIR/${APP_BINARY_NAME}"
cp -f "dist/${UPDATER_BINARY_NAME}" "$TAR_DIR/${UPDATER_BINARY_NAME}"
cp -f "README.md" "$TAR_DIR/README.md"
cp -f "PROJECT_PLAN.md" "$TAR_DIR/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "$TAR_DIR/update_manifest.example.json"
chmod +x "$TAR_DIR/${APP_BINARY_NAME}" "$TAR_DIR/${UPDATER_BINARY_NAME}"
tar -czf "$TAR_PACKAGE" -C release_bins "$TAR_BASENAME"

echo "[6/7] Creating Debian package..."
build_linux_icon
mkdir -p \
  "${DEB_ROOT}/DEBIAN" \
  "${DEB_ROOT}/opt/${PACKAGE_NAME}" \
  "${DEB_ROOT}/usr/bin" \
  "${DEB_ROOT}/usr/share/applications" \
  "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps" \
  "${DEB_ROOT}/usr/share/metainfo"
cp -f "dist/${APP_BINARY_NAME}" "${DEB_ROOT}/opt/${PACKAGE_NAME}/${APP_BINARY_NAME}"
cp -f "dist/${UPDATER_BINARY_NAME}" "${DEB_ROOT}/opt/${PACKAGE_NAME}/${UPDATER_BINARY_NAME}"
cp -f "README.md" "${DEB_ROOT}/opt/${PACKAGE_NAME}/README.md"
cp -f "PROJECT_PLAN.md" "${DEB_ROOT}/opt/${PACKAGE_NAME}/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "${DEB_ROOT}/opt/${PACKAGE_NAME}/update_manifest.example.json"
cp -f "$ICON_OUTPUT" "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png"
cp -f "$APPDATA_TEMPLATE" "${DEB_ROOT}/usr/share/metainfo/${PACKAGE_NAME}.appdata.xml"
render_desktop_file "universal-conversion-hub-uch" "${DEB_ROOT}/usr/share/applications/${DESKTOP_ID}"
cat > "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch" <<'EOF'
#!/bin/sh
exec /opt/universal-conversion-hub-uch/UniversalConversionHub_UCH "$@"
EOF
cat > "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch-updater" <<'EOF'
#!/bin/sh
exec /opt/universal-conversion-hub-uch/UniversalConversionHub_UCH_Updater "$@"
EOF
chmod 755 \
  "${DEB_ROOT}/opt/${PACKAGE_NAME}/${APP_BINARY_NAME}" \
  "${DEB_ROOT}/opt/${PACKAGE_NAME}/${UPDATER_BINARY_NAME}" \
  "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch" \
  "${DEB_ROOT}/usr/bin/universal-conversion-hub-uch-updater"
cat > "${DEB_ROOT}/DEBIAN/control" <<EOF
Package: ${PACKAGE_NAME}
Version: ${PACKAGE_VERSION}
Section: utils
Priority: optional
Architecture: ${DEB_ARCH}
Maintainer: Pugmaster04 <noreply@users.noreply.github.com>
Depends: python3-tk, xdg-utils
Suggests: ffmpeg, pandoc, libreoffice, p7zip-full, imagemagick, aria2
Description: ${APP_NAME}
 Modular desktop utility for conversion, extraction, archives, media workflows,
 storage analysis, and aria2-based downloads.
EOF
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB_PACKAGE"

echo "[7/7] Creating AppImage..."
download_appimagetool
mkdir -p \
  "${APPDIR_ROOT}/usr/bin" \
  "${APPDIR_ROOT}/usr/share/applications" \
  "${APPDIR_ROOT}/usr/share/icons/hicolor/256x256/apps" \
  "${APPDIR_ROOT}/usr/share/metainfo"
cp -f "dist/${APP_BINARY_NAME}" "${APPDIR_ROOT}/usr/bin/${APP_BINARY_NAME}"
cp -f "dist/${UPDATER_BINARY_NAME}" "${APPDIR_ROOT}/usr/bin/${UPDATER_BINARY_NAME}"
cp -f "README.md" "${APPDIR_ROOT}/usr/bin/README.md"
cp -f "PROJECT_PLAN.md" "${APPDIR_ROOT}/usr/bin/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "${APPDIR_ROOT}/usr/bin/update_manifest.example.json"
cp -f "$APP_RUN_TEMPLATE" "${APPDIR_ROOT}/AppRun"
cp -f "$ICON_OUTPUT" "${APPDIR_ROOT}/${PACKAGE_NAME}.png"
cp -f "$ICON_OUTPUT" "${APPDIR_ROOT}/.DirIcon"
cp -f "$ICON_OUTPUT" "${APPDIR_ROOT}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png"
cp -f "$APPDATA_TEMPLATE" "${APPDIR_ROOT}/usr/share/metainfo/${PACKAGE_NAME}.appdata.xml"
render_desktop_file "${APP_BINARY_NAME}" "${APPDIR_ROOT}/${DESKTOP_ID}"
cp -f "${APPDIR_ROOT}/${DESKTOP_ID}" "${APPDIR_ROOT}/usr/share/applications/${DESKTOP_ID}"
chmod 755 "${APPDIR_ROOT}/AppRun" "${APPDIR_ROOT}/usr/bin/${APP_BINARY_NAME}" "${APPDIR_ROOT}/usr/bin/${UPDATER_BINARY_NAME}"
APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE_TOOL" "$APPDIR_ROOT" "$APPIMAGE_PACKAGE"
chmod +x "$APPIMAGE_PACKAGE"

echo "Done."
echo "App binary:      $ROOT/dist/${APP_BINARY_NAME}"
echo "Updater binary:  $ROOT/dist/${UPDATER_BINARY_NAME}"
echo "Staged output:   $ROOT/release_bins"
echo "Linux package:   $ROOT/$TAR_PACKAGE"
echo "Debian package:  $ROOT/$DEB_PACKAGE"
echo "AppImage:        $ROOT/$APPIMAGE_PACKAGE"
