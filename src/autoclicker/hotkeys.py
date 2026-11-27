"""全局热键生命周期、冲突检查与安全重载。"""
from __future__ import annotations

import logging
from typing import Callable, Mapping

from .models import DEFAULT_HOTKEYS, HOTKEY_LABELS

LOG = logging.getLogger(__name__)


class HotkeyError(ValueError):
    pass


def normalize_hotkey(value: str) -> str:
    """接受 F6、f6、<f6> 以及 ctrl+shift+k 等 pynput 格式。"""
    if not isinstance(value, str) or not value.strip():
        raise HotkeyError("热键不能为空")
    text = value.strip().lower().replace(" ", "")
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1]
    parts = [part for part in text.replace(">", "").replace("<", "").split("+") if part]
    if not parts:
        raise HotkeyError("热键格式无效")
    modifiers = {"ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r", "alt_gr", "shift", "shift_l", "shift_r", "cmd", "cmd_l", "cmd_r"}
    ordinary = [part for part in parts if part not in modifiers]
    if len(ordinary) != 1:
        raise HotkeyError("每个热键必须且只能包含一个普通按键")
    key = ordinary[0]
    valid_key = (len(key) == 1 and key.isprintable()) or (
        len(key) > 1 and key[1:].isdigit() and key[0] == "f" and 1 <= int(key[1:]) <= 24
    ) or key in {"space", "enter", "tab", "esc", "home", "end", "insert", "delete", "page_up", "page_down", "up", "down", "left", "right"}
    if not valid_key:
        raise HotkeyError(f"不支持的按键：{key}")
    normalized_modifiers = [f"<{part}>" for part in parts if part in modifiers]
    normalized_key = key if len(key) == 1 else f"<{key}>"
    return "+".join(normalized_modifiers + [normalized_key])


def validate_hotkeys(values: Mapping[str, str]) -> dict[str, str]:
    if set(values) != set(DEFAULT_HOTKEYS):
        raise HotkeyError("热键配置不完整")
    normalized = {name: normalize_hotkey(values[name]) for name in DEFAULT_HOTKEYS}
    seen: dict[str, str] = {}
    for event, key in normalized.items():
        if key in seen:
            raise HotkeyError(f"“{HOTKEY_LABELS[event]}”与“{HOTKEY_LABELS[seen[key]]}”的热键重复")
        seen[key] = event
    return normalized


class HotkeyManager:
    def __init__(self, listener_factory: Callable | None = None):
        self._listener_factory = listener_factory
        self._listener = None
        self._callbacks: dict[str, Callable[[], None]] = {}
        self._hotkeys = dict(DEFAULT_HOTKEYS)

    @property
    def active(self) -> bool:
        return self._listener is not None

    @property
    def hotkeys(self) -> dict[str, str]:
        return dict(self._hotkeys)

    def on(self, event: str, callback: Callable[[], None]) -> None:
        if event not in DEFAULT_HOTKEYS:
            raise ValueError(f"未知热键事件：{event}")
        self._callbacks[event] = callback

    def start(self, hotkeys: Mapping[str, str] | None = None) -> None:
        values = validate_hotkeys(hotkeys or self._hotkeys)
        if self._listener is not None:
            self.stop()
        factory = self._listener_factory
        if factory is None:
            from pynput import keyboard
            factory = keyboard.GlobalHotKeys
        mapping = {values[event]: self._dispatch(event) for event in values}
        try:
            listener = factory(mapping)
            listener.daemon = True
            listener.start()
        except Exception as exc:
            raise HotkeyError(f"全局热键启动失败：{exc}") from exc
        self._listener = listener
        self._hotkeys = values

    def _dispatch(self, event: str) -> Callable[[], None]:
        def invoke() -> None:
            callback = self._callbacks.get(event)
            if callback:
                try:
                    callback()
                except Exception:
                    LOG.exception("热键回调失败：%s", event)
        return invoke

    def stop(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                LOG.debug("热键监听停止失败", exc_info=True)
