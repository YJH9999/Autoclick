"""可测试的后台点击引擎；所有回调都在工作线程触发。"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Callable, Protocol

from .models import ClickSettings
from .smart import SmartStopMonitor

LOG = logging.getLogger(__name__)


class Mouse(Protocol):
    position: tuple[int, int]
    def click(self, button: str, count: int = 1) -> None: ...


class PynputMouse:
    def __init__(self) -> None:
        from pynput.mouse import Controller
        self._controller = Controller()

    @property
    def position(self) -> tuple[int, int]:
        return tuple(self._controller.position)

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        self._controller.position = value

    def click(self, button: str, count: int = 1) -> None:
        from pynput.mouse import Button
        buttons = {"left": Button.left, "right": Button.right, "middle": Button.middle}
        self._controller.click(buttons[button], count)


class ClickEngine:
    """一次“点击”表示一轮操作；双击模式的物理按键事件为两次。"""

    def __init__(self, mouse: Mouse | None = None, smart_factory: Callable[[], SmartStopMonitor] = SmartStopMonitor):
        self._mouse = mouse if mouse is not None else PynputMouse()
        self._smart_factory = smart_factory
        self._stop_event = threading.Event()
        self._resume_event = threading.Event()
        self._resume_event.set()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._state = "idle"
        self._count = 0
        self._generation = 0
        self._last_error = ""
        self.on_progress: Callable[[int], None] | None = None
        self.on_stopped: Callable[[str], None] | None = None

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._state == "paused" and self.running

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    def start(self, settings: ClickSettings) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._generation += 1
            generation = self._generation
            self._stop_event.clear()
            self._resume_event.set()
            self._count = 0
            self._last_error = ""
            self._state = "running"
            self._thread = threading.Thread(
                target=self._run, args=(settings, generation),
                name="autoclicker-worker", daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> bool:
        self._stop_event.set()
        self._resume_event.set()
        with self._lock:
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
            if thread.is_alive():
                LOG.error("点击工作线程未能在超时时间内退出")
                return False
        return True

    def pause(self) -> None:
        with self._lock:
            if self._state == "running" and self._thread and self._thread.is_alive():
                self._resume_event.clear()
                self._state = "paused"

    def resume(self) -> None:
        with self._lock:
            if self._state == "paused" and self._thread and self._thread.is_alive():
                self._resume_event.set()
                self._state = "running"

    def random_position(self, settings: ClickSettings, rng: random.Random | None = None) -> tuple[int, int]:
        x, y = settings.x, settings.y
        if settings.area and settings.jitter_pct > 0:
            x1, y1, x2, y2 = settings.area
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            radius_x = max(1, int((x2 - x1) * settings.jitter_pct / 200))
            radius_y = max(1, int((y2 - y1) * settings.jitter_pct / 200))
            generator = rng or random
            x = generator.randint(cx - radius_x, cx + radius_x)
            y = generator.randint(cy - radius_y, cy + radius_y)
        return x, y

    def _click_once(self, settings: ClickSettings) -> tuple[int, int]:
        original = self._mouse.position if settings.restore_cursor else None
        position = tuple(self._mouse.position) if settings.position_mode == "follow" else self.random_position(settings)
        try:
            if settings.position_mode != "follow":
                self._mouse.position = position
            self._mouse.click(settings.button, 2 if settings.click_mode == "double" else 1)
            return position
        finally:
            if original is not None:
                self._mouse.position = original

    def _run(self, settings: ClickSettings, generation: int) -> None:
        reason = "stopped"
        smart = None
        try:
            # mss 在 Windows 上具有线程亲和性，必须由使用它的线程创建。
            smart = self._smart_factory() if settings.smart_stop else None
            next_deadline = time.monotonic()
            click_number = 0
            while not self._stop_event.is_set():
                if not self._resume_event.is_set():
                    self._stop_event.wait(0.05)
                    next_deadline = time.monotonic()
                    continue
                now = time.monotonic()
                if now < next_deadline:
                    self._stop_event.wait(min(next_deadline - now, 0.1))
                    continue
                try:
                    x, y = self._click_once(settings)
                except Exception as exc:  # 后端异常必须转化为可见状态，而非静默丢线程。
                    LOG.exception("鼠标点击失败")
                    with self._lock:
                        self._last_error = str(exc) or exc.__class__.__name__
                    reason = "error"
                    break
                with self._lock:
                    self._count += 1
                    count = self._count
                click_number += 1
                if self.on_progress:
                    try:
                        self.on_progress(count)
                    except Exception:
                        LOG.exception("点击进度回调失败")
                if settings.limit and count >= settings.limit:
                    reason = "completed"
                    break
                if smart and click_number % smart.check_every == 0:
                    try:
                        change = smart.check(x, y, settings.area)
                    except Exception:
                        LOG.exception("智能停止检测失败，本次运行关闭该检测")
                        smart = None
                    else:
                        if change:
                            reason = "smart_stop:" + change
                            break
                # 以单调时钟规划下一轮，避免累计 sleep 漂移；暂停后重新计时。
                next_deadline = max(next_deadline + settings.interval_ms / 1000, time.monotonic())
        finally:
            if smart is not None:
                try:
                    smart.close()
                except Exception:
                    LOG.debug("释放截屏资源失败", exc_info=True)
            with self._lock:
                if self._generation == generation:
                    self._state = "idle"
                    self._thread = None
            if self.on_stopped:
                try:
                    self.on_stopped(reason)
                except Exception:
                    LOG.exception("点击停止回调失败")
