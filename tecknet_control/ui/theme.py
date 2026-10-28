"""Colours, fonts and sizes of the window. Change the look here only.

Each colour is (light theme, dark theme), as CustomTkinter expects.
"""

import customtkinter as ctk

BACKGROUND = ("#F3F4F6", "#111318")
CARD = ("#FFFFFF", "#1B1E24")
CARD_BORDER = ("#E5E7EB", "#262A32")
FIELD = ("#F3F4F6", "#262A32")
FIELD_HOVER = ("#E5E7EB", "#30353F")
TEXT = ("#111827", "#F3F4F6")
MUTED = ("#6B7280", "#9CA3AF")
ACCENT = ("#2563EB", "#3B82F6")
ACCENT_HOVER = ("#1D4ED8", "#2563EB")
ACCENT_SOFT = ("#DBEAFE", "#1E2A44")
SUCCESS = ("#16A34A", "#4ADE80")
ERROR = ("#DC2626", "#F87171")
IDLE = ("#9CA3AF", "#6B7280")
BATTERY_LOW = ("#F59E0B", "#FBBF24")

FONT_FAMILY = "Segoe UI"
RADIUS = 12
PAD = 18  # inside cards
GAP = 12  # between cards

MENU_WIDTH = 230


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def menu_style():
    """Neutral drop-down menus (the default blue blocks are too loud)."""
    return dict(
        fg_color=FIELD, button_color=FIELD, button_hover_color=FIELD_HOVER,
        text_color=TEXT, dropdown_fg_color=CARD, dropdown_text_color=TEXT,
        dropdown_hover_color=FIELD_HOVER, corner_radius=8, font=font(13),
        dropdown_font=font(13), dynamic_resizing=False, width=MENU_WIDTH, height=34,
    )


def switch_style():
    return dict(
        progress_color=ACCENT, fg_color=("#C4C9D2", "#3A3F4A"),
        button_color=("#4B5563", "#D1D5DB"), button_hover_color=("#374151", "#F3F4F6"),
        switch_width=40, switch_height=20, text_color=TEXT, font=font(13),
    )


def button_style(primary=False):
    if primary:
        return dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFFFFF", corner_radius=8, font=font(13, "bold"), height=34)
    return dict(fg_color=FIELD, hover_color=FIELD_HOVER, text_color=TEXT, corner_radius=8, font=font(13), height=34)
