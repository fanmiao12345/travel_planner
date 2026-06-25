"""
线程安全迭代预算计数器

防止 Agent 进入无限循环。每次 LLM 调用前检查，耗尽则强制返回。
"""

from __future__ import annotations

import threading


class IterationBudget:
    """线程安全的迭代预算计数器。

    用法::

        budget = IterationBudget(max_iterations=50)
        if not budget.increment():
            return "已达最大迭代次数"
    """

    def __init__(self, max_iterations: int) -> None:
        self._max = max_iterations
        self._current = 0
        self._lock = threading.Lock()

    @property
    def current(self) -> int:
        return self._current

    @property
    def remaining(self) -> int:
        return max(0, self._max - self._current)

    @property
    def is_exhausted(self) -> bool:
        return self._current >= self._max

    def increment(self) -> bool:
        """原子递增。如果已达上限返回 False，否则递增并返回 True。"""
        with self._lock:
            if self._current >= self._max:
                return False
            self._current += 1
            return True

    def reset(self) -> None:
        """重置计数器。"""
        with self._lock:
            self._current = 0
