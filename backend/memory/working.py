"""
L1 工作记忆 — deque 滑动窗口

内存中保留最近 N 轮对话，自动 FIFO 淘汰。
"""

from __future__ import annotations

from collections import deque
from typing import Any


class WorkingMemory:
    """滑动窗口工作记忆。"""

    def __init__(self, window_size: int = 20) -> None:
        self._messages: deque[dict[str, str]] = deque(maxlen=window_size)

    def add(self, role: str, content: str) -> None:
        """添加一条消息。"""
        self._messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        """获取所有消息。"""
        return list(self._messages)

    def get_context_string(self) -> str:
        """获取格式化的上下文字符串。"""
        lines = []
        for msg in self._messages:
            lines.append(f"{msg['role']}: {msg['content']}")
        return "\n".join(lines)

    def clear(self) -> None:
        """清空工作记忆。"""
        self._messages.clear()
