"""Main window: header with the on/off switch, mouse status, controls, app settings.

Every change is saved and applied at once; confirmations appear in the line
at the bottom of the window, never in pop-ups. The look (colours, fonts) is
in ui/theme.py; the side wheel and side button cards in ui/controls_panel.py.
"""

import logging
import sys
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from . import __version__, config, devices, system
from .icons import app_icon
from .tray import Tray
from .ui import theme
from .ui.controls_panel import ControlsPanel
from .ui.widgets import Card, SettingRow

log = logging.getLogger(__name__)

VISIBLE_REFRESH_MS = 5000
TRAY_REFRESH_MS = 15000
LOW_BATTERY = 15
LOW_BATTERY_RESET = 25
IDENTIFY_TIMEOUT_MS = 15000


def resource(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


class App(ctk.CTk):
    def __init__(self, instance, input_thread, start_minimized=False):
        self.settings = config.load_settings()
        self.settings["start_with_windows"] = system.startup_enabled()
        ctk.set_appearance_mode(self.settings["theme"])
        super().__init__(fg_color=theme.BACKGROUND)
        self.input = input_thread
        self.title("Tecknet Control")
        self.geometry("640x720")
        self.minsize(600, 480)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        icon = resource("icon.ico")
        if icon.exists():
            # CustomTkinter sets its own icon shortly after start; set ours after it.
            self.after(250, lambda: self.iconbitmap(str(icon)))

        self.feedback_after_id = None
        self.refresh_after_id = None
        self.identify_after_id = None
        self.refresh_running = False
        self.low_battery_warned = False

        self.build_ui()
        self.tray = Tray(self)
        self.tray.start()
        self.apply_controls()
        self.input.side_button_callback = lambda button: self.after(0, lambda: self.controls.flash_button(button))
        if self.settings["start_with_windows"]:
            system.set_startup(True)  # keeps the path right after an update or a move
        instance.listen(lambda: self.after(0, self.show_app), lambda: self.after(0, self.exit_app))
        self.after(150, self.refresh_device)
        if start_minimized:
            self.withdraw()

    # --- layout -------------------------------------------------------------
    def build_ui(self):
        self.build_header()
        self.content = content = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        content.pack(fill="both", expand=True, padx=(16, 6), pady=(4, 0))
        # CustomTkinter scrolls 20 px per wheel notch on Windows; make it 80.
        content._parent_canvas.configure(yscrollincrement=4)
        self.build_device(content)
        self.controls = ControlsPanel(self, content)
        self.build_app_settings(content)
        self.controls.set_enabled(self.settings["enable_controls"])

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(6, 12))
        self.feedback_var = tk.StringVar()
        self.feedback_label = ctk.CTkLabel(footer, textvariable=self.feedback_var, font=theme.font(12, "bold"), text_color=theme.SUCCESS)
        self.feedback_label.pack(side="left")
        ctk.CTkLabel(footer, text=f"v{__version__}", font=theme.font(11), text_color=theme.MUTED).pack(side="right")

    def build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 10))
        image = ctk.CTkImage(light_image=app_icon(80), dark_image=app_icon(80), size=(40, 40))
        ctk.CTkLabel(header, image=image, text="").pack(side="left")
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(titles, text="Tecknet Control", font=theme.font(20, "bold"), text_color=theme.TEXT).pack(anchor="w")
        ctk.CTkLabel(titles, text="TECKNET TK-MS029", font=theme.font(12), text_color=theme.MUTED).pack(anchor="w")

        switch_box = ctk.CTkFrame(header, fg_color=theme.CARD, border_color=theme.CARD_BORDER, border_width=1, corner_radius=20)
        switch_box.pack(side="right")
        self.enable_var = tk.BooleanVar(value=self.settings["enable_controls"])
        self.enable_text = tk.StringVar()
        ctk.CTkLabel(switch_box, textvariable=self.enable_text, font=theme.font(13, "bold"), text_color=theme.TEXT).pack(side="left", padx=(14, 6), pady=6)
        ctk.CTkSwitch(switch_box, text="", width=46, variable=self.enable_var, command=self.toggle_controls, **theme.switch_style()).pack(side="left", padx=(0, 8))
        self.update_enable_text()

    def build_device(self, parent):
        card = Card(parent, "Mouse")
        card.pack(fill="x", pady=(0, theme.GAP))
        self.status_var = tk.StringVar(value="Checking…")
        self.detail_var = tk.StringVar(value="")
        self.battery_var = tk.StringVar(value="")
        row = card.row()
        status = ctk.CTkFrame(card, fg_color="transparent")
        status.grid(row=row, column=0, columnspan=2, sticky="w", padx=theme.PAD, pady=(0, 4))
        self.dot = ctk.CTkLabel(status, text="●", font=theme.font(16), text_color=theme.IDLE)
        self.dot.pack(side="left", padx=(0, 8))
        texts = ctk.CTkFrame(status, fg_color="transparent")
        texts.pack(side="left")
        ctk.CTkLabel(texts, textvariable=self.status_var, font=theme.font(14, "bold"), text_color=theme.TEXT).pack(anchor="w")
        ctk.CTkLabel(texts, textvariable=self.detail_var, font=theme.font(12), text_color=theme.MUTED).pack(anchor="w")
        battery = ctk.CTkFrame(card, fg_color="transparent")
        battery.grid(row=row, column=2, sticky="e", padx=theme.PAD)
        self.battery_label = ctk.CTkLabel(battery, textvariable=self.battery_var, font=theme.font(22, "bold"), text_color=theme.TEXT)
        self.battery_label.pack(anchor="e")
        self.battery_bar = ctk.CTkProgressBar(battery, width=120, height=6, progress_color=theme.SUCCESS, fg_color=theme.FIELD)
        self.battery_bar.pack(anchor="e", pady=(2, 0))
        self.battery_bar.set(0)
        self.battery_bar.pack_forget()
        card.finish()

    def build_app_settings(self, parent):
        card = Card(parent, "App")
        card.pack(fill="x", pady=(0, theme.GAP))
        self.start_var = tk.BooleanVar(value=self.settings["start_with_windows"])
        self.tray_var = tk.BooleanVar(value=self.settings["minimize_to_tray"])
        self.battery_alert_var = tk.BooleanVar(value=self.settings["low_battery_alert"])
        switches = (
            ("Start with Windows", "Opens in the tray when you sign in", self.start_var),
            ("Keep running when closed", "Controls keep working from the tray", self.tray_var),
            ("Low battery notification", f"At {LOW_BATTERY}% or less", self.battery_alert_var),
        )
        for label, note, variable in switches:
            row = SettingRow(card, label, tk.StringVar(value=note))
            row.place(ctk.CTkSwitch(card, text="", width=46, variable=variable, command=self.update_app_settings, **theme.switch_style()))
        row = SettingRow(card, "Theme")
        self.theme_menu = ctk.CTkOptionMenu(card, values=list(config.THEMES), command=self.change_theme, **{**theme.menu_style(), "width": 140})
        self.theme_menu.set(self.settings["theme"])
        row.place(self.theme_menu)
        # Only needed with a mouse that is not a TK-MS029.
        row = SettingRow(card, "Use another mouse", tk.StringVar(value="Press, then tilt its side wheel"))
        row.place(ctk.CTkButton(card, text="Add mouse", width=110, command=self.identify_mouse, **theme.button_style()))
        card.finish()

    # --- settings -------------------------------------------------------------
    def save(self, message):
        try:
            config.save_settings(self.settings)
        except OSError as error:
            self.show_feedback(f"Could not save settings: {error.strerror}", error=True)
            return False
        self.settings = config.load_settings() | {"start_with_windows": self.settings["start_with_windows"]}
        self.show_feedback(message)
        return True

    def apply_controls(self):
        self.input.apply(config.engine_config(self.settings))
        self.tray.refresh()

    def update_enable_text(self):
        self.enable_text.set("Custom controls on" if self.enable_var.get() else "Custom controls off")

    def toggle_controls(self):
        self.settings["enable_controls"] = bool(self.enable_var.get())
        enabled = self.settings["enable_controls"]
        if self.save("✓ Custom controls on" if enabled else "✓ Normal mouse: horizontal scroll, Back and Forward"):
            self.apply_controls()
        self.controls.set_enabled(enabled)
        self.update_enable_text()

    def set_controls_enabled(self, enabled):
        self.enable_var.set(enabled)
        self.toggle_controls()

    def update_app_settings(self):
        self.settings["start_with_windows"] = bool(self.start_var.get())
        self.settings["minimize_to_tray"] = bool(self.tray_var.get())
        self.settings["low_battery_alert"] = bool(self.battery_alert_var.get())
        if not system.set_startup(self.settings["start_with_windows"]):
            self.show_feedback("Could not change Start with Windows", error=True)
            return
        self.save("✓ Settings saved")

    def change_theme(self, name):
        self.settings["theme"] = name
        ctk.set_appearance_mode(name)
        self.save(f"✓ {name} theme")

    # --- identify mouse ----------------------------------------------------------
    def identify_mouse(self):
        self.show_feedback("Tilt the side wheel or press a side button on the mouse…", persist=True)
        self.input.identify_callback = lambda identifier, kind: self.after(0, lambda: self.identified(identifier))
        if self.identify_after_id:
            self.after_cancel(self.identify_after_id)
        self.identify_after_id = self.after(IDENTIFY_TIMEOUT_MS, self.identify_timeout)

    def identified(self, identifier):
        if self.identify_after_id:
            self.after_cancel(self.identify_after_id)
            self.identify_after_id = None
        if identifier in self.settings["device_ids"]:
            self.show_feedback(f"✓ This mouse is already recognised ({identifier})")
            return
        self.settings["device_ids"] = self.settings["device_ids"] + [identifier]
        if self.save(f"✓ Mouse added ({identifier})"):
            self.apply_controls()

    def identify_timeout(self):
        self.identify_after_id = None
        self.input.identify_callback = None
        self.show_feedback("No mouse input received", error=True)

    # --- feedback ------------------------------------------------------------------
    def show_feedback(self, text, error=False, persist=False):
        if self.feedback_after_id:
            self.after_cancel(self.feedback_after_id)
            self.feedback_after_id = None
        self.feedback_var.set(text)
        self.feedback_label.configure(text_color=theme.ERROR if error else theme.SUCCESS)
        if not persist:
            self.feedback_after_id = self.after(3500, self.clear_feedback)

    def clear_feedback(self):
        self.feedback_after_id = None
        self.feedback_var.set("")

    # --- device ----------------------------------------------------------------------
    def refresh_device(self):
        if self.refresh_after_id:
            self.after_cancel(self.refresh_after_id)
            self.refresh_after_id = None
        if self.refresh_running:
            return
        self.refresh_running = True
        targets = frozenset(self.settings["device_ids"])
        threading.Thread(target=self._read_device, args=(targets,), name="device", daemon=True).start()

    def _read_device(self, targets):
        try:
            state = devices.read_state(targets, self.input.seconds_since_activity("usb"))
        except Exception:
            log.exception("Device check failed")
            state = devices.DeviceState("None", "", False, None)
        self.after(0, lambda: self.show_device(state))

    def show_device(self, state):
        self.refresh_running = False
        if not state.connected:
            self.status_var.set("Not connected")
            self.detail_var.set("Turn the mouse on or move it to wake it up")
        elif state.connection == "Bluetooth":
            self.status_var.set("Connected")
            self.detail_var.set(f"Bluetooth · {state.name}")
        else:
            self.status_var.set("Connected")
            self.detail_var.set("2.4 GHz USB receiver · battery level not reported")
        self.dot.configure(text_color=theme.SUCCESS if state.connected else theme.IDLE)
        if state.battery is None:
            self.battery_var.set("")
            self.battery_bar.pack_forget()
        else:
            level = max(0, min(100, state.battery))
            self.battery_var.set(f"{level}%")
            self.battery_bar.configure(progress_color=theme.BATTERY_LOW if level <= LOW_BATTERY else theme.SUCCESS)
            self.battery_bar.set(level / 100)
            self.battery_bar.pack(anchor="e", pady=(2, 0))
            self.check_low_battery(level)
        self.tray.show_state(state)
        interval = TRAY_REFRESH_MS if self.state() == "withdrawn" else VISIBLE_REFRESH_MS
        self.refresh_after_id = self.after(interval, self.refresh_device)

    def check_low_battery(self, battery):
        if battery >= LOW_BATTERY_RESET:
            self.low_battery_warned = False
        elif battery <= LOW_BATTERY and not self.low_battery_warned and self.settings["low_battery_alert"]:
            self.low_battery_warned = True
            self.tray.notify("TK-MS029 battery low", f"{battery}% left. Charge the mouse soon.")

    # --- window ------------------------------------------------------------------------
    def show_app(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.refresh_device()

    def on_close(self):
        if self.tray_var.get():
            self.withdraw()
        else:
            self.exit_app()

    def exit_app(self):
        self.input.side_button_callback = None
        self.tray.stop()
        self.input.stop()
        self.destroy()
