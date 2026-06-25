"""
工具注册表 (单例)

负责:
- 工具注册/查询/列出
- 按能力发现工具
- 工具调度执行
"""

from __future__ import annotations

import asyncio
from typing import Any

from .base import ToolDef


class ToolRegistry:
    """工具注册表（单例模式）。"""

    _instance: ToolRegistry | None = None

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, tool: ToolDef) -> None:
        """注册一个工具。重复注册抛出 ValueError。"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDef]:
        return list(self._tools.values())

    def discover(self, capability: str) -> list[ToolDef]:
        """按能力标签发现工具。"""
        return [
            t for t in self._tools.values()
            if capability in t.capabilities
        ]

    async def dispatch(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """查找并执行工具。支持 sync 和 async 函数。"""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"工具 '{name}' 不存在")
        if tool.func is None:
            raise ValueError(f"工具 '{name}' 未绑定函数")

        params = params or {}
        result = tool.func(**params)
        if asyncio.iscoroutine(result):
            return await result
        return result

    @classmethod
    def reset(cls) -> None:
        """重置单例（用于测试）。"""
        cls._instance = None
