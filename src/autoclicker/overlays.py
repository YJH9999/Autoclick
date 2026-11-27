"""全屏单点拾取与区域选择，坐标均使用 Windows 虚拟桌面坐标。"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from .platform import VirtualScreen
from .theme import FONT

ACCENT = "#f2b35d"


def geometry(window: tk.Toplevel, screen: VirtualScreen) -> str:
    return f"{screen.width}x{screen.height}{screen.left:+d}{screen.top:+d}"


class BaseOverlay:
    def __init__(self, root, screen: VirtualScreen, on_pick: Callable, on_cancel: Callable[[], None]):
        self.root, self.screen = root, screen
        self.on_pick, self.on_cancel = on_pick, on_cancel
        self._closed = False
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(geometry(self.win, screen))
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.58)
        self.win.configure(bg="#090b0f")
        self.canvas = tk.Canvas(self.win, bg="#090b0f", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.win.bind("<Escape>", lambda _event: self.cancel())
        self.win.bind("<Button-3>", lambda _event: self.cancel())
        self.win.focus_force()

    def pointer(self) -> tuple[int, int]:
        return self.screen.clamp(self.win.winfo_pointerx(), self.win.winfo_pointery())

    def local(self, x: int, y: int) -> tuple[int, int]:
        return x - self.screen.left, y - self.screen.top

    def finish(self, callback: Callable, *args) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        callback(*args)

    def cancel(self) -> None:
        self.finish(self.on_cancel)


class PointPicker(BaseOverlay):
    def __init__(self, root, screen: VirtualScreen, on_pick: Callable, on_cancel: Callable[[], None]):
        super().__init__(root, screen, on_pick, on_cancel)
        self._armed = False
        self.h_line = self.canvas.create_line(0, 0, screen.width, 0, fill=ACCENT)
        self.v_line = self.canvas.create_line(0, 0, 0, screen.height, fill=ACCENT)
        self.dot = self.canvas.create_oval(0, 0, 0, 0, fill="#ef5b62", outline="white")
        self.label = self.canvas.create_text(0, 0, anchor="nw", fill="white", font=(FONT, 13, "bold"))
        self.canvas.create_text(screen.width / 2, 32, text="移动鼠标并单击以确定位置", fill=ACCENT,
                                font=(FONT, 16, "bold"))
        self.canvas.create_text(screen.width / 2, 62, text="Esc 或右键取消", fill="#c4c9d1", font=(FONT, 11))
        self.canvas.bind("<Motion>", lambda _event: self._draw())
        self.canvas.bind("<Button-1>", self._pick)
        self.win.after(350, self._arm)
        self._draw()

    def _arm(self) -> None:
        self._armed = True

    def _draw(self) -> None:
        if self._closed:
            return
        x, y = self.pointer()
        lx, ly = self.local(x, y)
        self.canvas.coords(self.h_line, 0, ly, self.screen.width, ly)
        self.canvas.coords(self.v_line, lx, 0, lx, self.screen.height)
        self.canvas.coords(self.dot, lx - 5, ly - 5, lx + 5, ly + 5)
        label_x = lx + 20 if lx + 230 < self.screen.width else lx - 190
        label_y = ly + 20 if ly + 45 < self.screen.height else ly - 40
        self.canvas.coords(self.label, label_x, label_y)
        self.canvas.itemconfigure(self.label, text=f"X {x}   Y {y}")

    def _pick(self, _event) -> None:
        if self._armed:
            x, y = self.pointer()
            self.finish(self.on_pick, x, y, None)


class AreaPicker(BaseOverlay):
    def __init__(self, root, screen: VirtualScreen, on_pick: Callable, on_cancel: Callable[[], None]):
        super().__init__(root, screen, on_pick, on_cancel)
        self.box: tuple[int, int, int, int] | None = None
        self.state = "idle"
        self.origin: tuple[int, int] | None = None
        self.offset: tuple[int, int] | None = None
        self.canvas.create_text(screen.width / 2, 30, fill=ACCENT, font=(FONT, 15, "bold"),
                                text="拖拽创建选区；拖动选区可移动；Enter 或双击确认")
        self.canvas.create_text(screen.width / 2, 58, fill="#c4c9d1", font=(FONT, 11),
                                text="单击可创建 24 × 24 选区；Esc 或右键取消")
        self.info = self.canvas.create_text(16, 16, anchor="nw", fill="white", font=(FONT, 11))
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Double-Button-1>", lambda _event: self.confirm())
        self.win.bind("<Return>", lambda _event: self.confirm())

    def _pointer_local(self) -> tuple[int, int]:
        return self.local(*self.pointer())

    def _motion(self, _event) -> None:
        if self.state == "idle":
            self.canvas.itemconfigure(self.info, text="鼠标 " + str(self.pointer()))

    def _set_box(self, first: tuple[int, int], second: tuple[int, int]) -> None:
        self.box = min(first[0], second[0]), min(first[1], second[1]), max(first[0], second[0]), max(first[1], second[1])
        self._draw()

    def _draw(self) -> None:
        self.canvas.delete("selection")
        if not self.box:
            return
        x1, y1, x2, y2 = self.box
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=ACCENT, width=3, tags="selection")
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        self.canvas.create_line(cx - 10, cy, cx + 10, cy, fill="white", tags="selection")
        self.canvas.create_line(cx, cy - 10, cx, cy + 10, fill="white", tags="selection")
        global_box = (x1 + self.screen.left, y1 + self.screen.top,
                      x2 + self.screen.left, y2 + self.screen.top)
        self.canvas.itemconfigure(self.info, text=f"中心 ({(global_box[0] + global_box[2]) // 2}, {(global_box[1] + global_box[3]) // 2})   尺寸 {x2-x1} × {y2-y1}")

    def _inside(self, point: tuple[int, int]) -> bool:
        if not self.box:
            return False
        x1, y1, x2, y2 = self.box
        return x1 - 5 <= point[0] <= x2 + 5 and y1 - 5 <= point[1] <= y2 + 5

    def _press(self, _event) -> None:
        point = self._pointer_local()
        if self.state == "placed" and self._inside(point):
            self.state = "moving"
            self.offset = point[0] - self.box[0], point[1] - self.box[1]
        else:
            self.state, self.origin = "dragging", point
            self._set_box(point, point)

    def _drag(self, _event) -> None:
        point = self._pointer_local()
        if self.state == "dragging" and self.origin:
            self._set_box(self.origin, point)
        elif self.state == "moving" and self.box and self.offset:
            width, height = self.box[2] - self.box[0], self.box[3] - self.box[1]
            x1 = max(0, min(self.screen.width - width, point[0] - self.offset[0]))
            y1 = max(0, min(self.screen.height - height, point[1] - self.offset[1]))
            self.box = x1, y1, x1 + width, y1 + height
            self._draw()

    def _release(self, _event) -> None:
        if self.state == "dragging" and self.box:
            if self.box[2] - self.box[0] < 8 or self.box[3] - self.box[1] < 8:
                x, y = self._pointer_local()
                self.box = max(0, x - 12), max(0, y - 12), min(self.screen.width, x + 12), min(self.screen.height, y + 12)
                self._draw()
        self.state = "placed" if self.box else "idle"
        self.origin = self.offset = None

    def confirm(self) -> None:
        if self.state == "placed" and self.box:
            x1, y1, x2, y2 = self.box
            area = (x1 + self.screen.left, y1 + self.screen.top,
                    x2 + self.screen.left, y2 + self.screen.top)
            self.finish(self.on_pick, (area[0] + area[2]) // 2, (area[1] + area[3]) // 2, area)
