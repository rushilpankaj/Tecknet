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
FLASH_MS = 300
KIND_NAMES = {"click": "click", "double": "double click", "hold": "hold"}
GESTURE_NAMES = {"left": "Move left", "right": "Move right", "up": "Move up", "down": "Move down"}
HOLD_LABELS = {actions.DO_NOTHING: "Nothing", actions.HOLD_GESTURES: "Gestures", actions.HOLD_PRECISION: "Precision mode"}


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

        row = SettingRow(card, "Faster when turned quickly", tk.StringVar(value="Volume moves up to 3 steps per notch"))
        self.accelerate_var = tk.BooleanVar(value=self.settings["wheel_acceleration"])
        accelerate = ctk.CTkSwitch(card, text="", width=46, variable=self.accelerate_var, command=self.on_wheel_change, **theme.switch_style())
        row.place(accelerate)

        row = SettingRow(card, "Reverse direction")
        self.invert_var = tk.BooleanVar(value=self.settings["invert_wheel"])
        invert = ctk.CTkSwitch(card, text="", width=46, variable=self.invert_var, command=self.on_wheel_change, **theme.switch_style())
        row.place(invert)
        card.finish()
        self.widgets += [self.wheel_menu, accelerate, invert]
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
        self.settings["wheel_acceleration"] = bool(self.accelerate_var.get())
        self.update_wheel_notes()
        if self.app.save(f"✓ Side wheel: {self.settings['wheel_preset']}"):
            self.app.apply_controls()

    # --- side buttons ------------------------------------------------------------
    def build_buttons(self, parent):
        card = Card(parent, "Side buttons", "Press a side button to see which one it is")
        card.pack(fill="x", pady=(0, theme.GAP))
        SectionLabel(card, "Click")
        for button in (1, 2):
            self.add_button_row(card, button, f"{button}_click")
        SectionLabel(card, "Double click")
        for button in (1, 2):
            self.add_button_row(card, button, f"{button}_double")

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
        marks = ctk.CTkFrame(card, fg_color="transparent", width=168, height=16)
        marks.pack_propagate(False)
        for text, side in (("Fast", "left"), ("Slow", "right")):
            ctk.CTkLabel(marks, text=text, font=theme.font(11), text_color=theme.MUTED, height=14).pack(side=side)
        marks.grid(row=card.row(), column=2, sticky="e", padx=(0, theme.PAD + 62))
        self.widgets.append(slider)
        self.update_wait_note()

        SectionLabel(card, "Hold", "about half a second")
        for button in (1, 2):
            self.add_button_row(card, button, f"{button}_hold")
        SectionLabel(card, "Gestures", "hold a button set to Gestures and move the mouse")
        for direction, label in GESTURE_NAMES.items():
            row = SettingRow(card, label)
            self.add_menu(card, row, f"gesture_{direction}")
        card.finish()

    def add_button_row(self, card, button, slot):
        row = SettingRow(card, BUTTON_NAMES[button], tk.StringVar(value=BUTTON_PLACES[button]))
        self.button_rows[button].append(card.grid_slaves(row=row.row, column=0)[0])
        self.add_menu(card, row, slot)

    def add_menu(self, card, row, slot):
        kind = config.slot_kind(slot)
        others = [(a, a) for a in actions.BUTTON_ACTIONS if a != actions.DO_NOTHING]
        nothing = (actions.DO_NOTHING, actions.DO_NOTHING)
        if kind == "click":
            choices = [(NORMAL_LABELS[int(slot[0])], actions.NORMAL_CLICK)] + others + [nothing]
        elif kind == "hold":
            choices = [(HOLD_LABELS[a], a) for a in HOLD_LABELS] + others
        else:
            choices = [nothing] + others
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
        if config.slot_kind(slot) == "hold" and action in HOLD_LABELS:
            return HOLD_LABELS[action]
        if action == actions.OPEN_PROGRAM:
            return f"Open {data.get('program_name') or 'app'}"
        if action == actions.SHORTCUT:
            return f"Keys: {data.get('keys_label') or 'shortcut'}"
        return action

    def show_slot(self, slot):
        self.menus[slot].show(self.slot_text(slot))

    def set_slot(self, slot, data):
        self.settings["buttons"][slot] = data
        kind = config.slot_kind(slot)
        if kind == "gesture":
            title = f"Gesture {GESTURE_NAMES[slot.split('_')[1]].lower()}"
        else:
            title = f"{BUTTON_NAMES[int(slot[0])]} {KIND_NAMES[kind]}"
        if self.app.save(f"✓ {title}: {self.slot_text(slot, data)}"):
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
        self.speed_label.configure(text=f"{int(value)} ms", text_color=theme.ACCENT)

    def on_speed_release(self):
        self.speed_label.configure(text_color=theme.TEXT)
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
