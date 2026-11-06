"""The "App profiles" card: what the side wheel does in a given program.

A profile is {"app": "chrome.exe", "wheel": "Navigate Tabs"} in settings.json;
the engine looks up the program in front only when the wheel is tilted.
"""

import customtkinter as ctk

from .. import actions, config, winapi
from . import theme
from .widgets import Card


class ProfilesPanel:
    def __init__(self, app, parent):
        self.app = app
        self.widgets = []
        self.card = Card(parent, "App profiles", "The side wheel can do something else in each app")
        self.card.pack(fill="x", pady=(0, theme.GAP))
        self.rows = ctk.CTkFrame(self.card, fg_color="transparent")
        self.rows.grid(row=self.card.row(), column=0, columnspan=3, sticky="ew", padx=theme.PAD)
        self.rows.grid_columnconfigure(0, weight=1)
        self.add_button = ctk.CTkButton(self.card, text="Add app", width=110, command=self.choose_app, **theme.button_style())
        self.add_button.grid(row=self.card.row(), column=0, sticky="w", padx=theme.PAD, pady=(6, 0))
        self.card.finish()
        self.render()

    @property
    def profiles(self):
        return self.app.settings["app_profiles"]

    def render(self):
        for widget in self.rows.winfo_children():
            widget.destroy()
        self.widgets = [self.add_button]
        if not self.profiles:
            ctk.CTkLabel(self.rows, text="Same as above in every app", font=theme.font(12), text_color=theme.MUTED, height=20).grid(row=0, column=0, sticky="w")
        for index, profile in enumerate(self.profiles):
            ctk.CTkLabel(self.rows, text=profile["app"], font=theme.font(13), text_color=theme.TEXT).grid(row=index, column=0, sticky="w", pady=4)
            menu = ctk.CTkOptionMenu(self.rows, values=list(actions.WHEEL_PRESETS), command=lambda value, i=index: self.set_wheel(i, value), **theme.menu_style())
            menu.set(profile["wheel"])
            menu.grid(row=index, column=1, sticky="e", pady=4)
            remove = ctk.CTkButton(self.rows, text="×", width=34, command=lambda i=index: self.remove(i), **theme.button_style())
            remove.grid(row=index, column=2, sticky="e", padx=(8, 0), pady=4)
            self.widgets += [menu, remove]
        self.set_enabled(self.app.settings["enable_controls"])

    def save(self, message):
        if self.app.save(message):
            self.app.apply_controls()
        self.render()

    def set_wheel(self, index, value):
        self.profiles[index]["wheel"] = value
        self.save(f"✓ {self.profiles[index]['app']}: {value}")

    def remove(self, index):
        name = self.profiles.pop(index)["app"]
        self.save(f"✓ Profile removed: {name}")

    def choose_app(self):
        taken = {p["app"] for p in self.profiles}
        programs = [p for p in winapi.open_window_programs() if p not in taken and p != "tecknetcontrol.exe"]
        OpenAppPicker(self.app, programs, self.add)

    def add(self, program):
        if len(self.profiles) >= config.MAX_APP_PROFILES:
            self.app.show_feedback("Too many app profiles", error=True)
            return
        self.profiles.append({"app": program, "wheel": self.app.settings["wheel_preset"]})
        self.save(f"✓ Profile added: {program}")

    def set_enabled(self, enabled):
        for widget in self.widgets:
            widget.configure(state="normal" if enabled else "disabled")


class OpenAppPicker(ctk.CTkToplevel):
    """Pick one of the programs that have a window open right now."""

    def __init__(self, parent, programs, on_select):
        super().__init__(parent, fg_color=theme.BACKGROUND)
        self.on_select = on_select
        self.title("Add app profile")
        self.geometry("360x420")
        self.transient(parent)
        ctk.CTkLabel(self, text="Open the app first, then pick it here", font=theme.font(13), text_color=theme.MUTED).pack(anchor="w", padx=18, pady=(16, 8))
        results = ctk.CTkScrollableFrame(self, fg_color=theme.CARD, corner_radius=theme.RADIUS, border_color=theme.CARD_BORDER, border_width=1)
        results.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        for program in programs:
            ctk.CTkButton(results, text=program, anchor="w", height=34, corner_radius=6, fg_color="transparent",
                          text_color=theme.TEXT, hover_color=theme.FIELD_HOVER, font=theme.font(13),
                          command=lambda p=program: self.select(p)).pack(fill="x", pady=1)
        if not programs:
            ctk.CTkLabel(results, text="No other apps open", text_color=theme.MUTED, font=theme.font(13)).pack(pady=20)
        self.after(120, self.bring_to_front)

    def bring_to_front(self):
        self.lift()
        self.focus_force()
        self.grab_set()

    def select(self, program):
        self.grab_release()
        self.destroy()
        self.on_select(program)
