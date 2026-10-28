"""The "Side wheel" and "Side buttons" cards.

Every change is saved and applied at once through the app (app.save and
app.apply_controls). Pressing a side button on the mouse lights up its rows,
so it is clear which button is which.
"""

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from .. import actions, config
from . import theme
from .app_picker import AppPicker
from .shortcut_dialog import ShortcutDialog
from .widgets import ActionMenu, Card, SectionLabel, SettingRow

BUTTON_NAMES = {1: "Back button", 2: "Forward button"}
BUTTON_PLACES = {1: "Rear side button", 2: "Front side button"}
NORMAL_LABELS = {1: "Back (normal)", 2: "Forward (normal)"}
OPEN_APP_LABEL = "Open app…"
SHORTCUT_LABEL = "Keyboard shortcut…"
FLASH_MS = 700


class ControlsPanel:
    def __init__(self, app, parent):
        self.app = app
        self.widgets = []
        self.menus = {}
        self.button_rows = {1: [], 2: []}
        self.flash_after = {1: None, 2: None}
        self.build_wheel(parent)
        self.build_buttons(parent)

    @property
    def settings(self):
        return self.app.settings

    # --- side wheel -------------------------------------------------------------
    def build_wheel(self, parent):
        card = Card(parent, "Side wheel", "Tilt the wheel left or right")
        card.pack(fill="x", pady=(0, theme.GAP))
        self.wheel_note = tk.StringVar()
        row = SettingRow(card, "Action", self.wheel_note)
        self.wheel_menu = ctk.CTkOptionMenu(card, values=list(actions.WHEEL_PRESETS), command=lambda _: self.on_wheel_change(), **theme.menu_style())
        self.wheel_menu.set(self.settings["wheel_preset"])
        row.place(self.wheel_menu)

        row = SettingRow(card, "Reverse direction")
        self.invert_var = tk.BooleanVar(value=self.settings["invert_wheel"])
        invert = ctk.CTkSwitch(card, text="", width=46, variable=self.invert_var, command=self.on_wheel_change, **theme.switch_style())
        row.place(invert)
        card.finish()
        self.widgets += [self.wheel_menu, invert]
        self.update_wheel_notes()

    def update_wheel_notes(self):
        pair = actions.WHEEL_PRESETS[self.settings["wheel_preset"]]
        if pair is None:
            self.wheel_note.set("Normal horizontal scrolling")
        else:
            left, right = reversed(pair) if self.settings["invert_wheel"] else pair
            self.wheel_note.set(f"Left: {left}  ·  Right: {right}")

    def on_wheel_change(self):
        self.settings["wheel_preset"] = self.wheel_menu.get()
        self.settings["invert_wheel"] = bool(self.invert_var.get())
        self.update_wheel_notes()
        if self.app.save(f"✓ Side wheel: {self.settings['wheel_preset']}"):
            self.app.apply_controls()

    # --- side buttons ------------------------------------------------------------
    def build_buttons(self, parent):
        card = Card(parent, "Side buttons", "Press a side button to see which one it is")
        card.pack(fill="x", pady=(0, theme.GAP))
        SectionLabel(card, "Click")
        for button in (1, 2):
            self.add_slot_row(card, button, f"{button}_click")
        SectionLabel(card, "Double click")
        for button in (1, 2):
            self.add_slot_row(card, button, f"{button}_double")

        self.wait_note = tk.StringVar()
        row = SettingRow(card, "Double-click wait", self.wait_note)
        low, high = config.DOUBLE_CLICK_RANGE
        holder = ctk.CTkFrame(card, fg_color="transparent")
        self.speed_var = tk.IntVar(value=self.settings["double_click_ms"])
        self.speed_label = ctk.CTkLabel(holder, text="", width=56, font=theme.font(13, "bold"), text_color=theme.TEXT)
        slider = ctk.CTkSlider(holder, from_=low, to=high, number_of_steps=(high - low) // 10, width=168,
                               variable=self.speed_var, command=self.on_speed_move,
                               progress_color=theme.ACCENT, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                               fg_color=theme.FIELD)
        slider.pack(side="left")
        self.speed_label.pack(side="left", padx=(6, 0))
        slider.bind("<ButtonRelease-1>", lambda _event: self.on_speed_release())
        row.place(holder)
        card.finish()
        self.widgets.append(slider)
        self.update_wait_note()

    def add_slot_row(self, card, button, slot):
        row = SettingRow(card, BUTTON_NAMES[button], tk.StringVar(value=BUTTON_PLACES[button]))
        self.button_rows[button].append(card.grid_slaves(row=row.row, column=0)[0])
        choices = [(a, a) for a in actions.BUTTON_ACTIONS]
        if config.slot_kind(slot) == "click":
            choices = [(NORMAL_LABELS[button], actions.NORMAL_CLICK)] + [c for c in choices if c[1] != actions.DO_NOTHING] + [(actions.DO_NOTHING, actions.DO_NOTHING)]
        else:
            choices = [(actions.DO_NOTHING, actions.DO_NOTHING)] + [c for c in choices if c[1] != actions.DO_NOTHING]
        choices += [(OPEN_APP_LABEL, actions.OPEN_PROGRAM), (SHORTCUT_LABEL, actions.SHORTCUT)]
        menu = ActionMenu(
            card, choices, specials={actions.OPEN_PROGRAM, actions.SHORTCUT},
            on_change=lambda value: self.set_slot(slot, {"action": value}),
            on_special=lambda value: self.ask_custom(slot, value),
        )
        row.place(menu)
        self.menus[slot] = menu
        self.widgets.append(menu)
        self.show_slot(slot)

    def slot_text(self, slot, data=None):
        data = data or self.settings["buttons"][slot]
        action = data["action"]
        if action == actions.NORMAL_CLICK:
            return NORMAL_LABELS[int(slot[0])]
        if action == actions.OPEN_PROGRAM:
            return f"Open {data.get('program_name') or 'app'}"
        if action == actions.SHORTCUT:
            return f"Keys: {data.get('keys_label') or 'shortcut'}"
        return action

    def show_slot(self, slot):
        self.menus[slot].show(self.slot_text(slot))

    def set_slot(self, slot, data):
        self.settings["buttons"][slot] = data
        button = int(slot[0])
        kind = "click" if config.slot_kind(slot) == "click" else "double click"
        if self.app.save(f"✓ {BUTTON_NAMES[button]} {kind}: {self.slot_text(slot, data)}"):
            self.app.apply_controls()
        self.show_slot(slot)
        self.update_wait_note()

    def ask_custom(self, slot, value):
        cancel = lambda: self.show_slot(slot)  # noqa: E731
        if value == actions.OPEN_PROGRAM:
            AppPicker(self.app, lambda path, name: self.set_program(slot, path, name), cancel)
        else:
            ShortcutDialog(self.app, lambda keys, label: self.set_slot(slot, {"action": actions.SHORTCUT, "keys": keys, "keys_label": label}), cancel)

    def set_program(self, slot, path, name):
        if not actions.valid_program(path):
            self.app.show_feedback("Choose an existing .exe or .lnk file on this PC", error=True)
            self.show_slot(slot)
            return
        self.set_slot(slot, {"action": actions.OPEN_PROGRAM, "program": str(Path(path)), "program_name": name})

    # --- double-click wait ---------------------------------------------------------
    def on_speed_move(self, value):
        self.speed_label.configure(text=f"{int(value)} ms")

    def on_speed_release(self):
        self.settings["double_click_ms"] = int(self.speed_var.get())
        self.update_wait_note()
        if self.app.save(f"✓ Double-click wait {self.settings['double_click_ms']} ms"):
            self.app.apply_controls()

    def update_wait_note(self):
        milliseconds = self.settings["double_click_ms"]
        self.speed_label.configure(text=f"{milliseconds} ms")
        waiting = [BUTTON_NAMES[b].split()[0] for b in (1, 2) if config.slot_binding(self.settings, f"{b}_double")]
        if waiting:
            self.wait_note.set(f"{' and '.join(waiting)} wait this long for a second click")
        else:
            self.wait_note.set("Not used: no double-click actions")

    # --- state -----------------------------------------------------------------------
    def set_enabled(self, enabled):
        for widget in self.widgets:
            widget.configure(state="normal" if enabled else "disabled")

    def flash_button(self, button):
        """Light up the rows of the side button that was just pressed."""
        for frame in self.button_rows.get(button, []):
            frame.configure(fg_color=theme.ACCENT_SOFT, corner_radius=6)
        if self.flash_after[button]:
            self.app.after_cancel(self.flash_after[button])
        self.flash_after[button] = self.app.after(FLASH_MS, lambda: self.unflash(button))

    def unflash(self, button):
        self.flash_after[button] = None
        for frame in self.button_rows[button]:
            frame.configure(fg_color="transparent")
