"""System tray icon: open the window, switch custom controls, exit."""

import ctypes
import os
import tempfile
import threading

import pystray

from .icons import app_icon, save_ico

SM_CXSMICON = 49
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10


class _SharpIcon(pystray.Icon):
    """pystray loads the icon at the large icon size and Windows then shrinks
    it for the tray, which blurs it. Load it at the tray size instead."""

    enabled = True

    def _assert_icon_handle(self):
        if self._icon_handle:
            return
        size = ctypes.windll.user32.GetSystemMetrics(SM_CXSMICON) or 16
        handle, path = tempfile.mkstemp(suffix=".ico")
        os.close(handle)
        try:
            save_ico(path, self.enabled, sizes=sorted({size, size * 2}))
            load_image = ctypes.windll.user32.LoadImageW
            load_image.restype = ctypes.c_void_p
            self._icon_handle = load_image(None, path, IMAGE_ICON, size, size, LR_LOADFROMFILE)
        finally:
            os.unlink(path)


class Tray:
    def __init__(self, app):
        self.app = app
        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda: app.after(0, app.show_app), default=True),
            pystray.MenuItem(
                "Custom controls",
                lambda: app.after(0, lambda: app.set_controls_enabled(not app.settings["enable_controls"])),
                checked=lambda item: app.settings["enable_controls"],
            ),
            pystray.MenuItem("Refresh", lambda: app.after(0, app.refresh_device)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", lambda: app.after(0, app.exit_app)),
        )
        self.icon = _SharpIcon("TecknetControl", app_icon(64), "TK-MS029", menu)
        self._enabled_shown = True

    def start(self):
        threading.Thread(target=self.icon.run, name="tray", daemon=True).start()

    def refresh(self):
        enabled = self.app.settings["enable_controls"]
        if enabled != self._enabled_shown:
            self._enabled_shown = enabled
            self.icon.enabled = enabled
            self.icon.icon = app_icon(64, enabled)  # makes pystray reload the handle
        self.icon.update_menu()

    def show_state(self, state):
        if not state.connected:
            title = "TK-MS029 · Disconnected"
        elif state.battery is not None:
            title = f"TK-MS029 · {state.connection} · {state.battery}%"
        else:
            title = f"TK-MS029 · {state.connection}"
        if not self.app.settings["enable_controls"]:
            title += " · Default mode"
        self.icon.title = title

    def notify(self, title, message):
        try:
            self.icon.notify(message, title)
        except Exception:
            pass

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass
