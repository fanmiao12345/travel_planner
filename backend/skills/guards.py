"""
Skill 运行时守卫

4 正交保护:
- SkillBudget: Token 预算 (线程安全)
- RateLimiter: 滑动窗口限流
- SensitiveDataFilter: 正则替换敏感数据
- TimeoutGuard: asyncio 超时
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from collections import deque
from typing import Any


class GuardError(Exception):
    """守卫异常基类。"""


class BudgetExhausted(GuardError):
    """Token 预算耗尽。"""


class RateExceeded(GuardError):
    """调用频率超限。"""


class SkillTimeout(GuardError):
    """执行超时。"""


class SkillBudget:
    """Token 预算守卫（线程安全）。"""

    def __init__(self, max_tokens: int = 100_000) -> None:
        self.max_tokens = max_tokens
        self._spent = 0
        self._lock = threading.Lock()

    def consume(self, tokens: int) -> bool:
        """消耗 tokens。返回 False 如果超限。"""
        with self._lock:
            if self._spent + tokens > self.max_tokens:
                return False
            self._spent += tokens
            return True

    def check(self, tokens: int = 0) -> None:
        """检查是否还有预算。超限则抛出 BudgetExhausted。"""
        with self._lock:
            if self._spent + tokens > self.max_tokens:
                raise BudgetExhausted(
                    f"Token 预算耗尽: 已用 {self._spent}, 限额 {self.max_tokens}"
                )


class RateLimiter:
    """滑动窗口限流器（per-tool）。"""

    def __init__(self, max_calls: int = 20, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = {}

    def check(self, tool_name: str = "default") -> None:
        """检查是否超限。超限则抛出 RateExceeded。"""
        now = time.monotonic()
        window = self._windows.setdefault(tool_name, deque())
        # 清理过期记录
        while window and window[0] < now - self.window_seconds:
            window.popleft()
        if len(window) >= self.max_calls:
            raise RateExceeded(
                f"调用频率超限: {tool_name} 在 {self.window_seconds}s 内调用 {len(window)} 次"
            )
        window.append(now)


class SensitiveDataFilter:
    """敏感数据过滤器。"""

    # 默认模式: API keys, Bearer tokens, AWS keys, private keys
    DEFAULT_PATTERNS: list[tuple[str, str]] = [
        (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+', r'\1=[REDACTED]'),
        (r'(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*', r'Bearer [REDACTED]'),
        (r'(?i)(AKIA[0-9A-Z]{16})', r'[REDACTED_AWS_KEY]'),
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', r'[REDACTED_PRIVATE_KEY]'),
        (r'(?i)(secret|password|token)\s*[:=]\s*\S+', r'\1=[REDACTED]'),
    ]

    def __init__(self, patterns: list[tuple[str, str]] | None = None) -> None:
        self.patterns = patterns or self.DEFAULT_PATTERNS

    def filter(self, text: str) -> str:
        """替换敏感数据为 [REDACTED]。"""
        for pattern, replacement in self.patterns:
            text = re.sub(pattern, replacement, text)
        return text


class TimeoutGuard:
    """异步超时守卫。"""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s

    async def run(self, coro: Any) -> Any:
        """执行协程，超时则抛出 SkillTimeout。"""
        try:
            return await asyncio.wait_for(coro, timeout=self.timeout_s)
        except asyncio.TimeoutError:
            raise SkillTimeout(f"Skill 执行超时 ({self.timeout_s}s)")
