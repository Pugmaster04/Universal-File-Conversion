#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
SELF_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
BOOTSTRAP_VENV_DIR="${ROOT}/.venv"
UBUNTU_PREREQ_CMD="sudo apt update && sudo apt install -y python3 python3-venv python3-tk tk-dev dpkg-dev curl"

print_linux_prereq_help() {
  cat >&2 <<EOF
Missing Linux build prerequisites.

Ubuntu / Debian install command:
  ${UBUNTU_PREREQ_CMD}

Notes:
  - Fix unrelated broken third-party apt repositories first if 'apt update' fails.
  - Do not run system-wide 'pip install' for this project on Ubuntu 24.04.
  - This build script creates and uses a repo-local virtual environment automatically.
EOF
}

require_command_or_exit() {
  local command_name="$1"
  local package_hint="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    return 0
  fi
  echo "Missing required command: ${command_name} (${package_hint})" >&2
  print_linux_prereq_help
  exit 1
}

require_python_module_or_exit() {
  local python_bin="$1"
  local module_name="$2"
  local package_hint="$3"
  if "$python_bin" - "$module_name" >/dev/null 2>&1 <<'PY'
import importlib.util
import sys

module_name = sys.argv[1]
sys.exit(0 if importlib.util.find_spec(module_name) else 1)
PY
  then
    return 0
  fi
  echo "Missing required Python module '${module_name}' (${package_hint})" >&2
  print_linux_prereq_help
  exit 1
}

bootstrap_local_virtualenv() {
  require_command_or_exit python3 "python3"
  require_command_or_exit curl "curl"
  require_command_or_exit dpkg-deb "dpkg-dev"
  require_python_module_or_exit python3 venv "python3-venv"
  require_python_module_or_exit python3 tkinter "python3-tk"

  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    return 0
  fi

  if [[ ! -x "${BOOTSTRAP_VENV_DIR}/bin/python" ]]; then
    echo "Creating local build virtual environment in ${BOOTSTRAP_VENV_DIR}..."
    python3 -m venv "${BOOTSTRAP_VENV_DIR}"
  fi

  export VIRTUAL_ENV="${BOOTSTRAP_VENV_DIR}"
  export PATH="${BOOTSTRAP_VENV_DIR}/bin:${PATH}"
  hash -r
  exec /usr/bin/env bash "$SELF_PATH" "$@"
}

bootstrap_local_virtualenv "$@"

PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Active virtual environment is missing python: ${PYTHON_BIN}" >&2
  print_linux_prereq_help
  exit 1
fi

require_command_or_exit curl "curl"
require_command_or_exit dpkg-deb "dpkg-dev"
require_python_module_or_exit "${PYTHON_BIN}" tkinter "python3-tk"

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

PACKAGE_VERSION="$("${PYTHON_BIN}" - <<'PY'
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
DEB_LATEST_PACKAGE="release_bins/${PACKAGE_NAME}_latest_${DEB_ARCH}.deb"
APPIMAGE_PACKAGE="release_bins/${APP_BINARY_NAME}_linux_${ARCH}.AppImage"
APPIMAGE_LATEST_PACKAGE="release_bins/${APP_BINARY_NAME}_linux_latest_${ARCH}.AppImage"
APPIMAGE_TOOL="${APPIMAGE_TOOL_DIR}/appimagetool-${APPIMAGE_ARCH}.AppImage"
APPIMAGE_TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${APPIMAGE_ARCH}.AppImage"

render_desktop_file() {
  local exec_target="$1"
  local output_path="$2"
  sed "s|__EXEC__|${exec_target}|g" "$DESKTOP_TEMPLATE" > "$output_path"
}

build_linux_icon() {
  "${PYTHON_BIN}" - <<'PY'
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

echo "[1/8] Installing Python dependencies..."
"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install -r requirements.txt

echo "[2/8] Building app binary..."
"${PYTHON_BIN}" -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH.spec

echo "[3/8] Building updater binary..."
"${PYTHON_BIN}" -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH_Updater.spec

echo "[4/8] Staging binaries..."
mkdir -p release_bins
rm -f \
  "release_bins/UniversalConversionHub_HCB" \
  "release_bins/UniversalConversionHub_HCB_Updater" \
  "release_bins/UniversalFileUtilitySuite" \
  "release_bins/UniversalFileUtilitySuite_Updater" \
  "$TAR_PACKAGE" \
  "$DEB_PACKAGE" \
  "$DEB_LATEST_PACKAGE" \
  "$APPIMAGE_PACKAGE" \
  "$APPIMAGE_LATEST_PACKAGE" \
  release_bins/*.deb \
  release_bins/*.AppImage
rm -rf "$TAR_DIR" "$APPDIR_ROOT" "$DEB_ROOT" "$BUILD_ROOT/deb-smoke"

cp -f "dist/${APP_BINARY_NAME}" "release_bins/${APP_BINARY_NAME}"
cp -f "dist/${UPDATER_BINARY_NAME}" "release_bins/${UPDATER_BINARY_NAME}"
chmod +x "release_bins/${APP_BINARY_NAME}" "release_bins/${UPDATER_BINARY_NAME}"

echo "[5/8] Creating Linux tar.gz package..."
mkdir -p "$TAR_DIR"
cp -f "dist/${APP_BINARY_NAME}" "$TAR_DIR/${APP_BINARY_NAME}"
cp -f "dist/${UPDATER_BINARY_NAME}" "$TAR_DIR/${UPDATER_BINARY_NAME}"
cp -f "README.md" "$TAR_DIR/README.md"
cp -f "PROJECT_PLAN.md" "$TAR_DIR/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "$TAR_DIR/update_manifest.example.json"
chmod +x "$TAR_DIR/${APP_BINARY_NAME}" "$TAR_DIR/${UPDATER_BINARY_NAME}"
tar -czf "$TAR_PACKAGE" -C release_bins "$TAR_BASENAME"

echo "[6/8] Creating Debian package..."
build_linux_icon
mkdir -p \
  "${DEB_ROOT}/DEBIAN" \
  "${DEB_ROOT}/opt/${PACKAGE_NAME}" \
  "${DEB_ROOT}/usr/bin" \
  "${DEB_ROOT}/usr/share/applications" \
  "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps" \
  "${DEB_ROOT}/usr/share/pixmaps" \
  "${DEB_ROOT}/usr/share/metainfo"
cp -f "dist/${APP_BINARY_NAME}" "${DEB_ROOT}/opt/${PACKAGE_NAME}/${APP_BINARY_NAME}"
cp -f "dist/${UPDATER_BINARY_NAME}" "${DEB_ROOT}/opt/${PACKAGE_NAME}/${UPDATER_BINARY_NAME}"
cp -f "README.md" "${DEB_ROOT}/opt/${PACKAGE_NAME}/README.md"
cp -f "PROJECT_PLAN.md" "${DEB_ROOT}/opt/${PACKAGE_NAME}/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "${DEB_ROOT}/opt/${PACKAGE_NAME}/update_manifest.example.json"
cp -f "$ICON_OUTPUT" "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png"
cp -f "$ICON_OUTPUT" "${DEB_ROOT}/usr/share/pixmaps/${PACKAGE_NAME}.png"
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
cp -f "$DEB_PACKAGE" "$DEB_LATEST_PACKAGE"

echo "[7/8] Creating AppImage..."
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
cp -f "$APPIMAGE_PACKAGE" "$APPIMAGE_LATEST_PACKAGE"
chmod +x "$APPIMAGE_LATEST_PACKAGE"

echo "[8/8] Validating install surface..."
"${PYTHON_BIN}" tools/validate_install_surface.py \
  --readme README.md \
  --artifacts release_bins \
  --required-asset "universal-conversion-hub-uch_latest_${DEB_ARCH}.deb" \
  --required-asset "UniversalConversionHub_UCH_linux_latest_${ARCH}.AppImage"

echo "Done."
echo "App binary:      $ROOT/dist/${APP_BINARY_NAME}"
echo "Updater binary:  $ROOT/dist/${UPDATER_BINARY_NAME}"
echo "Staged output:   $ROOT/release_bins"
echo "Linux package:   $ROOT/$TAR_PACKAGE"
echo "Debian package:  $ROOT/$DEB_PACKAGE"
echo "Debian latest:   $ROOT/$DEB_LATEST_PACKAGE"
echo "AppImage:        $ROOT/$APPIMAGE_PACKAGE"
echo "AppImage latest: $ROOT/$APPIMAGE_LATEST_PACKAGE"
