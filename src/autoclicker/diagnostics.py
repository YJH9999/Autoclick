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
        checks.append("Click engine and operation limit")
        validate_hotkeys(DEFAULT_HOTKEYS)
        checks.append("Hotkey validation")
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            store.save(dict(DEFAULT_CONFIG))
            loaded, warning = store.load()
            assert not warning and loaded["interval_ms"] == 100
        checks.append("Atomic configuration save and load")
    except Exception as exc:
        print(f"Self-test failed: {ascii(exc)}")
        return False
    for name in checks:
        print(f"PASS: {name}")
    print("All core self-tests passed; no real mouse input was generated.")
    return True
