"""
AdSync Helper - Main Kivy Application
Residential proxy app using SOCKS5 on port 8080
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.utils import platform
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp, sp

import threading
import socket
import time
import json
import urllib.request
from datetime import datetime

# Android-specific imports (only on device)
if platform == 'android':
    from android.permissions import request_permissions, Permission, check_permission
    from android import mActivity
    from jnius import autoclass

    # Java classes for foreground service & notification
    PythonService  = autoclass('org.kivy.android.PythonService')
    Intent         = autoclass('android.content.Intent')
    PendingIntent  = autoclass('android.app.PendingIntent')
    Context        = autoclass('android.content.Context')
    NotificationBuilder = autoclass('androidx.core.app.NotificationCompat$Builder')
    NotificationManager = autoclass('android.app.NotificationManager')
    NotificationChannel = autoclass('android.app.NotificationChannel')
    Build           = autoclass('android.os.Build')


# ─── Colours ────────────────────────────────────────────────────────────────
BG_DARK   = (0.102, 0.102, 0.18,  1)   # #1a1a2e
ACCENT    = (0.486, 0.624, 0.961, 1)   # #7c9ff5
GREEN     = (0.18,  0.80,  0.44,  1)   # #2ecc71
RED       = (0.753, 0.224, 0.169, 1)   # #c0392b
WHITE     = (1,     1,     1,     1)
MUTED     = (0.533, 0.533, 0.667, 1)   # #8888aa
CARD_BG   = (0.95,  0.96,  1.0,   1)


# ─── Heartbeat thread ───────────────────────────────────────────────────────
class HeartbeatThread(threading.Thread):
    """Posts a heartbeat every 60 s to let the backend know the node is alive."""

    HEARTBEAT_URL = "https://your-backend.example.com:8080/api/heartbeat"   # ← change

    def __init__(self, device_id, stop_event):
        super().__init__(daemon=True)
        self.device_id  = device_id
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            try:
                payload = json.dumps({
                    "device_id": self.device_id,
                    "timestamp": int(time.time()),
                    "proxy_port": 8080,
                    "status": "active"
                }).encode()
                req = urllib.request.Request(
                    self.HEARTBEAT_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass   # silent – no connectivity should not crash the node
            self.stop_event.wait(60)


# ─── SOCKS5 proxy ───────────────────────────────────────────────────────────
class Socks5Server(threading.Thread):
    """Minimal SOCKS5 proxy that tunnels TCP connections through this device."""

    SOCKS5_VER = 5
    PORT       = 8080

    def __init__(self, stop_event):
        super().__init__(daemon=True)
        self.stop_event = stop_event
        self.server_sock = None

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _recv_exact(sock, n):
        data = b''
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def _handle_client(self, client):
        try:
            # Greeting
            header = self._recv_exact(client, 2)
            ver, nmethods = header[0], header[1]
            if ver != self.SOCKS5_VER:
                return
            self._recv_exact(client, nmethods)
            client.sendall(b'\x05\x00')   # no auth

            # Request
            req = self._recv_exact(client, 4)
            if req[1] != 0x01:            # CONNECT only
                client.sendall(b'\x05\x07\x00\x01' + b'\x00'*6)
                return

            atype = req[3]
            if atype == 0x01:             # IPv4
                addr = socket.inet_ntoa(self._recv_exact(client, 4))
            elif atype == 0x03:           # Domain
                dlen = self._recv_exact(client, 1)[0]
                addr = self._recv_exact(client, dlen).decode()
            elif atype == 0x04:           # IPv6
                addr = socket.inet_ntop(socket.AF_INET6, self._recv_exact(client, 16))
            else:
                return

            port = int.from_bytes(self._recv_exact(client, 2), 'big')

            # Connect to target
            remote = socket.create_connection((addr, port), timeout=10)
            bind_addr = remote.getsockname()
            reply = (b'\x05\x00\x00\x01'
                     + socket.inet_aton(bind_addr[0])
                     + bind_addr[1].to_bytes(2, 'big'))
            client.sendall(reply)

            # Relay
            self._relay(client, remote)
        except Exception:
            pass
        finally:
            try: client.close()
            except: pass

    @staticmethod
    def _relay(a, b):
        a.setblocking(False)
        b.setblocking(False)
        import select
        sockets = [a, b]
        while True:
            r, _, e = select.select(sockets, [], sockets, 1)
            if e:
                break
            for s in r:
                data = None
                try:
                    data = s.recv(4096)
                except:
                    pass
                if not data:
                    return
                target = b if s is a else a
                try:
                    target.sendall(data)
                except:
                    return

    # ── main loop ────────────────────────────────────────────────────────────
    def run(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(('0.0.0.0', self.PORT))
        self.server_sock.listen(50)
        self.server_sock.settimeout(1.0)
        while not self.stop_event.is_set():
            try:
                client, _ = self.server_sock.accept()
                t = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break
        try: self.server_sock.close()
        except: pass

    def stop(self):
        self.stop_event.set()


# ─── Android foreground service helper ──────────────────────────────────────
def start_foreground_service():
    if platform != 'android':
        return
    try:
        ctx = mActivity.getApplicationContext()
        channel_id = "adsync_channel"

        if Build.VERSION.SDK_INT >= 26:
            ch = NotificationChannel(
                channel_id,
                "AdSync Helper",
                NotificationManager.IMPORTANCE_LOW
            )
            nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE)
            nm.createNotificationChannel(ch)

        intent     = Intent(ctx, mActivity.getClass())
        pi         = PendingIntent.getActivity(ctx, 0, intent,
                         PendingIntent.FLAG_IMMUTABLE)

        notification = (NotificationBuilder(ctx, channel_id)
                        .setContentTitle("AdSync Helper")
                        .setContentText("Sharing internet for Dev")
                        .setSmallIcon(ctx.getApplicationInfo().icon)
                        .setContentIntent(pi)
                        .setOngoing(True)
                        .build())

        PythonService.mService.startForeground(1, notification)
    except Exception as e:
        print(f"[FG Service] {e}")


# ─── UI ─────────────────────────────────────────────────────────────────────
class AdSyncUI(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.sharing      = False
        self.stop_event   = None
        self.socks_server = None
        self.heartbeat    = None
        self.mb_used      = 12.0
        self.device_id    = self._get_device_id()

        with self.canvas.before:
            Color(*BG_DARK)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self._build_ui()
        Clock.schedule_interval(self._tick, 1)

    # ── layout ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.add_widget(Widget(size_hint_y=0.06))

        # ── Header ──────────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=0.12, padding=[dp(20), 0])
        title = Label(
            text="📡  AdSync Helper",
            font_size=sp(22),
            color=ACCENT,
            bold=True,
            halign='center'
        )
        hdr.add_widget(title)
        self.add_widget(hdr)

        # ── Info card ────────────────────────────────────────────────────────
        card = BoxLayout(
            orientation='vertical',
            size_hint=(0.88, None),
            height=dp(90),
            pos_hint={'center_x': 0.5},
            padding=dp(14),
            spacing=dp(6)
        )
        with card.canvas.before:
            Color(0.941, 0.957, 1.0, 1)
            self.card_rect = RoundedRectangle(
                pos=card.pos, size=card.size, radius=[dp(14)]
            )
        card.bind(pos=lambda *a: setattr(self.card_rect, 'pos', card.pos),
                  size=lambda *a: setattr(self.card_rect, 'size', card.size))

        card.add_widget(Label(
            text="This app shares your internet connection",
            font_size=sp(13), bold=True,
            color=(0.165, 0.227, 0.486, 1),
            halign='left', valign='middle',
            size_hint_y=None, height=dp(22),
            text_size=(Window.width * 0.8, None)
        ))
        card.add_widget(Label(
            text="Your connection is used on Dev's behalf.",
            font_size=sp(12),
            color=(0.333, 0.333, 0.4, 1),
            halign='left', valign='middle',
            size_hint_y=None, height=dp(20),
            text_size=(Window.width * 0.8, None)
        ))
        self.add_widget(card)

        self.add_widget(Widget(size_hint_y=0.04))

        # ── Data counter ─────────────────────────────────────────────────────
        data_box = BoxLayout(
            size_hint=(0.88, None), height=dp(70),
            pos_hint={'center_x': 0.5},
            padding=dp(14), spacing=dp(10)
        )
        with data_box.canvas.before:
            Color(0.93, 0.95, 1.0, 1)
            self.data_rect = RoundedRectangle(
                pos=data_box.pos, size=data_box.size, radius=[dp(14)]
            )
        data_box.bind(pos=lambda *a: setattr(self.data_rect, 'pos', data_box.pos),
                      size=lambda *a: setattr(self.data_rect, 'size', data_box.size))

        data_box.add_widget(Label(
            text="📶", font_size=sp(24),
            size_hint_x=0.2
        ))
        info = BoxLayout(orientation='vertical')
        info.add_widget(Label(
            text="Data used today",
            font_size=sp(11), color=MUTED,
            halign='left', valign='middle',
            text_size=(Window.width * 0.55, None)
        ))
        self.data_label = Label(
            text=f"{self.mb_used:.1f} MB",
            font_size=sp(20), bold=True,
            color=(0.1, 0.1, 0.15, 1),
            halign='left', valign='middle',
            text_size=(Window.width * 0.55, None)
        )
        info.add_widget(self.data_label)
        data_box.add_widget(info)
        self.add_widget(data_box)

        self.add_widget(Widget(size_hint_y=0.04))

        # ── Status dot ───────────────────────────────────────────────────────
        self.status_label = Label(
            text="⚫  Not sharing",
            font_size=sp(13),
            color=MUTED,
            size_hint_y=0.07
        )
        self.add_widget(self.status_label)

        # ── Main button ──────────────────────────────────────────────────────
        btn_wrap = BoxLayout(
            size_hint=(0.88, None), height=dp(56),
            pos_hint={'center_x': 0.5}
        )
        self.main_btn = Button(
            text="START SHARING",
            font_size=sp(16),
            bold=True,
            background_normal='',
            background_color=(*BG_DARK[:3], 1),
            color=WHITE
        )
        self.main_btn.bind(on_release=self.toggle_sharing)
        btn_wrap.add_widget(self.main_btn)
        self.add_widget(btn_wrap)

        self.add_widget(Widget(size_hint_y=0.04))

        # ── Disclaimer ───────────────────────────────────────────────────────
        self.add_widget(Label(
            text="By tapping Start Sharing you agree to share\nyour internet bandwidth. You can stop anytime.",
            font_size=sp(11),
            color=MUTED,
            halign='center',
            size_hint_y=0.1,
            text_size=(Window.width * 0.8, None)
        ))

        self.add_widget(Widget(size_hint_y=0.06))

    # ── helpers ──────────────────────────────────────────────────────────────
    def _update_bg(self, *a):
        self.bg_rect.pos  = self.pos
        self.bg_rect.size = self.size

    def _get_device_id(self):
        try:
            if platform == 'android':
                Settings = autoclass('android.provider.Settings$Secure')
                return Settings.getString(
                    mActivity.getContentResolver(),
                    Settings.ANDROID_ID
                )
        except:
            pass
        import hashlib, uuid
        return hashlib.md5(str(uuid.getnode()).encode()).hexdigest()[:16]

    def _tick(self, dt):
        if self.sharing:
            self.mb_used += 0.003          # simulated; replace with real counter
            self.data_label.text = f"{self.mb_used:.1f} MB"

    # ── toggle ───────────────────────────────────────────────────────────────
    def toggle_sharing(self, *a):
        if not self.sharing:
            self._start_sharing()
        else:
            self._stop_sharing()

    def _start_sharing(self):
        # Android permissions
        if platform == 'android':
            request_permissions([
                Permission.INTERNET,
                Permission.FOREGROUND_SERVICE,
                Permission.RECEIVE_BOOT_COMPLETED,
                Permission.WAKE_LOCK,
            ])
            start_foreground_service()

        self.stop_event   = threading.Event()
        self.socks_server = Socks5Server(self.stop_event)
        self.socks_server.start()
        self.heartbeat    = HeartbeatThread(self.device_id, self.stop_event)
        self.heartbeat.start()

        self.sharing = True
        self.main_btn.text             = "STOP SHARING"
        self.main_btn.background_color = (*RED[:3], 1)
        self.status_label.text         = "🟢  Sharing active"
        self.status_label.color        = GREEN

    def _stop_sharing(self):
        if self.stop_event:
            self.stop_event.set()

        self.sharing = False
        self.main_btn.text             = "START SHARING"
        self.main_btn.background_color = (*BG_DARK[:3], 1)
        self.status_label.text         = "⚫  Not sharing"
        self.status_label.color        = MUTED

        if platform == 'android':
            try:
                PythonService.mService.stopForeground(True)
            except:
                pass


# ─── App entry ──────────────────────────────────────────────────────────────
class AdSyncApp(App):
    def build(self):
        Window.clearcolor = BG_DARK
        return AdSyncUI()

    def on_pause(self):
        return True          # keep running when screen off

    def on_resume(self):
        pass


if __name__ == '__main__':
    AdSyncApp().run()
