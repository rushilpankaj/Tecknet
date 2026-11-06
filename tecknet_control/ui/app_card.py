"""The "App" card: start with Windows, tray, battery warning, theme, another mouse."""

import tkinter as tk

import customtkinter as ctk

from .. import config, system
from . import theme
from .mouse_card import LOW_BATTERY
from .widgets import Card, SettingRow

IDENTIFY_TIMEOUT_MS = 15000


class AppCard:
    def __init__(self, app, parent):
        self.app = app
        self.identify_after_id = None
        settings = app.settings
        card = Card(parent, "App")
        card.pack(fill="x", pady=(0, theme.GAP))
        self.start_var = tk.BooleanVar(value=settings["start_with_windows"])
        self.tray_var = tk.BooleanVar(value=settings["minimize_to_tray"])
        self.battery_alert_var = tk.BooleanVar(value=settings["low_battery_alert"])
        switches = (
            ("Start with Windows", "Opens in the tray when you sign in", self.start_var),
            ("Keep running when closed", "Controls keep working from the tray", self.tray_var),
            ("Low battery notification", f"At {LOW_BATTERY}% or less", self.battery_alert_var),
        )
        for label, note, variable in switches:
            row = SettingRow(card, label, tk.StringVar(value=note))
            row.place(ctk.CTkSwitch(card, text="", width=46, variable=variable, command=self.save_switches, **theme.switch_style()))
        row = SettingRow(card, "Theme")
        theme_menu = ctk.CTkOptionMenu(card, values=list(config.THEMES), command=self.change_theme, **{**theme.menu_style(), "width": 140})
        theme_menu.set(settings["theme"])
        row.place(theme_menu)
        # Only needed with a mouse that is not a TK-MS029.
        row = SettingRow(card, "Use another mouse", tk.StringVar(value="Press, then tilt its side wheel"))
        row.place(ctk.CTkButton(card, text="Add mouse", width=110, command=self.identify_mouse, **theme.button_style()))
        card.finish()

    def save_switches(self):
        settings = self.app.settings
        settings["start_with_windows"] = bool(self.start_var.get())
        settings["minimize_to_tray"] = bool(self.tray_var.get())
        settings["low_battery_alert"] = bool(self.battery_alert_var.get())
        if not system.set_startup(settings["start_with_windows"]):
            self.app.show_feedback("Could not change Start with Windows", error=True)
            return
        self.app.save("✓ Settings saved")

    def change_theme(self, name):
        self.app.settings["theme"] = name
        ctk.set_appearance_mode(name)
        self.app.save(f"✓ {name} theme")

    # --- add another mouse: the next wheel tilt or side-button press names it ---
    def identify_mouse(self):
        app = self.app
        app.show_feedback("Tilt the side wheel or press a side button on the mouse…", persist=True)
        app.input.identify_callback = lambda identifier, kind: app.after(0, lambda: self.identified(identifier))
        if self.identify_after_id:
            app.after_cancel(self.identify_after_id)
        self.identify_after_id = app.after(IDENTIFY_TIMEOUT_MS, self.identify_timeout)

    def identified(self, identifier):
        app = self.app
        if self.identify_after_id:
            app.after_cancel(self.identify_after_id)
            self.identify_after_id = None
        if identifier in app.settings["device_ids"]:
            app.show_feedback(f"✓ This mouse is already recognised ({identifier})")
            return
        app.settings["device_ids"] = app.settings["device_ids"] + [identifier]
        if app.save(f"✓ Mouse added ({identifier})"):
            app.apply_controls()

    def identify_timeout(self):
        self.identify_after_id = None
        self.app.input.identify_callback = None
        self.app.show_feedback("No mouse input received", error=True)
