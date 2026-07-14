# LAN Messenger

A small cross-platform desktop LAN messenger for Windows and Mac. It has no central server: each running app discovers nearby copies on the same local network and sends messages or files directly.

## Requirements

- Python 3.10 or newer
- Both computers must be on the same local network
- The firewall must allow Python to receive local network connections on port `45778`

## Run

```bash
python p2p_chat.py
```

## Build Executables

Windows executable:

```text
dist/LANMessenger.exe
```

Mac executable:

Build it on a Mac by opening Terminal in this folder and running:

```bash
chmod +x build_mac.command
./build_mac.command
```

The Mac app will be created at:

```text
dist/LANMessenger.app
```

The Mac release ZIP will be created at:

```text
dist/LANMessenger-macOS.zip
```

## GitHub Releases and Updates

The in-app `Update` button checks the latest GitHub release at:

```text
https://github.com/guinsubham/LAN-Messenger/releases/latest
```

Attach platform-specific files to each release:

- Windows: `LANMessenger-Windows.exe`
- macOS: `LANMessenger-macOS.zip`

The macOS ZIP must contain `LANMessenger.app`; the `build_mac.command` script creates this ZIP automatically on a Mac.

Open the app on two computers on the same Wi-Fi or wired LAN. Choose a display name, then the main window will show online users and their status. Set your own status from the top bar: `Available`, `AFK`, or `Offline`. Double-click a user to open a separate conversation window where you can send messages, add emojis, switch dark mode on or off, and send files. Windows also supports drag and drop file sending. On Mac, use `Send File(s)` because the third-party drag-and-drop extension is disabled for stability. Today's chat history is shown automatically, and the `History` button shows all older saved history for that user. Web links and local file paths, including Windows paths with spaces, become clickable automatically. Received files show an `Open Location` button.

Notification sounds play when a message arrives, a file is received, or a new user comes online.

On first run, the app asks whether to start automatically when the computer starts. If enabled, Windows creates a Startup shortcut and macOS creates a LaunchAgent. Windows startup launches use tray mode, so the app runs minimized with a tray icon. The macOS build opens normally at startup to avoid unstable third-party menu-bar tray behavior.

Received files are saved to:

```text
~/Documents/LAN Messenger/<Sender_Name>_DD_MM_YYYY
```

## Notes

- This is a local-network peer-to-peer app, not an internet messenger.
- There is no account system and no cloud storage.
- Chat history is stored locally on each device and is not automatically deleted.
- Transfers are not encrypted yet, so use it only on networks you trust.
- If peers do not appear, check that both devices are on the same network and that the operating system firewall allows local network access for Python.
