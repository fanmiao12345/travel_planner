"""
漂移检测器

滑动窗口基线对比，检测质量下降。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class DriftAlert:
    metric: str
    baseline: float
    current: float
    deviation: float
    message: str


class DriftDetector:
    """漂移检测器。"""

    def __init__(self, threshold: float = 0.2, min_samples: int = 3) -> None:
        self._threshold = threshold
        self._min_samples = min_samples
        self._windows: dict[str, deque[float]] = {}

    def record(self, metric: str, value: float) -> None:
        """记录一个指标值。"""
        window = self._windows.setdefault(metric, deque(maxlen=10))
        window.append(value)

    def get_baseline(self, metric: str) -> float | None:
        """获取指标基线（最近 10 个值的均值）。"""
        window = self._windows.get(metric)
        if not window or len(window) < self._min_samples:
            return None
        return sum(window) / len(window)

    def check(self, metric: str, current: float) -> list[DriftAlert]:
        """检查当前值是否偏离基线。"""
        baseline = self.get_baseline(metric)
        if baseline is None:
            return []
        if baseline == 0:
            return []
        deviation = abs(current - baseline) / baseline
        if deviation > self._threshold:
            direction = "下降" if current < baseline else "上升"
            return [DriftAlert(
                metric=metric, baseline=baseline, current=current,
                deviation=deviation,
                message=f"{metric} {direction} {deviation:.0%}: 基线 {baseline:.3f} → 当前 {current:.3f}",
            )]
        return []
