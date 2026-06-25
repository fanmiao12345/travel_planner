"""
自动调参器

根据指标趋势自动调整迭代预算等参数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .drift import DriftDetector
from .store import EvalStore


@dataclass
class TuningRule:
    metric: str
    condition: str      # "lt" | "gt"
    threshold: float
    action: str         # "increase_iterations" | "decrease_iterations"
    params: dict = field(default_factory=dict)


_DEFAULT_RULES = [
    TuningRule(metric="accuracy", condition="lt", threshold=0.4,
               action="increase_iterations", params={"delta": 5, "max": 120}),
    TuningRule(metric="total_latency_ms", condition="gt", threshold=30000,
               action="decrease_iterations", params={"delta": 3, "min": 5}),
]


class RuntimeOverrides:
    """进程级运行时参数覆盖。"""
    _overrides: dict[str, Any] = {}

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return cls._overrides.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        cls._overrides[key] = value

    @classmethod
    def clear(cls) -> None:
        cls._overrides.clear()

    @classmethod
    def get_all(cls) -> dict[str, Any]:
        return dict(cls._overrides)


class AutoOptimizer:
    """自动调参器。"""

    def __init__(
        self,
        store: EvalStore,
        drift_detector: DriftDetector | None = None,
        rules: list[TuningRule] | None = None,
    ) -> None:
        self._store = store
        self._drift = drift_detector
        self._rules = rules or _DEFAULT_RULES

    async def check_and_adjust(self) -> list[dict[str, Any]]:
        """检查指标并自动调整参数。返回调整日志。"""
        adjustments: list[dict[str, Any]] = []
        metrics_list = self._store.get_all_metrics()
        if not metrics_list:
            return adjustments

        # 计算最近指标均值
        recent = metrics_list[:10]
        avg_accuracy = sum(m.get("accuracy", 0) for m in recent) / len(recent)
        avg_latency = sum(m.get("total_latency_ms", 0) for m in recent) / len(recent)

        for rule in self._rules:
            value = avg_accuracy if rule.metric == "accuracy" else avg_latency
            triggered = False
            if rule.condition == "lt" and value < rule.threshold:
                triggered = True
            elif rule.condition == "gt" and value > rule.threshold:
                triggered = True

            if triggered:
                current = RuntimeOverrides.get("max_iterations", 50)
                if rule.action == "increase_iterations":
                    new_val = min(current + rule.params.get("delta", 5), rule.params.get("max", 120))
                    RuntimeOverrides.set("max_iterations", new_val)
                    adjustments.append({
                        "action": rule.action, "old": current, "new": new_val,
                        "reason": f"{rule.metric}={value:.3f} < {rule.threshold}",
                    })
                    self._store.save_optimization(rule.action, {"old": current, "new": new_val},
                                                   f"{rule.metric}={value:.3f}")
                elif rule.action == "decrease_iterations":
                    new_val = max(current - rule.params.get("delta", 3), rule.params.get("min", 5))
                    RuntimeOverrides.set("max_iterations", new_val)
                    adjustments.append({
                        "action": rule.action, "old": current, "new": new_val,
                        "reason": f"{rule.metric}={value:.0f} > {rule.threshold}",
                    })
                    self._store.save_optimization(rule.action, {"old": current, "new": new_val},
                                                   f"{rule.metric}={value:.0f}")

        return adjustments
