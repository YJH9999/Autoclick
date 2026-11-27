"""可选的区域画面变化检测；无截屏依赖时自动禁用。"""
from __future__ import annotations

from collections import deque
from typing import Any


class SmartStopMonitor:
    AREA = 48
    STREAK = 8
    NO_CHANGE_DIFF = 2.5
    CHANGED_DIFF = 55.0

    def __init__(self, capturer: Any = None):
        self.check_every = 3
        self._capturer = capturer
        self._own_capturer = capturer is None
        self._initial = None
        self._history = deque(maxlen=16)
        if self._capturer is None:
            try:
                import mss
                self._capturer = mss.mss()
            except Exception:
                self._capturer = None

    @staticmethod
    def _thumbnail(image: Any):
        if image is None:
            return None
        from PIL import Image
        if hasattr(image, "rgb"):
            image = Image.frombytes("RGB", image.size, image.rgb)
        return image.convert("L").resize((16, 16))

    @staticmethod
    def difference(first: Any, second: Any) -> float:
        from PIL import ImageChops
        histogram = ImageChops.difference(first, second).histogram()
        total = sum(histogram)
        return sum(index * count for index, count in enumerate(histogram)) / total if total else 0.0

    def _grab(self, x: int, y: int, area: tuple[int, int, int, int] | None):
        if self._capturer is None:
            return None
        if area:
            left, top, right, bottom = area
            # 大选区只比较中心 256×256，避免每几轮就抓取整张 4K 屏幕。
            max_side = 256
            if right - left > max_side:
                center = (left + right) // 2
                left, right = center - max_side // 2, center + max_side // 2
            if bottom - top > max_side:
                center = (top + bottom) // 2
                top, bottom = center - max_side // 2, center + max_side // 2
        else:
            half = self.AREA // 2
            left, top, right, bottom = x - half, y - half, x + half, y + half
        # 不能假定主屏从 (0,0) 开始；负坐标是多显示器的合法坐标。
        if right - left < 10 or bottom - top < 10:
            return None
        return self._capturer.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})

    def check(self, x: int, y: int, area: tuple[int, int, int, int] | None = None) -> str:
        if self._capturer is None:
            return ""
        current = self._thumbnail(self._grab(x, y, area))
        if current is None:
            return ""
        if self._initial is None:
            self._initial = current
            self._history.append(current)
            return ""
        if self.difference(current, self._initial) > self.CHANGED_DIFF:
            return "changed"
        self._history.append(current)
        if len(self._history) >= self.STREAK + 1:
            recent = list(self._history)[-(self.STREAK + 1):]
            if all(self.difference(recent[i], recent[i - 1]) < self.NO_CHANGE_DIFF for i in range(1, len(recent))):
                return "no_change"
        return ""

    def close(self) -> None:
        if self._own_capturer and self._capturer is not None:
            close = getattr(self._capturer, "close", None)
            if close:
                close()
        self._capturer = None
