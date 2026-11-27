"""进程入口与全局异常边界。"""
from __future__ import annotations

import ctypes
import logging
import sys

from .app import AutoClickerApp
from .diagnostics import self_test
from .logging_setup import configure_logging
from .platform import SingleInstance, activate_existing_window, enable_dpi_awareness

LOG = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    if "--self-test" in sys.argv or "--selftest" in sys.argv:
        raise SystemExit(0 if self_test() else 1)
    enable_dpi_awareness()
    instance = SingleInstance()
    if not instance.acquired:
        if not activate_existing_window() and ctypes.windll:
            ctypes.windll.user32.MessageBoxW(0, "AutoClicker 已在运行，请从任务栏或系统托盘恢复窗口。", "AutoClicker", 0x40)
        return
    app = None
    try:
        app = AutoClickerApp()
        app.report_callback_exception = lambda exc, value, tb: LOG.error("Tk 回调异常", exc_info=(exc, value, tb))
        app.mainloop()
    except Exception:
        LOG.exception("应用发生未处理异常")
        if app is not None:
            try:
                app.quit()
            except Exception:
                pass
        raise
    finally:
        instance.release()


if __name__ == "__main__":
    main()
