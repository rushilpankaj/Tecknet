"""Window that records a keyboard shortcut (e.g. Ctrl + Shift + T)."""

import tkinter as tk

import customtkinter as ctk

from .. import actions
from . import theme

# Windows virtual-key codes Tk reports for the modifier keys (left/right merged).
_MODIFIERS = {
    16: actions.VK_SHIFT, 160: actions.VK_SHIFT, 161: actions.VK_SHIFT,
    17: actions.VK_CONTROL, 162: actions.VK_CONTROL, 163: actions.VK_CONTROL,
    18: actions.VK_MENU, 164: actions.VK_MENU, 165: actions.VK_MENU,
    91: actions.VK_LWIN, 92: actions.VK_LWIN,
}
_MODIFIER_ORDER = (actions.VK_CONTROL, actions.VK_SHIFT, actions.VK_MENU, actions.VK_LWIN)
_KEY_NAMES = {
    "Prior": "Page Up", "Next": "Page Down", "Return": "Enter", "Escape": "Esc",
    "space": "Space", "BackSpace": "Backspace", "Caps_Lock": "Caps Lock",
    "Print": "Print Screen", "Scroll_Lock": "Scroll Lock", "Num_Lock": "Num Lock",
}


def key_name(keysym):
    if len(keysym) == 1:
        return keysym.upper()
    return _KEY_NAMES.get(keysym, keysym.replace("_", " "))


def shortcut_label(modifiers, main_name):
    return " + ".join([actions.MODIFIER_KEYS[m] for m in _MODIFIER_ORDER if m in modifiers] + [main_name])


class ShortcutDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save, on_cancel):
        super().__init__(parent, fg_color=theme.BACKGROUND)
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.held = set()
        self.keys = None
        self.label = ""
        self.title("Keyboard shortcut")
        self.geometry("400x250")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        ctk.CTkLabel(self, text="Press the shortcut", font=theme.font(16, "bold"), text_color=theme.TEXT).pack(pady=(22, 2))
        ctk.CTkLabel(self, text="For example Ctrl + Shift + T", font=theme.font(12), text_color=theme.MUTED).pack()
        self.preview = tk.StringVar(value="…")
        ctk.CTkLabel(self, textvariable=self.preview, font=theme.font(20, "bold"), text_color=theme.ACCENT,
                     fg_color=theme.ACCENT_SOFT, corner_radius=10, height=48, width=300).pack(pady=16)
        self.win_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Add the Windows key", variable=self.win_var, command=self.refresh_preview,
                        font=theme.font(12), text_color=theme.TEXT, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER).pack()
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=16)
        self.save_button = ctk.CTkButton(buttons, text="Save", width=110, command=self.save, state="disabled", **theme.button_style(primary=True))
        self.save_button.pack(side="right")
        ctk.CTkButton(buttons, text="Cancel", width=110, command=self.cancel, **theme.button_style()).pack(side="right", padx=(0, 8))

        self.bind("<KeyPress>", self.key_down)
        self.bind("<KeyRelease>", self.key_up)
        self.after(120, self.bring_to_front)

    def bring_to_front(self):
        self.lift()
        self.focus_force()
        self.grab_set()

    def key_down(self, event):
        code = event.keycode
        if code in _MODIFIERS:
            self.held.add(_MODIFIERS[code])
            return "break"
        modifiers = set(self.held)
        self.keys = [m for m in _MODIFIER_ORDER if m in modifiers] + [code]
        self.main_name = key_name(event.keysym)
        self.refresh_preview()
        return "break"

    def key_up(self, event):
        self.held.discard(_MODIFIERS.get(event.keycode))
        return "break"

    def current(self):
        if not self.keys:
            return None, ""
        *modifiers, main = self.keys
        modifiers = set(modifiers)
        if self.win_var.get():
            modifiers.add(actions.VK_LWIN)
        keys = [m for m in _MODIFIER_ORDER if m in modifiers] + [main]
        return keys, shortcut_label(modifiers, self.main_name)

    def refresh_preview(self):
        keys, label = self.current()
        valid = keys is not None and actions.valid_shortcut(keys)
        self.preview.set(label if keys else "…")
        self.save_button.configure(state="normal" if valid else "disabled")

    def save(self):
        keys, label = self.current()
        if keys and actions.valid_shortcut(keys):
            self.grab_release()
            self.destroy()
            self.on_save(keys, label)

    def cancel(self):
        self.grab_release()
        self.destroy()
        self.on_cancel()
