"""控制台与滚动文件日志，不记录配置内容或敏感信息。"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os

from .config import default_config_path


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(console)
    if os.environ.get("AUTOCLICKER_DISABLE_FILE_LOG") == "1":
        return
    try:
        path = default_config_path().parent / "logs" / "autoclicker.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    except OSError:
        root.warning("无法创建日志文件，仅保留控制台日志")
