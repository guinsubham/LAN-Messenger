#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install Python 3 from https://www.python.org/downloads/macos/"
  exit 1
fi

python3 -m pip install --user --upgrade pip setuptools wheel

python3 -m pip install --user --only-binary=:all: --upgrade \
  pyinstaller

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name LANMessenger \
  --add-data "assets/app_icon.png:assets" \
  --add-data "assets/app_icon.ico:assets" \
  --add-data "assets/Incoming_msg.wav:assets" \
  --add-data "assets/File_received.wav:assets" \
  --add-data "assets/New_User_Online.wav:assets" \
  --add-data "assets/typing_indicator_preview.gif:assets" \
  p2p_chat.py

echo
echo "Mac app created at: dist/LANMessenger.app"
echo "Command-line executable created at: dist/LANMessenger/LANMessenger"
echo
echo "To open it: double-click dist/LANMessenger.app"
