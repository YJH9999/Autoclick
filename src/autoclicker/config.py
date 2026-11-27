"""应用配置校验与原子持久化。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .models import (
    APP_DIR_NAME,
    BUILTIN_PRESETS,
    CFG_VERSION,
    DEFAULT_CONFIG,
    ClickSettings,
    parse_hotkeys,
)


class ConfigError(RuntimeError):
    """配置无法读取或保存。"""


def default_config_path() -> Path:
    override = os.environ.get("AUTOCLICKER_CONFIG_DIR")
    if override:
        return Path(override).expanduser() / "config.json"
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / APP_DIR_NAME / "config.json"


def normalize_config(raw: Any) -> dict[str, Any]:
    """从不可信 JSON 生成完整、有效的新配置；无效字段回退默认值。"""
    source = raw if isinstance(raw, dict) else {}
    cfg = dict(DEFAULT_CONFIG)
    cfg["hotkeys"] = dict(DEFAULT_CONFIG["hotkeys"])
    cfg["presets"] = {}
    try:
        settings = ClickSettings.from_mapping(source)
    except ValueError:
        # 文件可能部分损坏，逐字段恢复而不是丢弃整个配置。
        for key in ("x", "y", "area", "interval_ms", "jitter_pct", "button",
                    "click_mode", "limit", "position_mode", "restore_cursor", "smart_stop"):
            candidate = dict(cfg)
            candidate[key] = source.get(key, cfg[key])
            try:
                value = getattr(ClickSettings.from_mapping(candidate), key)
                cfg[key] = value
            except (ValueError, TypeError):
                pass
    else:
        cfg.update(settings.to_dict())

    for key in ("topmost", "sound", "low_perf"):
        if isinstance(source.get(key), bool):
            cfg[key] = source[key]
    if source.get("theme") in ("dark", "light"):
        cfg["theme"] = source["theme"]
    if source.get("close_choice") in ("", "tray", "quit"):
        cfg["close_choice"] = source["close_choice"]
    if source.get("start_delay") is not None:
        try:
            delay = int(source["start_delay"])
            if isinstance(source["start_delay"], bool) or not 0 <= delay <= 60:
                raise ValueError
            cfg["start_delay"] = delay
        except (ValueError, TypeError, OverflowError):
            pass
    cfg["hotkeys"] = parse_hotkeys(source.get("hotkeys"), DEFAULT_CONFIG["hotkeys"])

    presets = source.get("presets")
    if isinstance(presets, dict):
        for name, value in presets.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 40:
                continue
            if name in BUILTIN_PRESETS or not isinstance(value, dict):
                continue
            try:
                preset = ClickSettings.from_mapping({**cfg, **value})
            except ValueError:
                continue
            cfg["presets"][name.strip()] = {
                key: getattr(preset, key) for key in
                ("interval_ms", "jitter_pct", "button", "click_mode", "limit")
            }
    if isinstance(source.get("cfg_version"), int) and source["cfg_version"] < 3:
        cfg["sound"] = False
    cfg["cfg_version"] = CFG_VERSION
    return cfg


class ConfigStore:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path) if path else default_config_path()

    def load(self) -> tuple[dict[str, Any], str]:
        if not self.path.exists():
            return normalize_config({}), ""
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, dict):
                raise ValueError("配置根节点不是对象")
            return normalize_config(raw), ""
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return normalize_config({}), f"配置读取失败，已使用默认值：{exc}"

    def save(self, config: dict[str, Any]) -> None:
        clean = normalize_config(config)
        self._atomic_write(clean, self.path)

    def export(self, config: dict[str, Any], destination: str | os.PathLike[str]) -> None:
        self._atomic_write(normalize_config(config), Path(destination))

    def import_file(self, source: str | os.PathLike[str]) -> dict[str, Any]:
        path = Path(source)
        try:
            with path.open("r", encoding="utf-8") as handle:
                return normalize_config(json.load(handle))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfigError(f"无法导入配置：{exc}") from exc

    @staticmethod
    def _atomic_write(config: dict[str, Any], path: Path) -> None:
        temporary: str | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temporary = handle.name
                json.dump(config, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
            raise ConfigError(f"配置保存失败：{exc}") from exc
