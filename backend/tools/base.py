"""
工具定义基础结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ToolDef:
    """工具定义。

    Attributes:
        name: 工具唯一标识
        description: 人类可读描述
        parameters: JSON Schema 参数定义
        func: 工具函数（sync 或 async）
        capabilities: 能力标签列表 (e.g. ["search", "web", "travel"])
    """
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    func: Callable[..., Awaitable[Any] | Any] = None  # type: ignore[assignment]
    capabilities: list[str] = field(default_factory=list)
