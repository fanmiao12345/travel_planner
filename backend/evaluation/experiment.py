"""
A/B 实验运行器

支持加权随机变体分配、Welch's t-test 统计对比。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class ExperimentVariant:
    name: str
    config_overrides: dict = field(default_factory=dict)
    weight: float = 0.5
    description: str = ""


class ExperimentRunner:
    """A/B 实验运行器。"""

    def assign_variant(self, variants: dict[str, float]) -> str:
        """加权随机分配变体。"""
        names = list(variants.keys())
        weights = list(variants.values())
        total = sum(weights)
        r = random.random() * total
        cumulative = 0.0
        for name, weight in zip(names, weights):
            cumulative += weight
            if r <= cumulative:
                return name
        return names[-1]

    @staticmethod
    def compute_statistics(values: list[float]) -> dict:
        """计算基本统计量。"""
        if not values:
            return {"mean": 0, "std": 0, "count": 0}
        n = len(values)
        mean = sum(values) / n
        if n < 2:
            return {"mean": mean, "std": 0, "count": n}
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        return {"mean": mean, "std": math.sqrt(variance), "count": n}

    @staticmethod
    def welch_t_test(a: list[float], b: list[float]) -> dict:
        """Welch's t-test (不假设等方差)。"""
        na, nb = len(a), len(b)
        if na < 2 or nb < 2:
            return {"t": 0, "df": 0, "p_value": 1.0, "significant": False}

        ma = sum(a) / na
        mb = sum(b) / nb
        va = sum((x - ma) ** 2 for x in a) / (na - 1)
        vb = sum((x - mb) ** 2 for x in b) / (nb - 1)

        se = math.sqrt(va / na + vb / nb) if va / na + vb / nb > 0 else 1e-10
        t = (ma - mb) / se

        # Welch-Satterthwaite 自由度
        num = (va / na + vb / nb) ** 2
        den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
        df = num / den if den > 0 else 1

        # 近似 p 值 (双尾)
        p_value = 2.0 * (1.0 - _normal_cdf(abs(t)))

        return {
            "t": t, "df": df, "p_value": p_value,
            "significant": p_value < 0.05,
            "mean_a": ma, "mean_b": mb,
        }


def _normal_cdf(x: float) -> float:
    """标准正态 CDF (Abramowitz-Stegun 近似)。"""
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2)
    return 0.5 * (1.0 + sign * y)
