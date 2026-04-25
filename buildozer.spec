[app]

# ── Identity ────────────────────────────────────────────────────────────────
title           = AdSync Helper
package.name    = adsynchelper
package.domain  = com.adsync
version         = 1.0

# ── Source ──────────────────────────────────────────────────────────────────
source.dir       = .
source.include_exts = py,png,jpg,kv,atlas,json

# ── Python requirements ─────────────────────────────────────────────────────
requirements = python3,kivy==2.3.0,android,pyjnius

# ── Orientation & UI ────────────────────────────────────────────────────────
orientation     = portrait
fullscreen      = 0

# ── Android target ──────────────────────────────────────────────────────────
android.minapi          = 26
android.api             = 34
android.ndk             = 25b
android.sdk             = 34
android.archs           = arm64-v8a, armeabi-v7a

# ── Permissions ─────────────────────────────────────────────────────────────
android.permissions =
    INTERNET,
    FOREGROUND_SERVICE,
    FOREGROUND_SERVICE_DATA_SYNC,
    RECEIVE_BOOT_COMPLETED,
    WAKE_LOCK,
    REQUEST_INSTALL_PACKAGES

# ── Services ────────────────────────────────────────────────────────────────
# Foreground service keeps the proxy alive even with the screen off
android.services = AdSyncService:service/boot_service.py:foreground

# ── Boot receiver ───────────────────────────────────────────────────────────
# Declared in AndroidManifest so BOOT_COMPLETED wakes the app
android.manifest_attributes =
    uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"

android.add_manifest_xml =
    <receiver android:name=".BootBroadcastReceiver"
              android:enabled="true"
              android:exported="true">
        <intent-filter android:priority="1000">
            <action android:name="android.intent.action.BOOT_COMPLETED"/>
            <action android:name="android.intent.action.QUICKBOOT_POWERON"/>
            <category android:name="android.intent.category.DEFAULT"/>
        </intent-filter>
    </receiver>

# ── Notification channel (required Android 8+) ──────────────────────────────
android.meta_data = notification_channel_id:adsync_channel

# ── Icons & splash ──────────────────────────────────────────────────────────
# icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/splash.png

# ── Build ────────────────────────────────────────────────────────────────────
[buildozer]
log_level = 2
warn_on_root = 1
