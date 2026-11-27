"""AutoClicker 主窗口与 UI 状态编排。"""
from __future__ import annotations

import ctypes
import logging
import math
import os
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from . import __version__
from .config import ConfigError, ConfigStore, normalize_config
from .dialogs import CloseDialog, SettingsDialog, TextDialog
from .engine import ClickEngine
from .hotkeys import HotkeyError, HotkeyManager
from .models import BUILTIN_PRESETS, DEFAULT_HOTKEYS, PRESET_KEYS, ClickSettings, parse_int
from .overlays import AreaPicker, PointPicker
from .platform import resource_path, virtual_screen
from .theme import FONT, apply_mode, colors, pair
from .tray import TrayIcon
from .widgets import Card, ScreenPreview

LOG = logging.getLogger(__name__)
BUTTONS = {"左键": "left", "右键": "right", "中键": "middle"}
CLICK_MODES = {"单击": "single", "双击": "double"}


class AutoClickerApp(ctk.CTk):
    def __init__(self, store: ConfigStore | None = None):
        self.store = store or ConfigStore()
        self.config, config_warning = self.store.load()
        apply_mode(self.config["theme"])
        super().__init__()
        self.title("AutoClicker")
        self.geometry("600x840")
        self.minsize(560, 680)
        self.resizable(True, True)
        self.overrideredirect(True)
        self.configure(fg_color=pair("window"))
        self._center_window()
        self._set_icon()
        self.protocol("WM_DELETE_WINDOW", self.request_close)

        self.screen = virtual_screen(self.winfo_screenwidth(), self.winfo_screenheight())
        self.engine = ClickEngine()
        self.engine.on_stopped = lambda reason: self._ui_call(self._engine_stopped, reason)
        self.hotkeys = HotkeyManager()
        for event, callback in {
            "toggle": self.toggle_start, "pause": self.toggle_pause,
            "pick": self.open_area_picker, "emergency": self.emergency_stop,
        }.items():
            self.hotkeys.on(event, lambda callback=callback: self._ui_call(callback))
        self.tray = TrayIcon(self)
        self.overlay = None
        self.cards: list[Card] = []
        self._drag_offset = None
        self._folded = False
        self._closing = False
        self._run_started: float | None = None
        self._countdown_end: float | None = None
        self._notice_until = 0.0
        self._poll_job = None
        self._build_titlebar()
        self._build_content()
        self._load_into_form()
        self._refresh_theme()
        self._start_hotkeys()
        self.after(180, self._enable_taskbar)
        self._poll_job = self.after(100, self._poll)
        if config_warning:
            self.after(250, lambda: self._show_warning("配置提示", config_warning))
        self.after(300, self._check_screen)

    def _ui_call(self, callback, *args) -> None:
        if not self._closing:
            try:
                self.after(0, callback, *args)
            except tk.TclError:
                pass

    def _set_icon(self) -> None:
        try:
            self.iconbitmap(str(resource_path("icon.ico")))
        except (tk.TclError, OSError):
            LOG.debug("窗口图标加载失败", exc_info=True)

    def _center_window(self) -> None:
        width, height = 600, 840
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _check_screen(self) -> None:
        current = virtual_screen(self.winfo_screenwidth(), self.winfo_screenheight())
        if current != self.screen:
            self.screen = current
            self.preview.set_screen(current)
            self._set_position(*current.clamp(self.config["x"], self.config["y"]), self.config.get("area"), save=False)

    # ---------------- 窗口与标题栏 ----------------
    def _build_titlebar(self) -> None:
        self.titlebar = ctk.CTkFrame(self, height=42, corner_radius=0, fg_color=pair("surface"))
        self.titlebar.pack(fill="x")
        self.titlebar.pack_propagate(False)
        brand = ctk.CTkLabel(self.titlebar, text="◆  AUTOCLICKER", font=(FONT, 12, "bold"), text_color=pair("accent"))
        brand.pack(side="left", padx=(16, 8), pady=9)
        ctk.CTkLabel(self.titlebar, text=f"v{__version__}", font=(FONT, 9), text_color=pair("muted")).pack(side="left")
        self.close_button = self._title_button("×", 34, self.request_close, danger=True)
        self.close_button.pack(side="right", padx=(2, 8), pady=7)
        self._title_button("—", 34, self.minimize).pack(side="right", padx=2, pady=7)
        self._title_button("说明", 48, self.show_help).pack(side="right", padx=2, pady=7)
        self._title_button("设置", 48, self.show_settings).pack(side="right", padx=2, pady=7)
        self.theme_button = self._title_button("浅色", 48, self.toggle_theme)
        self.theme_button.pack(side="right", padx=2, pady=7)
        self.pin_button = self._title_button("置顶", 48, self.toggle_pin)
        self.pin_button.pack(side="right", padx=2, pady=7)
        for widget in (self.titlebar, brand):
            widget.bind("<ButtonPress-1>", self._title_press)
            widget.bind("<B1-Motion>", self._title_drag)
            widget.bind("<Double-Button-1>", lambda _event: self.toggle_fold())

    def _title_button(self, text: str, width: int, command, danger: bool = False):
        return ctk.CTkButton(
            self.titlebar, text=text, width=width, height=28, command=command,
            font=(FONT, 11), corner_radius=6,
            fg_color="transparent" if danger else pair("surface_2"),
            hover_color=pair("red") if danger else pair("border"), text_color=pair("text"),
        )

    def _title_press(self, event) -> None:
        self._drag_offset = event.x_root - self.winfo_x(), event.y_root - self.winfo_y()

    def _title_drag(self, event) -> None:
        if self._drag_offset:
            self.geometry(f"+{event.x_root-self._drag_offset[0]}+{event.y_root-self._drag_offset[1]}")

    def _hwnd(self) -> int | None:
        if os.name != "nt":
            return None
        try:
            parent = ctypes.windll.user32.GetParent(self.winfo_id())
            return parent or self.winfo_id()
        except Exception:
            return None

    def _enable_taskbar(self) -> None:
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            user32 = ctypes.windll.user32
            get_style = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
            set_style = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
            set_style(hwnd, -20, (get_style(hwnd, -20) or 0) | 0x00040000)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
        except Exception:
            LOG.debug("任务栏入口注册失败", exc_info=True)

    def minimize(self) -> None:
        if self._folded:
            self.toggle_fold()
        hwnd = self._hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)
        else:
            self.iconify()

    def show_window(self) -> None:
        self.deiconify()
        if self.tray.active:
            self.tray.stop()
        hwnd = self._hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        self.lift()
        self._set_topmost()

    def toggle_fold(self) -> None:
        self._folded = not self._folded
        if self._folded:
            self.content.pack_forget()
        else:
            self.content.pack(fill="both", expand=True)

    def toggle_pin(self) -> None:
        self.config["topmost"] = not self.config["topmost"]
        self._set_topmost()
        self._refresh_theme()
        self._save_quietly()

    def _set_topmost(self) -> None:
        self.attributes("-topmost", self.config["topmost"])

    def toggle_theme(self) -> None:
        self.config["theme"] = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        apply_mode(self.config["theme"])
        self._refresh_theme()
        self._save_quietly()
        self._set_topmost()
        self.lift()

    def _refresh_theme(self) -> None:
        palette = colors()
        self.configure(fg_color=palette["window"])
        self.titlebar.configure(fg_color=palette["surface"])
        for card in self.cards:
            card.refresh_theme()
        self.theme_button.configure(text="浅色" if ctk.get_appearance_mode() == "Dark" else "深色")
        self.pin_button.configure(fg_color=palette["accent"] if self.config["topmost"] else palette["surface_2"],
                                  text_color=palette["accent_text"] if self.config["topmost"] else palette["text"])
        self.preview.redraw()
        self.status_frame.configure(fg_color=palette["surface"])
        self._set_topmost()

    # ---------------- 表单 ----------------
    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self.form = ctk.CTkScrollableFrame(self.content, fg_color="transparent", scrollbar_button_color=pair("border"))
        position = Card(self.form, "点击位置", "支持多显示器与负坐标")
        position.pack(fill="x", padx=14, pady=(12, 8))
        self.cards.append(position)
        self.preview = ScreenPreview(position.body, self.screen, self._preview_changed, height=90)
        self.preview.pack(fill="x", pady=(2, 8))
        coordinate_row = ctk.CTkFrame(position.body, fg_color="transparent")
        coordinate_row.pack(fill="x")
        self.coordinate_label = ctk.CTkLabel(coordinate_row, text="", font=(FONT, 13, "bold"), text_color=pair("accent"))
        self.coordinate_label.pack(side="left")
        ctk.CTkLabel(coordinate_row, text="X", font=(FONT, 11), text_color=pair("muted")).pack(side="left", padx=(16, 4))
        self.x_entry = ctk.CTkEntry(coordinate_row, width=72, height=28, justify="center")
        self.x_entry.pack(side="left")
        ctk.CTkLabel(coordinate_row, text="Y", font=(FONT, 11), text_color=pair("muted")).pack(side="left", padx=(8, 4))
        self.y_entry = ctk.CTkEntry(coordinate_row, width=72, height=28, justify="center")
        self.y_entry.pack(side="left")
        ctk.CTkButton(coordinate_row, text="应用", width=52, height=28, command=self._apply_coordinates,
                      fg_color=pair("surface_2"), hover_color=pair("border")).pack(side="left", padx=(6, 0))
        self.x_entry.bind("<Return>", lambda _event: self._apply_coordinates())
        self.y_entry.bind("<Return>", lambda _event: self._apply_coordinates())
        picker_row = ctk.CTkFrame(position.body, fg_color="transparent")
        picker_row.pack(fill="x", pady=(8, 0))
        self.area_button = ctk.CTkButton(picker_row, text="区域选点  F8", height=32, command=self.open_area_picker,
                                         fg_color=pair("accent"), hover_color=pair("accent_hover"), text_color=pair("accent_text"),
                                         font=(FONT, 12, "bold"))
        self.area_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.point_button = ctk.CTkButton(picker_row, text="拾取鼠标位置", height=32, command=self.open_point_picker,
                                          fg_color=pair("surface_2"), hover_color=pair("border"))
        self.point_button.pack(side="left", fill="x", expand=True, padx=(4, 0))

        click = Card(self.form, "点击规则", "参数修改将在下次启动时生效")
        click.pack(fill="x", padx=14, pady=8)
        self.cards.append(click)
        click.body.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(click.body, text="点击间隔", font=(FONT, 12)).grid(row=0, column=0, sticky="w", pady=5)
        interval_row = ctk.CTkFrame(click.body, fg_color="transparent")
        interval_row.grid(row=0, column=1, sticky="ew", padx=(16, 0), pady=5)
        self.interval = ctk.CTkComboBox(interval_row, values=["1", "5", "10", "20", "50", "75", "100", "150", "200", "300", "500", "750", "1000", "1500", "2000", "5000", "10000", "30000", "60000", "300000", "600000", "3600000"], width=116)
        self.interval.pack(side="left")
        ctk.CTkLabel(interval_row, text="ms", font=(FONT, 11), text_color=pair("muted")).pack(side="left", padx=6)
        self.rate_label = ctk.CTkLabel(interval_row, text="约 10.0 次/秒", font=(FONT, 11), text_color=pair("muted"))
        self.rate_label.pack(side="right")
        self.interval.bind("<KeyRelease>", lambda _event: self._update_rate())
        self.interval.configure(command=lambda _value: self._update_rate())
        ctk.CTkLabel(click.body, text="鼠标按键", font=(FONT, 12)).grid(row=1, column=0, sticky="w", pady=5)
        self.button_mode = ctk.CTkSegmentedButton(click.body, values=list(BUTTONS), height=30)
        self.button_mode.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=5)
        ctk.CTkLabel(click.body, text="点击方式", font=(FONT, 12)).grid(row=2, column=0, sticky="w", pady=5)
        self.click_mode = ctk.CTkSegmentedButton(click.body, values=list(CLICK_MODES), height=30)
        self.click_mode.grid(row=2, column=1, sticky="ew", padx=(16, 0), pady=5)
        ctk.CTkLabel(click.body, text="重复次数", font=(FONT, 12)).grid(row=3, column=0, sticky="w", pady=5)
        limit_row = ctk.CTkFrame(click.body, fg_color="transparent")
        limit_row.grid(row=3, column=1, sticky="ew", padx=(16, 0), pady=5)
        self.limit_mode = ctk.CTkSegmentedButton(limit_row, values=["无限", "指定次数"], command=self._limit_changed, height=30)
        self.limit_mode.pack(side="left", fill="x", expand=True)
        self.limit_entry = ctk.CTkEntry(limit_row, width=88, height=30, placeholder_text="次数")
        self.limit_entry.pack(side="right", padx=(8, 0))
        ctk.CTkLabel(click.body, text="区域随机范围", font=(FONT, 12)).grid(row=4, column=0, sticky="w", pady=(8, 2))
        jitter_row = ctk.CTkFrame(click.body, fg_color="transparent")
        jitter_row.grid(row=4, column=1, sticky="ew", padx=(16, 0), pady=(8, 2))
        self.jitter = ctk.CTkSlider(jitter_row, from_=0, to=100, number_of_steps=100, command=self._jitter_changed)
        self.jitter.pack(side="left", fill="x", expand=True)
        self.jitter_label = ctk.CTkLabel(jitter_row, text="0%", width=44, font=(FONT, 11), text_color=pair("muted"))
        self.jitter_label.pack(side="right")

        task = Card(self.form, "运行方式", "紧急停止热键可在设置中修改")
        task.pack(fill="x", padx=14, pady=8)
        self.cards.append(task)
        task.body.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(task.body, text="位置模式", font=(FONT, 12)).grid(row=0, column=0, sticky="w", pady=4)
        self.position_mode = ctk.CTkSegmentedButton(task.body, values=["固定位置", "跟随鼠标"], command=self._position_mode_changed, height=30)
        self.position_mode.grid(row=0, column=1, sticky="ew", padx=(16, 0), pady=4)
        ctk.CTkLabel(task.body, text="启动延迟", font=(FONT, 12)).grid(row=1, column=0, sticky="w", pady=4)
        delay_row = ctk.CTkFrame(task.body, fg_color="transparent")
        delay_row.grid(row=1, column=1, sticky="w", padx=(16, 0), pady=4)
        self.delay_entry = ctk.CTkEntry(delay_row, width=76, height=30, justify="center")
        self.delay_entry.pack(side="left")
        ctk.CTkLabel(delay_row, text="秒（0～60，可取消）", font=(FONT, 11), text_color=pair("muted")).pack(side="left", padx=8)
        switches = ctk.CTkFrame(task.body, fg_color="transparent")
        switches.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.sound_var = tk.BooleanVar()
        self.restore_var = tk.BooleanVar()
        self.smart_var = tk.BooleanVar()
        self.low_var = tk.BooleanVar()
        for row, column, text, variable in (
            (0, 0, "操作提示音", self.sound_var), (0, 1, "点击后恢复光标", self.restore_var),
            (1, 0, "智能停止（实验性）", self.smart_var), (1, 1, "低配模式", self.low_var),
        ):
            ctk.CTkSwitch(switches, text=text, variable=variable, font=(FONT, 11)).grid(row=row, column=column, sticky="w", padx=(0, 20), pady=5)
        switches.grid_columnconfigure(0, weight=1)
        switches.grid_columnconfigure(1, weight=1)

        preset_row = ctk.CTkFrame(self.form, fg_color="transparent")
        preset_row.pack(fill="x", padx=14, pady=(2, 8))
        ctk.CTkLabel(preset_row, text="预设", font=(FONT, 12, "bold")).pack(side="left", padx=(2, 8))
        self.preset_box = ctk.CTkComboBox(preset_row, values=list(BUILTIN_PRESETS), command=self.apply_preset, state="readonly")
        self.preset_box.pack(side="left", fill="x", expand=True)
        for text, command in (("保存当前", self.save_preset), ("删除", self.delete_preset)):
            ctk.CTkButton(preset_row, text=text, width=76, height=30, command=command,
                          fg_color=pair("surface_2"), hover_color=pair("border")).pack(side="left", padx=(6, 0))

        controls = ctk.CTkFrame(self.content, fg_color="transparent")
        controls.pack(fill="x", padx=14, pady=(0, 8), side="bottom")
        self.start_button = ctk.CTkButton(controls, text="开始点击  F6", height=44, command=self.toggle_start,
                                          fg_color=pair("green"), hover_color=pair("green_hover"), font=(FONT, 15, "bold"))
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.pause_button = ctk.CTkButton(controls, text="暂停  F7", height=44, command=self.toggle_pause, state="disabled",
                                          fg_color=pair("surface_2"), hover_color=pair("border"), font=(FONT, 13, "bold"))
        self.pause_button.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self.status_frame = ctk.CTkFrame(self.content, corner_radius=8, fg_color=pair("surface"))
        self.status_frame.pack(fill="x", padx=14, pady=(0, 8), side="bottom")
        self.status_label = ctk.CTkLabel(self.status_frame, text="● 就绪", font=(FONT, 12, "bold"), text_color=pair("muted"))
        self.status_label.pack(anchor="w", padx=12, pady=(8, 0))
        self.metrics_label = ctk.CTkLabel(self.status_frame, text="点击 0 次   运行 00:00   鼠标 (0, 0)", font=(FONT, 10),
                                          text_color=pair("muted"))
        self.metrics_label.pack(anchor="w", padx=12, pady=(2, 8))
        self.form.pack(fill="both", expand=True)

    def _load_into_form(self) -> None:
        cfg = self.config
        self.interval.set(str(cfg["interval_ms"]))
        self.button_mode.set(next(key for key, value in BUTTONS.items() if value == cfg["button"]))
        self.click_mode.set(next(key for key, value in CLICK_MODES.items() if value == cfg["click_mode"]))
        self.limit_mode.set("指定次数" if cfg["limit"] else "无限")
        self._set_entry(self.limit_entry, str(cfg["limit"] or 100))
        self._limit_changed(self.limit_mode.get())
        self.jitter.set(cfg["jitter_pct"])
        self._jitter_changed(cfg["jitter_pct"])
        self.position_mode.set("跟随鼠标" if cfg["position_mode"] == "follow" else "固定位置")
        self._set_entry(self.delay_entry, str(cfg["start_delay"]))
        self.sound_var.set(cfg["sound"])
        self.restore_var.set(cfg["restore_cursor"])
        self.smart_var.set(cfg["smart_stop"])
        self.low_var.set(cfg["low_perf"])
        self._set_position(cfg["x"], cfg["y"], cfg["area"], save=False)
        self._refresh_presets()
        self._position_mode_changed(self.position_mode.get())
        self._update_rate()

    @staticmethod
    def _set_entry(entry, value: str) -> None:
        state = entry.cget("state")
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)
        entry.configure(state=state)

    def _collect_config(self) -> dict:
        candidate = dict(self.config)
        candidate["presets"] = dict(self.config.get("presets", {}))
        candidate["hotkeys"] = dict(self.config["hotkeys"])
        candidate.update(
            x=parse_int(self.x_entry.get(), "X 坐标", -1_000_000, 1_000_000),
            y=parse_int(self.y_entry.get(), "Y 坐标", -1_000_000, 1_000_000),
            interval_ms=parse_int(self.interval.get(), "点击间隔", 1, 3_600_000),
            jitter_pct=round(self.jitter.get()),
            button=BUTTONS[self.button_mode.get()],
            click_mode=CLICK_MODES[self.click_mode.get()],
            limit=parse_int(self.limit_entry.get(), "点击次数", 1, 10_000_000) if self.limit_mode.get() == "指定次数" else 0,
            position_mode="follow" if self.position_mode.get() == "跟随鼠标" else "fixed",
            restore_cursor=self.restore_var.get(), smart_stop=self.smart_var.get(),
            start_delay=parse_int(self.delay_entry.get() or "0", "启动延迟", 0, 60),
            sound=self.sound_var.get(), low_perf=self.low_var.get(),
        )
        return normalize_config(candidate)

    def _save_quietly(self) -> bool:
        try:
            self.store.save(self.config)
            return True
        except ConfigError as exc:
            LOG.error("%s", exc)
            self._notify("配置未能保存", "red")
            return False

    def _limit_changed(self, value: str) -> None:
        self.limit_entry.configure(state="normal" if value == "指定次数" else "disabled")

    def _jitter_changed(self, value: float) -> None:
        self.jitter_label.configure(text=f"{round(value)}%")

    def _position_mode_changed(self, value: str) -> None:
        state = "normal" if value == "固定位置" else "disabled"
        for widget in (self.point_button, self.area_button, self.x_entry, self.y_entry):
            widget.configure(state=state)
        self.preview.configure(cursor="crosshair" if value == "固定位置" else "arrow")
        self.preview.unbind("<Button-1>")
        self.preview.unbind("<B1-Motion>")
        if value == "固定位置":
            self.preview.bind("<Button-1>", self.preview._pick)
            self.preview.bind("<B1-Motion>", self.preview._pick)
        self._update_jitter_state()

    def _update_jitter_state(self) -> None:
        enabled = bool(self.config.get("area")) and self.position_mode.get() == "固定位置"
        self.jitter.configure(state="normal" if enabled else "disabled")

    def _update_rate(self) -> None:
        try:
            interval = parse_int(self.interval.get(), "点击间隔", 1, 3_600_000)
            rate = 1000 / interval
            text = f"约 {rate:.1f} 次/秒" if rate >= 0.1 else f"约 {interval/1000:g} 秒/次"
            self.rate_label.configure(text=text)
        except ValueError:
            self.rate_label.configure(text="等待有效输入")

    # ---------------- 坐标与取点 ----------------
    def _set_position(self, x: int, y: int, area=None, save: bool = True) -> None:
        self.config["x"], self.config["y"], self.config["area"] = x, y, area
        self.coordinate_label.configure(text=f"({x}, {y})" + ("  ·  区域" if area else "  ·  单点"))
        self._set_entry(self.x_entry, str(x))
        self._set_entry(self.y_entry, str(y))
        self.preview.set_target(x, y, area)
        self._update_jitter_state()
        if save:
            self._save_quietly()

    def _apply_coordinates(self) -> None:
        try:
            x = parse_int(self.x_entry.get(), "X 坐标", -1_000_000, 1_000_000)
            y = parse_int(self.y_entry.get(), "Y 坐标", -1_000_000, 1_000_000)
        except ValueError as exc:
            self._notify(str(exc), "red")
            return
        self._set_position(x, y, None)

    def _preview_changed(self, x: int, y: int) -> None:
        if self.position_mode.get() == "固定位置":
            self._set_position(x, y, None, save=False)

    def _open_overlay(self, picker_class) -> None:
        if self.overlay or self._closing:
            return
        self._cancel_countdown()
        if self.engine.running:
            self.engine.stop()
        self.screen = virtual_screen(self.winfo_screenwidth(), self.winfo_screenheight())
        self.withdraw()
        try:
            self.overlay = picker_class(self, self.screen, self._picked, self._pick_cancelled)
        except Exception as exc:
            LOG.exception("取点窗口创建失败")
            self.overlay = None
            self.show_window()
            self._show_error("无法取点", str(exc))

    def open_area_picker(self) -> None:
        self._open_overlay(AreaPicker)

    def open_point_picker(self) -> None:
        self._open_overlay(PointPicker)

    def _picked(self, x: int, y: int, area=None) -> None:
        self.overlay = None
        self.show_window()
        self._set_position(x, y, area)
        if area is None:
            self.jitter.set(0)
            self._jitter_changed(0)
            self.config["jitter_pct"] = 0
        self._beep("ok")
        self._notify("点击位置已更新", "green")

    def _pick_cancelled(self) -> None:
        self.overlay = None
        self.show_window()
        self._notify("已取消取点", "muted")

    # ---------------- 预设 ----------------
    def _all_presets(self) -> dict:
        return {**BUILTIN_PRESETS, **self.config.get("presets", {})}

    def _refresh_presets(self, selected: str | None = None) -> None:
        names = list(self._all_presets())
        self.preset_box.configure(values=names)
        self.preset_box.set(selected if selected in names else names[0])

    def apply_preset(self, name: str) -> None:
        preset = self._all_presets().get(name)
        if not preset:
            return
        self.interval.set(str(preset["interval_ms"]))
        self.button_mode.set(next(key for key, value in BUTTONS.items() if value == preset["button"]))
        self.click_mode.set(next(key for key, value in CLICK_MODES.items() if value == preset["click_mode"]))
        self.limit_mode.set("指定次数" if preset["limit"] else "无限")
        self._set_entry(self.limit_entry, str(preset["limit"] or 100))
        self._limit_changed(self.limit_mode.get())
        self.jitter.set(preset["jitter_pct"])
        self._jitter_changed(preset["jitter_pct"])
        self._update_rate()
        self._notify(f"已应用预设“{name}”", "green")

    def save_preset(self) -> None:
        try:
            candidate = self._collect_config()
        except ValueError as exc:
            self._notify(str(exc), "red")
            return
        dialog = ctk.CTkInputDialog(title="保存预设", text="预设名称（最多 40 个字符）")
        name = (dialog.get_input() or "").strip()
        if not name:
            return
        if len(name) > 40 or name in BUILTIN_PRESETS:
            self._notify("名称过长，或与内置预设重名", "red")
            return
        self.config["presets"][name] = {key: candidate[key] for key in PRESET_KEYS}
        if self._save_quietly():
            self._refresh_presets(name)
            self._notify(f"已保存预设“{name}”", "green")

    def delete_preset(self) -> None:
        name = self.preset_box.get()
        if name in BUILTIN_PRESETS:
            self._notify("内置预设不可删除", "orange")
            return
        if name not in self.config.get("presets", {}):
            return
        if messagebox.askyesno("删除预设", f"确定删除“{name}”吗？", parent=self):
            del self.config["presets"][name]
            if self._save_quietly():
                self._refresh_presets()
                self._notify("预设已删除", "green")

    # ---------------- 热键、导入导出与帮助 ----------------
    def _start_hotkeys(self) -> None:
        try:
            self.hotkeys.start(self.config["hotkeys"])
            self.config["hotkeys"] = self.hotkeys.hotkeys
        except HotkeyError as exc:
            LOG.error("%s", exc)
            self.after(250, lambda: self._show_warning("热键不可用", f"{exc}\n\n可在“设置”中修改热键；界面按钮仍可正常使用。"))
            self._update_hotkey_labels(DEFAULT_HOTKEYS)

    def apply_preferences(self, hotkeys: dict[str, str], close_choice: str) -> None:
        previous_hotkeys = self.config["hotkeys"]
        try:
            self.hotkeys.start(hotkeys)
        except Exception:
            # start 失败前会停止旧监听，尽力恢复旧配置。
            try:
                self.hotkeys.start(previous_hotkeys)
            except Exception:
                LOG.exception("旧热键恢复失败")
            raise
        self.config["hotkeys"] = self.hotkeys.hotkeys
        self.config["close_choice"] = close_choice
        self.store.save(self.config)
        self._update_hotkey_labels(hotkeys)
        self._notify("设置已保存", "green")

    def _update_hotkey_labels(self, hotkeys: dict[str, str]) -> None:
        def short(event: str) -> str:
            return hotkeys.get(event, DEFAULT_HOTKEYS[event]).replace("<", "").replace(">", "").upper()
        self.area_button.configure(text=f"区域选点  {short('pick')}")
        if not self.engine.running and self._countdown_end is None:
            self.start_button.configure(text=f"开始点击  {short('toggle')}")
        self.pause_button.configure(text=f"暂停  {short('pause')}" if not self.engine.paused else f"继续  {short('pause')}")

    def export_config(self, path: str) -> None:
        try:
            self.store.save(self._collect_config())
            self.store.export(self._collect_config(), path)
        except (ConfigError, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    def import_config(self, path: str) -> None:
        try:
            imported = self.store.import_file(path)
            self.store.save(imported)
        except ConfigError as exc:
            raise RuntimeError(str(exc)) from exc
        self.config = imported
        self._load_into_form()
        apply_mode(self.config["theme"])
        self._refresh_theme()
        try:
            self.hotkeys.start(self.config["hotkeys"])
            self.config["hotkeys"] = self.hotkeys.hotkeys
        except HotkeyError as exc:
            self._show_warning("热键提示", str(exc))
        self._update_hotkey_labels(self.config["hotkeys"])
        self._notify("配置已导入", "green")

    def show_settings(self) -> None:
        SettingsDialog(self)

    def show_help(self) -> None:
        try:
            text = resource_path("README.md").read_text(encoding="utf-8")
        except OSError:
            text = "未找到使用说明。请查看项目目录中的 README.md。"
        TextDialog(self, "使用说明", text)

    # ---------------- 运行控制 ----------------
    def toggle_start(self) -> None:
        if self.overlay or self._closing:
            return
        if self.engine.running:
            self.engine.stop()
            self._run_started = None
            self._beep("warn")
            self._refresh_state()
            return
        if self._countdown_end is not None:
            self._cancel_countdown()
            self._notify("倒计时已取消", "orange")
            return
        try:
            candidate = self._collect_config()
            settings = ClickSettings.from_mapping(candidate)
            self.store.save(candidate)
        except (ValueError, ConfigError) as exc:
            self._show_error("无法开始", str(exc))
            return
        self.config = candidate
        if candidate["start_delay"]:
            self._countdown_end = time.monotonic() + candidate["start_delay"]
            self._notify(f"将在 {candidate['start_delay']} 秒后开始，请切换到目标窗口", "orange", sticky=True)
        else:
            self._start_engine(settings)
        self._refresh_state()

    def _start_engine(self, settings: ClickSettings | None = None) -> None:
        self._countdown_end = None
        self._notice_until = 0.0
        if settings is None:
            settings = ClickSettings.from_mapping(self.config)
        if self.engine.start(settings):
            self._run_started = time.monotonic()
            self._beep("ok")
        self._refresh_state()

    def _cancel_countdown(self) -> None:
        self._countdown_end = None
        self._refresh_state()

    def toggle_pause(self) -> None:
        if self.engine.paused:
            self.engine.resume()
        elif self.engine.running:
            self.engine.pause()
        self._refresh_state()

    def emergency_stop(self) -> None:
        self._countdown_end = None
        self.engine.stop()
        self._run_started = None
        if self.overlay:
            self.overlay.cancel()
        self._beep("warn")
        self._notify("已紧急停止", "red")
        self._refresh_state()

    def _engine_stopped(self, reason: str) -> None:
        if self.engine.running:
            return  # 忽略上一轮延迟送达的回调，避免覆盖新任务状态。
        self._run_started = None
        if reason == "completed":
            self._beep("info")
            self._notify("已达到指定次数，任务完成", "green")
        elif reason == "error":
            self._beep("error")
            self._show_error("点击已停止", f"鼠标操作失败：{self.engine.last_error}")
        elif reason.startswith("smart_stop:"):
            text = "检测到区域画面突变" if reason.endswith("changed") else "检测到连续多次点击无画面反馈"
            self._beep("info")
            self._notify(f"智能停止：{text}", "orange")
        self._refresh_state()

    def _refresh_state(self) -> None:
        if self._closing:
            return
        palette = colors()
        toggle = self.config["hotkeys"].get("toggle", "<f6>").replace("<", "").replace(">", "").upper()
        pause = self.config["hotkeys"].get("pause", "<f7>").replace("<", "").replace(">", "").upper()
        if self._countdown_end is not None:
            remaining = max(0, math.ceil(self._countdown_end - time.monotonic()))
            self.start_button.configure(text=f"取消倒计时  {remaining}s", fg_color=palette["orange"])
            self.pause_button.configure(state="disabled")
            self.status_label.configure(text=f"● 等待启动 · {remaining} 秒", text_color=palette["orange"])
        elif self.engine.running:
            paused = self.engine.paused
            self.start_button.configure(text=f"停止  {toggle}", fg_color=palette["red"], hover_color=palette["red_hover"])
            self.pause_button.configure(state="normal", text=f"{'继续' if paused else '暂停'}  {pause}")
            self.status_label.configure(text="● 已暂停" if paused else "● 正在点击", text_color=palette["orange"] if paused else palette["green"])
        else:
            self.start_button.configure(text=f"开始点击  {toggle}", fg_color=palette["green"], hover_color=palette["green_hover"])
            self.pause_button.configure(state="disabled", text=f"暂停  {pause}")
            if time.monotonic() >= self._notice_until:
                self.status_label.configure(text="● 就绪", text_color=palette["muted"])

    def _notify(self, text: str, color: str = "muted", sticky: bool = False) -> None:
        if self._closing:
            return
        self.status_label.configure(text=text, text_color=colors().get(color, colors()["muted"]))
        self._notice_until = time.monotonic() + (3600 if sticky else 3.0)

    # ---------------- 状态、关闭与音效 ----------------
    def _poll(self) -> None:
        if self._closing:
            return
        if self._countdown_end is not None and time.monotonic() >= self._countdown_end:
            try:
                self._start_engine()
            except ValueError as exc:
                self._countdown_end = None
                self._show_error("无法开始", str(exc))
        self._refresh_state()
        elapsed = max(0, int(time.monotonic() - self._run_started)) if self._run_started is not None else 0
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
        limit = self.config.get("limit", 0)
        count_text = f"点击 {self.engine.count}/{limit} 次" if limit else f"点击 {self.engine.count} 次"
        mouse = (self.winfo_pointerx(), self.winfo_pointery())
        self.metrics_label.configure(text=f"{count_text}   运行 {duration}   鼠标 ({mouse[0]}, {mouse[1]})")
        self._poll_job = self.after(300 if self.low_var.get() else 100, self._poll)

    def _beep(self, kind: str) -> None:
        if not self.sound_var.get():
            return
        try:
            import winsound
            sound = {"ok": winsound.MB_OK, "info": winsound.MB_ICONASTERISK,
                     "warn": winsound.MB_ICONWARNING, "error": winsound.MB_ICONHAND}.get(kind, winsound.MB_OK)
            winsound.MessageBeep(sound)
        except Exception:
            LOG.debug("提示音播放失败", exc_info=True)

    def request_close(self) -> None:
        choice = self.config.get("close_choice", "")
        if not choice:
            dialog = CloseDialog(self)
            self.wait_window(dialog)
            if not dialog.choice:
                return
            raw = dialog.choice
            choice = raw.removesuffix(":once")
            if not raw.endswith(":once"):
                self.config["close_choice"] = choice
                self._save_quietly()
        if choice == "tray":
            self.withdraw()
            if not self.tray.start():
                self.show_window()
                self._show_error("托盘不可用", "无法最小化到系统托盘，请使用设置中的“完全退出”。")
        else:
            self.quit()

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except tk.TclError:
                pass
        self._countdown_end = None
        self.hotkeys.stop()
        self.engine.stop()
        self.tray.stop()
        if self.overlay:
            try:
                self.overlay.win.destroy()
            except tk.TclError:
                pass
            self.overlay = None
        try:
            self.store.save(self._collect_config())
        except (ConfigError, ValueError, tk.TclError):
            LOG.exception("退出时保存配置失败")
        self.destroy()

    def _show_error(self, title: str, text: str) -> None:
        LOG.error("%s：%s", title, text)
        if not self._closing:
            messagebox.showerror(title, text, parent=self)
        self._notify(text, "red")

    def _show_warning(self, title: str, text: str) -> None:
        if not self._closing:
            messagebox.showwarning(title, text, parent=self)
