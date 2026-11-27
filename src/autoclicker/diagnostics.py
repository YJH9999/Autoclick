"""无需真实鼠标操作的核心自检，可用于打包后快速验证。"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from .config import ConfigStore
from .engine import ClickEngine
from .hotkeys import validate_hotkeys
from .models import DEFAULT_CONFIG, DEFAULT_HOTKEYS, ClickSettings


class FakeMouse:
    def __init__(self) -> None:
        self.position = (10, 20)
        self.clicks = 0

    def click(self, button: str, count: int = 1) -> None:
        self.clicks += count


def self_test() -> bool:
    checks = []
    try:
        settings = ClickSettings.from_mapping({**DEFAULT_CONFIG, "limit": 3, "interval_ms": 2})
        mouse = FakeMouse()
        engine = ClickEngine(mouse=mouse)
        assert engine.start(settings)
        deadline = time.monotonic() + 3
        while engine.running and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not engine.running and engine.count == 3 and mouse.clicks == 3
        checks.append("点击引擎与次数限制")
        validate_hotkeys(DEFAULT_HOTKEYS)
        checks.append("热键配置校验")
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            store.save(dict(DEFAULT_CONFIG))
            loaded, warning = store.load()
            assert not warning and loaded["interval_ms"] == 100
        checks.append("配置原子保存与读取")
    except Exception as exc:
        print(f"自检失败：{exc}")
        return False
    for name in checks:
        print(f"通过：{name}")
    print("核心自检全部通过；测试未移动真实鼠标。")
    return True
