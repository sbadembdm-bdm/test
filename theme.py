"""Uygulama genel görünümü: koyu lacivert + altın tema."""
import tkinter as tk
from tkinter import ttk

BG = "#0e1526"
CARD = "#182135"
FIELD = "#212d47"
TEXT = "#e6ebf5"
MUTED = "#93a0bf"
GOLD = "#d9b64a"
GOLD_TEXT = "#1a1405"
DANGER = "#7f2430"
LOG_BG = "#0a0f1d"
LOG_FG = "#8fe3a1"

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")


def apply_style(root):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT, font=FONT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=TEXT)

    style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT,
                    insertcolor=TEXT, bordercolor=FIELD, lightcolor=FIELD,
                    darkcolor=FIELD, padding=5)
    style.map("TEntry", fieldbackground=[("disabled", CARD)])

    style.configure("TCombobox", fieldbackground=FIELD, background=FIELD,
                    foreground=TEXT, arrowcolor=GOLD, bordercolor=FIELD,
                    lightcolor=FIELD, darkcolor=FIELD, padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", FIELD)],
              foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", FIELD)],
              selectforeground=[("readonly", TEXT)])

    style.configure("TCheckbutton", background=CARD, foreground=TEXT,
                    focuscolor=CARD, font=FONT_SMALL)
    style.map("TCheckbutton",
              background=[("active", CARD)],
              foreground=[("disabled", MUTED)])

    style.configure("TButton", background=FIELD, foreground=TEXT,
                    borderwidth=0, focuscolor=FIELD, padding=(12, 6),
                    font=FONT_SMALL)
    style.map("TButton",
              background=[("active", "#2c3b5e"), ("disabled", "#161f33")],
              foreground=[("disabled", "#5a6685")])

    style.configure("Accent.TButton", background=GOLD, foreground=GOLD_TEXT,
                    font=("Segoe UI", 10, "bold"), padding=(20, 8))
    style.map("Accent.TButton",
              background=[("active", "#e8c962"), ("disabled", "#6e6236")],
              foreground=[("disabled", "#3a331a")])

    style.configure("Danger.TButton", background=DANGER, foreground=TEXT,
                    padding=(14, 8))
    style.map("Danger.TButton",
              background=[("active", "#9b3242"), ("disabled", "#3a1a20")],
              foreground=[("disabled", "#7a5a60")])

    style.configure("Treeview", background=FIELD, fieldbackground=FIELD,
                    foreground=TEXT, borderwidth=0, rowheight=24)
    style.configure("Treeview.Heading", background=CARD, foreground=GOLD,
                    borderwidth=0, font=FONT_SMALL)
    style.map("Treeview",
              background=[("selected", GOLD)],
              foreground=[("selected", GOLD_TEXT)])

    style.configure("Vertical.TScrollbar", background=FIELD, troughcolor=BG,
                    bordercolor=BG, arrowcolor=MUTED)
    style.map("Vertical.TScrollbar", background=[("active", "#2c3b5e")])

    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", GOLD)
    root.option_add("*TCombobox*Listbox.selectForeground", GOLD_TEXT)
    return style


def style_listbox(lb):
    lb.configure(bg=FIELD, fg=TEXT, selectbackground=GOLD,
                 selectforeground=GOLD_TEXT, highlightthickness=0,
                 borderwidth=0, font=FONT_SMALL)
