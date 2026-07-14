#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install Python 3 from https://www.python.org/downloads/macos/"
  exit 1
fi

python3 -m pip install --user --upgrade pip setuptools wheel
python3 -m pip install --user --only-binary=:all: --upgrade pyinstaller tkinterdnd2

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --name LANMessengerDebug \
  --collect-all tkinterdnd2 \
  --hidden-import tkinterdnd2 \
  --add-data "assets/app_icon.png:assets" \
  --add-data "assets/app_icon.ico:assets" \
  --add-data "assets/Incoming_msg.wav:assets" \
  --add-data "assets/File_received.wav:assets" \
  --add-data "assets/New_User_Online.wav:assets" \
  --add-data "assets/typing_indicator_preview.gif:assets" \
  p2p_chat.py

echo
echo "Debug build created at: dist/LANMessengerDebug/LANMessengerDebug"
echo "Run it from Terminal with:"
echo "dist/LANMessengerDebug/LANMessengerDebug"
