"""Windows 屏幕、DPI、单实例与窗口辅助函数。"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import logging
import os
import sys
from pathlib import Path

LOG = logging.getLogger(__name__)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    # 源码运行时资源在 assets/；PyInstaller 中直接位于临时根目录。
    candidate = base / name
    if candidate.exists():
        return candidate
    return base / "assets" / name


def enable_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        # Per-monitor v2，避免缩放环境下物理坐标与 pynput 坐标不一致。
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                LOG.debug("无法设置 DPI 感知", exc_info=True)


@dataclass(frozen=True, slots=True)
class VirtualScreen:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def clamp(self, x: int, y: int) -> tuple[int, int]:
        return max(self.left, min(self.right - 1, x)), max(self.top, min(self.bottom - 1, y))

    def to_relative(self, x: int, y: int) -> tuple[float, float]:
        return (x - self.left) / max(1, self.width), (y - self.top) / max(1, self.height)

    def from_relative(self, x: float, y: float) -> tuple[int, int]:
        return self.clamp(round(self.left + x * self.width), round(self.top + y * self.height))


def virtual_screen(fallback_width: int = 1920, fallback_height: int = 1080) -> VirtualScreen:
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
            left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
            width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
            if width > 0 and height > 0:
                return VirtualScreen(left, top, width, height)
        except Exception:
            LOG.debug("读取虚拟屏幕失败", exc_info=True)
    return VirtualScreen(0, 0, fallback_width, fallback_height)


class SingleInstance:
    """持有 Windows 命名互斥体；退出时显式释放。"""
    def __init__(self, name: str = r"Local\AutoClicker_SingleInstance_V5"):
        self._handle = None
        self.acquired = False
        if os.name != "nt":
            self.acquired = True
            return
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            ctypes.set_last_error(0)
            self._handle = kernel32.CreateMutexW(None, False, name)
            self.acquired = bool(self._handle) and ctypes.get_last_error() != 183
            if self._handle and not self.acquired:
                kernel32.CloseHandle(self._handle)
                self._handle = None
        except Exception:
            LOG.exception("单实例锁不可用，将继续启动")
            self.acquired = True

    def release(self) -> None:
        if self._handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None


def activate_existing_window(title: str = "AutoClicker") -> bool:
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            return True
    except Exception:
        LOG.debug("激活已有窗口失败", exc_info=True)
    return False
