"""Window to choose the application a side button opens."""

import os
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from . import theme

START_MENU_FOLDERS = (
    Path(os.getenv("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    Path(os.getenv("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
)
MAX_RESULTS = 80
_cache = None


def installed_apps():
    """(name, shortcut path) for every Start menu shortcut, sorted by name."""
    global _cache
    if _cache is None:
        apps = {}
        for folder in START_MENU_FOLDERS:
            if folder.is_dir():
                for shortcut in folder.rglob("*.lnk"):
                    name = shortcut.stem
                    if "uninstall" not in name.lower():
                        apps.setdefault(name, str(shortcut))
        _cache = sorted(apps.items(), key=lambda item: item[0].lower())
    return _cache


class AppPicker(ctk.CTkToplevel):
    def __init__(self, parent, on_select, on_cancel):
        super().__init__(parent, fg_color=theme.BACKGROUND)
        self.on_select = on_select
        self.on_cancel = on_cancel
        self.title("Choose application")
        self.geometry("440x540")
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.apps = installed_apps()

        ctk.CTkLabel(self, text="Choose application", font=theme.font(16, "bold"), text_color=theme.TEXT).pack(anchor="w", padx=18, pady=(18, 8))
        self.search = ctk.CTkEntry(self, placeholder_text="Search installed applications…", height=38, corner_radius=8,
                                   fg_color=theme.CARD, border_color=theme.CARD_BORDER, text_color=theme.TEXT, font=theme.font(13))
        self.search.pack(fill="x", padx=18)
        self.results = ctk.CTkScrollableFrame(self, fg_color=theme.CARD, corner_radius=theme.RADIUS,
                                              border_color=theme.CARD_BORDER, border_width=1)
        self.results.pack(fill="both", expand=True, padx=18, pady=12)
        ctk.CTkButton(self, text="Browse for an .exe or shortcut…", command=self.browse, **theme.button_style()).pack(fill="x", padx=18, pady=(0, 18))
        self.search.bind("<KeyRelease>", self.render)
        self.render()
        # CTkToplevel can open behind the main window on Windows.
        self.after(120, self.bring_to_front)

    def bring_to_front(self):
        self.lift()
        self.focus_force()
        self.search.focus_set()
        self.grab_set()

    def render(self, *_):
        for widget in self.results.winfo_children():
            widget.destroy()
        query = self.search.get().lower().strip()
        matches = [app for app in self.apps if query in app[0].lower()][:MAX_RESULTS]
        for name, path in matches:
            ctk.CTkButton(
                self.results, text=name, anchor="w", height=34, corner_radius=6, fg_color="transparent",
                text_color=theme.TEXT, hover_color=theme.FIELD_HOVER, font=theme.font(13),
                command=lambda p=path, n=name: self.select(p, n),
            ).pack(fill="x", pady=1)
        if not matches:
            ctk.CTkLabel(self.results, text="No applications found", text_color=theme.MUTED, font=theme.font(13)).pack(pady=20)

    def browse(self):
        self.grab_release()
        path = filedialog.askopenfilename(
            parent=self, title="Choose application",
            filetypes=[("Applications and shortcuts", "*.exe *.lnk")],
        )
        if path:
            self.select(path, Path(path).stem)
        else:
            self.grab_set()

    def select(self, path, name):
        self.grab_release()
        self.destroy()
        self.on_select(path, name)

    def cancel(self):
        self.grab_release()
        self.destroy()
        self.on_cancel()
