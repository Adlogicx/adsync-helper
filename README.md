# AdSync Helper — Build & Deploy Guide

## Project structure

```
AdSyncHelper/
├── main.py                  ← Kivy UI + SOCKS5 proxy + heartbeat
├── service/
│   └── boot_service.py      ← Boot receiver (auto-start after restart)
├── buildozer.spec           ← Full Android build config
└── README.md
```

---

## Prerequisites (one-time setup on Ubuntu / Debian)

```bash
# System deps
sudo apt update && sudo apt install -y \
    git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev \
    libncurses5-dev libncursesw5-dev libtinfo5 \
    cmake libffi-dev libssl-dev

# Python deps
pip3 install --user buildozer cython==0.29.36 kivy==2.3.0

# Android SDK / NDK are downloaded automatically by buildozer on first run
```

---

## Build the APK

```bash
cd AdSyncHelper

# Debug build (fastest, good for testing)
buildozer android debug

# Release build (for distribution)
buildozer android release
```

The APK lands at:
```
bin/AdSync Helper-1.0-arm64-v8a-debug.apk
```

---

## Install on device

```bash
# Enable USB Debugging on the phone first, then:
buildozer android deploy run

# Or install manually via ADB
adb install bin/AdSyncHelper-1.0-arm64-v8a-debug.apk
```

---

## What each file does

### `main.py`
| Class | Role |
|---|---|
| `Socks5Server` | Full SOCKS5 proxy on port 8080. Handles IPv4, IPv6, domain addresses. Relays TCP traffic bidirectionally. |
| `HeartbeatThread` | Posts JSON heartbeat to your backend every 60 s with `device_id`, `timestamp`, `proxy_port`, `status`. |
| `AdSyncUI` | Kivy UI. START/STOP button, data counter, status dot. |
| `start_foreground_service()` | Pins the notification "AdSync Helper — Sharing internet for Dev" so Android never kills the process. |

### `service/boot_service.py`
Starts `Socks5Server` + `HeartbeatThread` headlessly when the phone boots, without showing the UI.

---

## Backend heartbeat endpoint

Your server receives POST requests like this every 60 s:

```json
{
  "device_id": "a3f9c12e...",
  "timestamp": 1745000000,
  "proxy_port": 8080,
  "status": "active"
}
```

Update `HeartbeatThread.HEARTBEAT_URL` in `main.py` to point to your server.

---

## Proxy credentials for buyers

Each device exposes a SOCKS5 proxy at:

```
Host:     <device public IP>   (from heartbeat or STUN)
Port:     8080
Auth:     none (IP-whitelisted) or add username/password to Socks5Server
Protocol: SOCKS5
```

---

## Permissions explained

| Permission | Why needed |
|---|---|
| `INTERNET` | Run the proxy and send heartbeats |
| `FOREGROUND_SERVICE` | Keep proxy alive with screen off |
| `RECEIVE_BOOT_COMPLETED` | Auto-start after phone restart |
| `WAKE_LOCK` | Prevent CPU sleep while proxy is active |

---

## Customise

- **Change proxy port** → edit `PORT = 8080` in `Socks5Server`
- **Add auth** → in `_handle_client`, replace `b'\x05\x00'` with username/password handshake
- **Heartbeat URL** → edit `HEARTBEAT_URL` in `HeartbeatThread`
- **App icon** → drop `icon.png` (512×512) in `assets/` and uncomment `icon.filename` in `buildozer.spec`
