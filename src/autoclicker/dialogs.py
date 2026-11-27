"""设置、关闭确认与只读文本对话框。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .hotkeys import HotkeyError, validate_hotkeys
from .models import HOTKEY_LABELS
from .theme import FONT, colors


class Modal(ctk.CTkToplevel):
    def __init__(self, app, title: str, width: int, height: int):
        super().__init__(app)
        self.title(title)
        self.resizable(False, False)
        self.transient(app)
        self.attributes("-topmost", True)
        self.configure(fg_color=colors()["window"])
        self.update_idletasks()
        x = max(app.winfo_rootx() + (app.winfo_width() - width) // 2, 0)
        y = max(app.winfo_rooty() + (app.winfo_height() - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(50, self._focus)

    def _focus(self) -> None:
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass


class CloseDialog(Modal):
    def __init__(self, app):
        super().__init__(app, "关闭 AutoClicker", 410, 230)
        self.choice: str | None = None
        palette = colors()
        ctk.CTkLabel(self, text="关闭窗口后，要做什么？", font=(FONT, 16, "bold")).pack(pady=(22, 5))
        ctk.CTkLabel(self, text="后台运行时仍可通过全局热键控制。", font=(FONT, 11),
                     text_color=palette["muted"]).pack()
        self.value = tk.StringVar(value="tray")
        for text, value in (("最小化到托盘，保持当前任务", "tray"), ("停止点击并完全退出", "quit")):
            ctk.CTkRadioButton(self, text=text, value=value, variable=self.value,
                               font=(FONT, 12)).pack(anchor="w", padx=52, pady=5)
        self.remember = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="记住选择，不再询问", variable=self.remember,
                        font=(FONT, 11)).pack(anchor="w", padx=52, pady=(4, 10))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=52)
        ctk.CTkButton(row, text="确定", command=self._accept).pack(side="left", expand=True, padx=(0, 5))
        ctk.CTkButton(row, text="取消", command=self.destroy, fg_color=palette["surface_2"],
                      hover_color=palette["border"]).pack(side="left", expand=True, padx=(5, 0))

    def _accept(self) -> None:
        self.choice = self.value.get()
        if not self.remember.get():
            self.choice = self.choice + ":once"
        self.destroy()


class SettingsDialog(Modal):
    def __init__(self, app):
        self.app = app
        super().__init__(app, "首选项", 500, 510)
        palette = colors()
        ctk.CTkLabel(self, text="首选项", font=(FONT, 19, "bold")).pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text="热键格式示例：F6、Ctrl+Shift+K", font=(FONT, 11),
                     text_color=palette["muted"]).pack(anchor="w", padx=24, pady=(0, 14))
        self.entries: dict[str, ctk.CTkEntry] = {}
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=24)
        grid.grid_columnconfigure(1, weight=1)
        for row, (event, label) in enumerate(HOTKEY_LABELS.items()):
            ctk.CTkLabel(grid, text=label, font=(FONT, 12)).grid(row=row, column=0, sticky="w", pady=6)
            entry = ctk.CTkEntry(grid, height=32)
            entry.insert(0, app.config["hotkeys"][event])
            entry.grid(row=row, column=1, sticky="ew", padx=(20, 0), pady=6)
            self.entries[event] = entry
        ctk.CTkLabel(self, text="点击关闭按钮时", font=(FONT, 12)).pack(anchor="w", padx=24, pady=(16, 4))
        self.close_choice = ctk.CTkComboBox(self, values=["每次询问", "最小化到托盘", "完全退出"], state="readonly")
        current = {"": "每次询问", "tray": "最小化到托盘", "quit": "完全退出"}[app.config["close_choice"]]
        self.close_choice.set(current)
        self.close_choice.pack(fill="x", padx=24)
        self.error = ctk.CTkLabel(self, text="", text_color=palette["red"], font=(FONT, 11), wraplength=440)
        self.error.pack(fill="x", padx=24, pady=(10, 0))
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=24, pady=(12, 0))
        ctk.CTkButton(tools, text="导入配置", fg_color=palette["surface_2"], hover_color=palette["border"],
                      command=self._import).pack(side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(tools, text="导出配置", fg_color=palette["surface_2"], hover_color=palette["border"],
                      command=self._export).pack(side="left", expand=True, padx=4)
        ctk.CTkButton(tools, text="恢复默认热键", fg_color=palette["surface_2"], hover_color=palette["border"],
                      command=self._defaults).pack(side="left", expand=True, padx=(4, 0))
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=(22, 18), side="bottom")
        ctk.CTkButton(actions, text="取消", fg_color=palette["surface_2"], hover_color=palette["border"],
                      command=self.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(actions, text="保存设置", command=self._save).pack(side="right", padx=(0, 6))

    def _save(self) -> None:
        try:
            hotkeys = validate_hotkeys({key: entry.get() for key, entry in self.entries.items()})
            choice = {"每次询问": "", "最小化到托盘": "tray", "完全退出": "quit"}[self.close_choice.get()]
            self.app.apply_preferences(hotkeys, choice)
        except (HotkeyError, ValueError, RuntimeError) as exc:
            self.error.configure(text=str(exc))
            return
        self.destroy()

    def _defaults(self) -> None:
        from .models import DEFAULT_HOTKEYS
        for key, entry in self.entries.items():
            entry.delete(0, "end")
            entry.insert(0, DEFAULT_HOTKEYS[key])

    def _import(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="导入配置", filetypes=[("JSON 配置", "*.json")])
        if path:
            try:
                self.app.import_config(path)
            except RuntimeError as exc:
                messagebox.showerror("导入失败", str(exc), parent=self)
            else:
                self.destroy()

    def _export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self, title="导出配置", defaultextension=".json",
                                            initialfile="autoclicker-config.json", filetypes=[("JSON 配置", "*.json")])
        if path:
            try:
                self.app.export_config(path)
            except RuntimeError as exc:
                messagebox.showerror("导出失败", str(exc), parent=self)
            else:
                self.error.configure(text="配置已导出。", text_color=colors()["green"])


class TextDialog(Modal):
    def __init__(self, app, title: str, text: str):
        super().__init__(app, title, 560, 500)
        self.resizable(True, True)
        self.minsize(420, 340)
        box = ctk.CTkTextbox(self, font=(FONT, 11), wrap="word")
        box.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        box.insert("1.0", text)
        box.configure(state="disabled")
        ctk.CTkButton(self, text="关闭", command=self.destroy).pack(pady=(0, 14))
