"""核心数据模型、默认值与输入校验（不依赖 GUI）。"""
from __future__ import annotations

from dataclasses import dataclass, fields
import math
from typing import Any, Mapping

APP_DIR_NAME = "AutoClicker"
CFG_VERSION = 6

DEFAULT_HOTKEYS = {
    "toggle": "<f6>",
    "pause": "<f7>",
    "pick": "<f8>",
    "emergency": "<f9>",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "cfg_version": CFG_VERSION,
    "x": 960,
    "y": 540,
    "area": None,
    "interval_ms": 100,
    "jitter_pct": 0,
    "button": "left",
    "click_mode": "single",
    "limit": 0,
    "position_mode": "fixed",
    "restore_cursor": False,
    "topmost": True,
    "sound": False,
    "start_delay": 0,
    "theme": "dark",
    "low_perf": False,
    "close_choice": "",
    "smart_stop": False,
    "hotkeys": dict(DEFAULT_HOTKEYS),
    "presets": {},
}

BUILTIN_PRESETS = {
    "网页按钮": {"interval_ms": 120, "jitter_pct": 15, "button": "left", "click_mode": "single", "limit": 0},
    "极速连点": {"interval_ms": 10, "jitter_pct": 0, "button": "left", "click_mode": "single", "limit": 0},
    "双击操作": {"interval_ms": 500, "jitter_pct": 30, "button": "left", "click_mode": "double", "limit": 20},
    "网页表单": {"interval_ms": 250, "jitter_pct": 10, "button": "left", "click_mode": "single", "limit": 0},
    "游戏拾取": {"interval_ms": 80, "jitter_pct": 20, "button": "left", "click_mode": "single", "limit": 0},
    "稳健点击": {"interval_ms": 1000, "jitter_pct": 30, "button": "left", "click_mode": "single", "limit": 0},
    "快速双击": {"interval_ms": 50, "jitter_pct": 10, "button": "left", "click_mode": "double", "limit": 50},
    "办公勾选": {"interval_ms": 400, "jitter_pct": 5, "button": "left", "click_mode": "single", "limit": 100},
}
PRESET_KEYS = ("interval_ms", "jitter_pct", "button", "click_mode", "limit")
HOTKEY_LABELS = {
    "toggle": "开始 / 停止",
    "pause": "暂停 / 继续",
    "pick": "区域选点",
    "emergency": "紧急停止",
}


def parse_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name}必须是整数")
    try:
        number = float(str(value).strip())
    except (ValueError, TypeError):
        raise ValueError(f"{name}请输入数字") from None
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"{name}必须是整数")
    number = int(number)
    if not minimum <= number <= maximum:
        raise ValueError(f"{name}需在 {minimum}～{maximum} 之间")
    return number


def parse_hotkeys(value: Any, fallback: Mapping[str, str] | None = None) -> dict[str, str]:
    """规范化 pynput 热键；非法或重复项回退，确保配置永远可加载。"""
    result = dict(fallback or DEFAULT_HOTKEYS)
    if isinstance(value, Mapping):
        for event in DEFAULT_HOTKEYS:
            candidate = value.get(event)
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            candidate = candidate.strip().lower().replace(" ", "")
            if len(candidate) <= 40:
                result[event] = candidate
    # 全局热键冲突会导致监听失效；重复绑定回退默认。
    if len(set(result.values())) != len(result):
        return dict(fallback or DEFAULT_HOTKEYS)
    return result


def normalize_area(value: Any) -> tuple[int, int, int, int] | None:
    if value is None or value == "":
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("选区格式无效")
    coordinates = [parse_int(v, "选区坐标", -1_000_000, 1_000_000) for v in value]
    x1, y1, x2, y2 = coordinates
    if x1 == x2 or y1 == y2:
        raise ValueError("选区宽度和高度必须大于 0")
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


@dataclass(frozen=True, slots=True)
class ClickSettings:
    x: int = 960
    y: int = 540
    area: tuple[int, int, int, int] | None = None
    interval_ms: int = 100
    jitter_pct: int = 0
    button: str = "left"
    click_mode: str = "single"
    limit: int = 0
    position_mode: str = "fixed"
    restore_cursor: bool = False
    smart_stop: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", parse_int(self.x, "X 坐标", -1_000_000, 1_000_000))
        object.__setattr__(self, "y", parse_int(self.y, "Y 坐标", -1_000_000, 1_000_000))
        object.__setattr__(self, "area", normalize_area(self.area))
        object.__setattr__(self, "interval_ms", parse_int(self.interval_ms, "点击间隔", 1, 3_600_000))
        object.__setattr__(self, "jitter_pct", parse_int(self.jitter_pct, "随机范围", 0, 100))
        object.__setattr__(self, "limit", parse_int(self.limit, "点击次数", 0, 10_000_000))
        if self.button not in ("left", "right", "middle"):
            raise ValueError("鼠标按键无效")
        if self.click_mode not in ("single", "double"):
            raise ValueError("点击方式无效")
        if self.position_mode not in ("fixed", "follow"):
            raise ValueError("位置模式无效")
        if not isinstance(self.restore_cursor, bool) or not isinstance(self.smart_stop, bool):
            raise ValueError("开关配置无效")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ClickSettings":
        names = {item.name for item in fields(cls)}
        return cls(**{name: value.get(name, DEFAULT_CONFIG[name]) for name in names})

    def to_dict(self) -> dict[str, Any]:
        return {item.name: getattr(self, item.name) for item in fields(self)}
