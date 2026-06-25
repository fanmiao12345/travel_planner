"""
Skill 基础抽象

定义 BaseSkill ABC、SkillState、SkillContext、SkillResult、ResourceHandle。
所有旅行 Skill 继承 BaseSkill 并实现 execute()。
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillState(Enum):
    """Skill 生命周期状态。"""
    DISCOVERED = "discovered"
    ACTIVATED = "activated"
    RUNNING = "running"
    DEACTIVATED = "deactivated"


@dataclass
class SkillContext:
    """Skill 执行上下文。"""
    task: str
    query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    memory_context: str = ""


@dataclass
class SkillResult:
    """Skill 执行结果。"""
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "completed"


@dataclass
class ResourceHandle:
    """资源句柄，用于 Skill 清理。"""
    kind: str
    label: str
    _cleanup_fn: Any = None

    async def cleanup(self) -> None:
        if self._cleanup_fn:
            if asyncio.iscoroutinefunction(self._cleanup_fn):
                await self._cleanup_fn()
            else:
                self._cleanup_fn()


class BaseSkill(ABC):
    """Skill 基类。

    子类必须设置:
        name: str           — 唯一标识
        description: str    — 人类可读描述
        version: str        — 版本号
        dependencies: list  — 依赖的其他 Skill 名称

    并实现:
        async def execute(self, context: SkillContext) -> SkillResult
    """

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    dependencies: list[str] = []
    full_content: str = ""
    references: list[str] = []
    guard_config: dict[str, Any] = {}

    def __init__(self) -> None:
        self._state = SkillState.DISCOVERED
        self._resources: list[ResourceHandle] = []

    async def activate(self) -> None:
        """激活 Skill（分配资源）。"""
        self._state = SkillState.ACTIVATED

    async def deactivate(self) -> None:
        """停用 Skill（释放资源）。"""
        await self.cleanup()
        self._state = SkillState.DEACTIVATED

    def track_resource(self, kind: str, label: str, cleanup: Any) -> ResourceHandle:
        """注册一个需要清理的资源。"""
        handle = ResourceHandle(kind=kind, label=label, _cleanup_fn=cleanup)
        self._resources.append(handle)
        return handle

    async def release_resource(self, handle: ResourceHandle) -> None:
        """释放指定资源。"""
        await handle.cleanup()
        if handle in self._resources:
            self._resources.remove(handle)

    async def cleanup(self) -> None:
        """逆序释放所有资源（best-effort）。"""
        for handle in reversed(self._resources):
            try:
                await handle.cleanup()
            except Exception:
                pass
        self._resources.clear()

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """执行 Skill 逻辑。子类必须实现。"""
        ...

    def get_prompt_template(self) -> str:
        """获取 Skill 的 prompt 模板（用于 LLM）。"""
        return self.full_content or self.description

    @property
    def is_active(self) -> bool:
        return self._state in (SkillState.ACTIVATED, SkillState.RUNNING)

    @property
    def state(self) -> SkillState:
        return self._state
