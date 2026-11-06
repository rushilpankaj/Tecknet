"""The "Mouse" card: connection and battery level."""

import tkinter as tk

import customtkinter as ctk

from . import theme
from .widgets import Card

LOW_BATTERY = 15  # %; the bar turns amber and the tray warns at this level


class MouseCard:
    def __init__(self, parent):
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
        ctk.CTkLabel(battery, textvariable=self.battery_var, font=theme.font(22, "bold"), text_color=theme.TEXT).pack(anchor="e")
        self.battery_bar = ctk.CTkProgressBar(battery, width=120, height=6, progress_color=theme.SUCCESS, fg_color=theme.FIELD)
        self.battery_bar.set(0)
        card.finish()

    def show(self, state):
        """state: devices.DeviceState."""
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
            self.battery_bar.pack_forget()  # an empty bar would read as 0 %
            return
        level = max(0, min(100, state.battery))
        self.battery_var.set(f"{level}%")
        self.battery_bar.configure(progress_color=theme.BATTERY_LOW if level <= LOW_BATTERY else theme.SUCCESS)
        self.battery_bar.set(level / 100)
        self.battery_bar.pack(anchor="e", pady=(2, 0))
