#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ARCH="$(uname -m)"
case "$ARCH" in
  amd64) ARCH="x86_64" ;;
esac
PACKAGE_BASENAME="UniversalConversionHub_UCH_linux_${ARCH}"
PACKAGE_DIR="release_bins/${PACKAGE_BASENAME}"
PACKAGE_ARCHIVE="release_bins/${PACKAGE_BASENAME}.tar.gz"

echo "[1/4] Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[2/4] Building app binary..."
python3 -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH.spec

echo "[3/4] Building updater binary..."
python3 -m PyInstaller --noconfirm --clean UniversalConversionHub_UCH_Updater.spec

echo "[4/5] Staging binaries..."
mkdir -p release_bins
rm -f "release_bins/UniversalConversionHub_HCB" "release_bins/UniversalConversionHub_HCB_Updater" \
      "release_bins/UniversalFileUtilitySuite" "release_bins/UniversalFileUtilitySuite_Updater" \
      "$PACKAGE_ARCHIVE"
rm -rf "$PACKAGE_DIR"
if [[ -f "dist/UniversalConversionHub_UCH" ]]; then
  cp -f "dist/UniversalConversionHub_UCH" "release_bins/UniversalConversionHub_UCH"
  chmod +x "release_bins/UniversalConversionHub_UCH"
fi
if [[ -f "dist/UniversalConversionHub_UCH_Updater" ]]; then
  cp -f "dist/UniversalConversionHub_UCH_Updater" "release_bins/UniversalConversionHub_UCH_Updater"
  chmod +x "release_bins/UniversalConversionHub_UCH_Updater"
fi

echo "[5/5] Creating Linux tar.gz package..."
mkdir -p "$PACKAGE_DIR"
cp -f "dist/UniversalConversionHub_UCH" "$PACKAGE_DIR/UniversalConversionHub_UCH"
cp -f "dist/UniversalConversionHub_UCH_Updater" "$PACKAGE_DIR/UniversalConversionHub_UCH_Updater"
cp -f "README.md" "$PACKAGE_DIR/README.md"
cp -f "PROJECT_PLAN.md" "$PACKAGE_DIR/PROJECT_PLAN.md"
cp -f "update_manifest.example.json" "$PACKAGE_DIR/update_manifest.example.json"
chmod +x "$PACKAGE_DIR/UniversalConversionHub_UCH" "$PACKAGE_DIR/UniversalConversionHub_UCH_Updater"
tar -czf "$PACKAGE_ARCHIVE" -C release_bins "$PACKAGE_BASENAME"

echo "Done."
echo "App binary:      $ROOT/dist/UniversalConversionHub_UCH"
echo "Updater binary:  $ROOT/dist/UniversalConversionHub_UCH_Updater"
echo "Staged output:   $ROOT/release_bins"
echo "Linux package:   $ROOT/$PACKAGE_ARCHIVE"

