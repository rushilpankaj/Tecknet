"""Small reusable pieces of the window: cards, rows and the action menu."""

import tkinter as tk

import customtkinter as ctk

from . import theme


class Card(ctk.CTkFrame):
    """A rounded panel with a title and an optional subtitle."""

    def __init__(self, parent, title, subtitle=""):
        super().__init__(parent, fg_color=theme.CARD, border_color=theme.CARD_BORDER, border_width=1, corner_radius=theme.RADIUS)
        self.grid_columnconfigure(1, weight=1)
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=theme.PAD, pady=(14, 4))
        self.header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.header, text=title, font=theme.font(15, "bold"), text_color=theme.TEXT, height=24).grid(row=0, column=0, sticky="w")
        if subtitle:
            ctk.CTkLabel(self.header, text=subtitle, font=theme.font(12), text_color=theme.MUTED, height=18).grid(row=1, column=0, sticky="w")
        self.next_row = 1

    def row(self):
        row = self.next_row
        self.next_row += 1
        return row

    def finish(self):
        # Empty space at the bottom (a spacer frame would paint over the border).
        self.grid_rowconfigure(self.row(), minsize=10)


class SettingRow:
    """Label on the left (with an optional note under it), control on the right."""

    def __init__(self, card, label, note_var=None):
        self.row = card.row()
        text = ctk.CTkFrame(card, fg_color="transparent")
        text.grid(row=self.row, column=0, sticky="w", padx=(theme.PAD, 8), pady=4)
        ctk.CTkLabel(text, text=label, font=theme.font(13), text_color=theme.TEXT, height=20).pack(anchor="w")
        if note_var is not None:
            ctk.CTkLabel(text, textvariable=note_var, font=theme.font(12), text_color=theme.MUTED, justify="left", height=18).pack(anchor="w")
        self.card = card

    def place(self, widget, column=2, padx=None):
        widget.grid(row=self.row, column=column, sticky="e", padx=padx or (0, theme.PAD), pady=4)
        return widget


class SectionLabel:
    """A small heading inside a card, e.g. "Back button"."""

    def __init__(self, card, text, note=""):
        row = card.row()
        frame = ctk.CTkFrame(card, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=theme.PAD, pady=(10, 0))
        ctk.CTkLabel(frame, text=text.upper(), font=theme.font(11, "bold"), text_color=theme.ACCENT, height=20).pack(side="left")
        if note:
            ctk.CTkLabel(frame, text=note, font=theme.font(11), text_color=theme.MUTED).pack(side="left", padx=(8, 0))


class ActionMenu(ctk.CTkOptionMenu):
    """A drop-down of actions where some entries open a dialog ("Open app…").

    choices: list of (label, value). on_change(value) is called for normal
    entries; on_special(value) for the ones in `specials`, which must call
    show() afterwards to put the right label back if the user cancels.
    """

    def __init__(self, parent, choices, specials, on_change, on_special):
        self.labels = {value: label for label, value in choices}
        self.values = {label: value for label, value in choices}
        self.specials = specials
        self.on_change = on_change
        self.on_special = on_special
        self.variable = tk.StringVar()
        super().__init__(parent, values=[label for label, _ in choices], variable=self.variable, command=self._chosen, **theme.menu_style())

    def show(self, text):
        self.variable.set(text)

    def _chosen(self, label):
        value = self.values.get(label)
        if value in self.specials:
            self.on_special(value)
        else:
            self.on_change(value)
