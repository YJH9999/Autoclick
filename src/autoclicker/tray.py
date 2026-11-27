"""按需创建的系统托盘；所有 Tk 操作都桥接回 UI 线程。"""
from __future__ import annotations

import logging
import threading

from PIL import Image

from .platform import resource_path

LOG = logging.getLogger(__name__)


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self._icon = None
        self._thread = None

    @property
    def active(self) -> bool:
        return self._icon is not None

    def start(self) -> bool:
        if self._icon is not None:
            return True
        try:
            import pystray
            path = resource_path("icon.ico")
            with Image.open(path) as source:
                image = source.convert("RGBA").resize((64, 64))
            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", lambda *_: self.app.after(0, self.app.show_window), default=True),
                pystray.MenuItem("开始 / 停止", lambda *_: self.app.after(0, self.app.toggle_start)),
                pystray.MenuItem("紧急停止", lambda *_: self.app.after(0, self.app.emergency_stop)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", lambda *_: self.app.after(0, self.app.quit)),
            )
            icon = pystray.Icon("AutoClicker", image, "AutoClicker 自动点击器", menu)
            self._icon = icon
            self._thread = threading.Thread(target=self._run, args=(icon,), name="autoclicker-tray", daemon=True)
            self._thread.start()
            return True
        except Exception:
            LOG.exception("系统托盘启动失败")
            self._icon = None
            return False

    def _run(self, icon) -> None:
        try:
            icon.run()
        except Exception:
            LOG.exception("系统托盘异常退出")

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                LOG.debug("系统托盘停止失败", exc_info=True)
