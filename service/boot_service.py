"""
AdSync Boot Receiver Service
Automatically starts the proxy when the phone restarts.
This file is invoked by the Android BOOT_COMPLETED broadcast.
"""

from kivy.utils import platform

if platform == 'android':
    from jnius import autoclass, PythonJavaClass, java_method

    PythonService = autoclass('org.kivy.android.PythonService')

    class BootReceiver(PythonJavaClass):
        """Broadcast receiver that catches BOOT_COMPLETED and restarts the proxy."""

        __javainterfaces__ = ['android/content/BroadcastReceiver']
        __javacontext__    = 'app'

        @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
        def onReceive(self, context, intent):
            Intent = autoclass('android.content.Intent')
            action = intent.getAction()
            if action == 'android.intent.action.BOOT_COMPLETED':
                service_intent = Intent(context,
                    autoclass('org.adsynchelper.ServiceEntrypoint'))
                context.startForegroundService(service_intent)


def start_service_on_boot():
    """Called by the Kivy service entry point at boot."""
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))

    # Import and run the proxy + heartbeat directly (no UI needed at boot)
    import threading
    from main import Socks5Server, HeartbeatThread, start_foreground_service
    import hashlib, uuid

    device_id  = hashlib.md5(str(uuid.getnode()).encode()).hexdigest()[:16]
    stop_event = threading.Event()

    start_foreground_service()

    socks = Socks5Server(stop_event)
    socks.start()

    hb = HeartbeatThread(device_id, stop_event)
    hb.start()

    # Keep the service thread alive
    import time
    while True:
        time.sleep(60)
