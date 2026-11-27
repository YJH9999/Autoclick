"""可复用 UI 组件。"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from .platform import VirtualScreen
from .theme import FONT, colors


class Card(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = "", **kwargs):
        super().__init__(master, corner_radius=12, border_width=1, **kwargs)
        self.configure(fg_color=(colors()["surface"], colors()["surface"]))
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=16, pady=(12, 4))
        self.title_label = ctk.CTkLabel(self.header, text=title, font=(FONT, 14, "bold"))
        self.title_label.pack(side="left")
        if subtitle:
            ctk.CTkLabel(self.header, text=subtitle, font=(FONT, 10), text_color=colors()["muted"]).pack(side="left", padx=10)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16, pady=(4, 14))

    def refresh_theme(self) -> None:
        palette = colors()
        self.configure(fg_color=palette["surface"], border_color=palette["border"])
        self.title_label.configure(text_color=palette["text"])
        for child in self.header.winfo_children():
            if child is not self.title_label and isinstance(child, ctk.CTkLabel):
                child.configure(text_color=palette["muted"])


class ScreenPreview(tk.Canvas):
    """按整个虚拟桌面比例显示目标；点击/拖动可修改固定坐标。"""
    def __init__(self, master, screen: VirtualScreen, on_change: Callable[[int, int], None], height: int = 118):
        self.screen = screen
        self.on_change = on_change
        self.x, self.y = screen.clamp(screen.width // 2, screen.height // 2)
        self.area = None
        palette = colors()
        super().__init__(master, height=height, bg=palette["preview"], highlightthickness=1,
                         highlightbackground=palette["border"], cursor="crosshair")
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<Button-1>", self._pick)
        self.bind("<B1-Motion>", self._pick)

    def set_target(self, x: int, y: int, area=None) -> None:
        self.x, self.y = x, y
        self.area = area
        self.redraw()

    def set_screen(self, screen: VirtualScreen) -> None:
        self.screen = screen
        self.redraw()

    def _pick(self, event) -> None:
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        x, y = self.screen.from_relative(event.x / width, event.y / height)
        self.x, self.y, self.area = x, y, None
        self.redraw()
        self.on_change(x, y)

    def _point(self, x: int, y: int) -> tuple[float, float]:
        rx, ry = self.screen.to_relative(x, y)
        return rx * max(1, self.winfo_width()), ry * max(1, self.winfo_height())

    def redraw(self) -> None:
        if not self.winfo_exists():
            return
        palette = colors()
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        self.configure(bg=palette["preview"], highlightbackground=palette["border"])
        self.delete("all")
        for step in range(1, 4):
            self.create_line(width * step / 4, 0, width * step / 4, height, fill=palette["grid"])
            self.create_line(0, height * step / 4, width, height * step / 4, fill=palette["grid"])
        if self.area:
            first, second = self._point(self.area[0], self.area[1]), self._point(self.area[2], self.area[3])
            self.create_rectangle(*first, *second, outline=palette["accent"], width=2)
        x, y = self._point(self.x, self.y)
        self.create_line(x - 9, y, x + 9, y, fill=palette["text"])
        self.create_line(x, y - 9, x, y + 9, fill=palette["text"])
        self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=palette["red"], outline=palette["text"])
        text = f"虚拟桌面  {self.screen.width} × {self.screen.height}   原点 ({self.screen.left}, {self.screen.top})"
        self.create_rectangle(0, height - 20, width, height, fill=palette["preview"], outline="")
        self.create_text(width / 2, height - 10, text=text, fill=palette["muted"], font=(FONT, 9))
