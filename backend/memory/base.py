"""
记忆系统基础结构

定义 MemoryType、Memory、MemoryProvider ABC。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryType(Enum):
    """记忆类型。"""
    WORKING = "working"      # L1: 工作记忆（滑动窗口）
    EPISODIC = "episodic"    # L2: 情节记忆（SQLite + 向量检索）
    SEMANTIC = "semantic"    # L3: 语义记忆（用户画像）


@dataclass
class Memory:
    """记忆条目。"""
    id: str
    content: str
    memory_type: MemoryType
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class MemoryProvider(ABC):
    """记忆提供者抽象基类。"""

    @abstractmethod
    async def store(self, content: str, metadata: dict[str, Any]) -> str:
        """存储一条记忆。返回 ID。"""
        ...

    @abstractmethod
    async def recall(self, query: str, top_k: int = 5) -> list[Memory]:
        """检索相关记忆。"""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """清空所有记忆。"""
        ...
