#!/usr/bin/env bash
#
# build_mac.sh - One-click macOS packaging for VirtualCockroach.
#
# Usage:
#   bash build_mac.sh
#
# Produces dist/VirtualCockroach.app using PyInstaller, with a generated
# icon.icns (from icon.png) and the roach.png asset bundled inside the app.
#
set -e

echo "==> VirtualCockroach macOS build"

# ---------------------------------------------------------------------------
# 1. Python 3
# ---------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install it with:" >&2
  echo "    brew install python3" >&2
  exit 1
fi
PY=python3
echo "==> Using python: $($PY --version 2>&1)"

# ---------------------------------------------------------------------------
# 2. Virtual environment + dependencies
# ---------------------------------------------------------------------------
if [ ! -d "venv" ]; then
  echo "==> Creating virtualenv (venv)"
  "$PY" -m venv venv
fi
# Activate the venv for the remainder of the script.
# shellcheck disable=SC1091
source venv/bin/activate

echo "==> Installing dependencies from requirements.txt"
pip install --upgrade pip
pip install -r requirements.txt

# ---------------------------------------------------------------------------
# 3. Icon: icon.png -> icon.icns via sips + iconutil
# ---------------------------------------------------------------------------
if [ ! -f "icon.png" ]; then
  echo "ERROR: icon.png not found in the current directory." >&2
  echo "       Place an icon.png (>=1024x1024 recommended) next to this script." >&2
  exit 1
fi

echo "==> Generating icon.icns from icon.png"
rm -rf icon.iconset
mkdir icon.iconset
sips -z  16   16    icon.png --out icon.iconset/icon_16x16.png
sips -z  32   32    icon.png --out icon.iconset/icon_16x16@2x.png
sips -z  32   32    icon.png --out icon.iconset/icon_32x32.png
sips -z  64   64    icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128  128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256  256   icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256  256   icon.png --out icon.iconset/icon_256x256.png
sips -z 512  512   icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512  512   icon.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
iconutil --convert icns icon.iconset

# ---------------------------------------------------------------------------
# 4. PyInstaller
# ---------------------------------------------------------------------------
if [ ! -f "roach.png" ]; then
  echo "ERROR: roach.png not found in the current directory." >&2
  echo "       The roach sprite asset must sit next to this script." >&2
  exit 1
fi

echo "==> Running PyInstaller"
pyinstaller --windowed --onefile \
  --icon icon.icns \
  --add-data "roach.png:." \
  --hidden-import pynput.keyboard._darwin \
  --hidden-import pynput.mouse._darwin \
  --hidden-import pynput._util \
  cockroach.py

echo "==> Done. App at: dist/VirtualCockroach.app"
