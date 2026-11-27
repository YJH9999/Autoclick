"""主题令牌：集中管理颜色，避免控件间配色漂移。"""
from __future__ import annotations

import customtkinter as ctk

FONT = "Microsoft YaHei UI"

DARK = {
    "window": "#111318", "surface": "#191c22", "surface_2": "#22262e",
    "border": "#30353f", "text": "#f2f4f7", "muted": "#9aa3af",
    "accent": "#f2b35d", "accent_hover": "#d99a46", "accent_text": "#2a1b08",
    "green": "#36b37e", "green_hover": "#279568", "red": "#e05d5d",
    "red_hover": "#c64747", "orange": "#d99a46", "preview": "#0d0f13",
    "grid": "#292e37", "disabled": "#555c68",
}
LIGHT = {
    "window": "#f4f5f7", "surface": "#ffffff", "surface_2": "#eceff3",
    "border": "#d8dde5", "text": "#20242b", "muted": "#626b78",
    "accent": "#9a5a08", "accent_hover": "#b97519", "accent_text": "#ffffff",
    "green": "#198754", "green_hover": "#146c43", "red": "#c83e4d",
    "red_hover": "#a92e3c", "orange": "#a75d00", "preview": "#fafbfc",
    "grid": "#e4e8ee", "disabled": "#858d99",
}


def colors() -> dict[str, str]:
    return DARK if ctk.get_appearance_mode() == "Dark" else LIGHT


def pair(name: str) -> tuple[str, str]:
    return LIGHT[name], DARK[name]


def apply_mode(mode: str) -> None:
    ctk.set_appearance_mode("Light" if mode == "light" else "Dark")
