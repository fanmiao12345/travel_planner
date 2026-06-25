"""
Skill 注册表 (单例)

负责:
- Skill 注册/查询/列出
- 依赖拓扑排序 + 环检测
- 运行时守卫应用
- 启用/禁用持久化
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from .base import BaseSkill, SkillContext, SkillResult, SkillState
from .guards import (
    BudgetExhausted,
    RateLimiter,
    SensitiveDataFilter,
    SkillBudget,
    TimeoutGuard,
)

_PERSIST_PATH = Path.home() / ".travel_planner" / "skills.json"


class SkillRegistry:
    """Skill 注册表（单例模式）。"""

    _instance: SkillRegistry | None = None

    def __new__(cls) -> SkillRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills = {}
            cls._instance._disabled = set()
            cls._instance._guard_config = {}
            cls._instance._load_persisted()
        return cls._instance

    def register(self, skill: BaseSkill) -> None:
        """注册一个 Skill。重复注册抛出 ValueError。"""
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' 已注册")
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def list_metadata(self) -> list[dict[str, Any]]:
        """列出所有 Skill 的元数据。"""
        return [
            {
                "name": s.name,
                "description": s.description,
                "version": s.version,
                "enabled": self.is_enabled(s.name),
                "dependencies": s.dependencies,
            }
            for s in self._skills.values()
        ]

    def get_full_skill(self, name: str) -> dict[str, Any] | None:
        """获取 Skill 完整信息（含 prompt 模板）。"""
        skill = self._skills.get(name)
        if not skill:
            return None
        return {
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "enabled": self.is_enabled(name),
            "dependencies": skill.dependencies,
            "prompt_template": skill.get_prompt_template(),
            "full_content": skill.full_content,
            "references": skill.references,
        }

    def load(self, name: str, tier: str = "metadata") -> dict[str, Any] | None:
        """分层加载 Skill 信息。tier: metadata | fullcontent | references"""
        skill = self._skills.get(name)
        if not skill:
            return None
        result: dict[str, Any] = {
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "enabled": self.is_enabled(name),
        }
        if tier in ("fullcontent", "references"):
            result["prompt_template"] = skill.get_prompt_template()
            result["full_content"] = skill.full_content
        if tier == "references":
            result["references"] = skill.references
        return result

    def resolve_dependencies(self, name: str) -> list[BaseSkill]:
        """拓扑排序解析依赖。检测到环抛出 ValueError。"""
        visited: set[str] = set()
        stack: set[str] = set()
        order: list[BaseSkill] = []

        def _dfs(n: str) -> None:
            if n in stack:
                raise ValueError(f"检测到循环依赖: {n}")
            if n in visited:
                return
            stack.add(n)
            skill = self._skills.get(n)
            if skill:
                for dep in skill.dependencies:
                    _dfs(dep)
            stack.discard(n)
            visited.add(n)
            if skill:
                order.append(skill)

        _dfs(name)
        return order

    async def activate_with_dependencies(self, name: str) -> list[BaseSkill]:
        """激活 Skill 及其所有依赖。"""
        skills = self.resolve_dependencies(name)
        for skill in skills:
            if skill.state != SkillState.ACTIVATED:
                await skill.activate()
        return skills

    async def execute(self, name: str, context: SkillContext) -> SkillResult:
        """执行 Skill（带守卫）。"""
        skill = self._skills.get(name)
        if not skill:
            raise ValueError(f"Skill '{name}' 不存在")
        if not self.is_enabled(name):
            raise ValueError(f"Skill '{name}' 已禁用")

        # 激活依赖
        await self.activate_with_dependencies(name)

        # 合并 guard 配置
        guard_cfg = {**self._guard_config, **skill.guard_config}

        # 创建守卫
        budget = SkillBudget(max_tokens=guard_cfg.get("max_tokens", 100_000))
        rate_limiter = RateLimiter(
            max_calls=guard_cfg.get("max_calls", 20),
            window_seconds=guard_cfg.get("window_seconds", 60.0),
        )
        timeout_guard = TimeoutGuard(timeout_s=guard_cfg.get("timeout_s", 30.0))
        sensitive_filter = SensitiveDataFilter()

        # 执行
        skill._state = SkillState.RUNNING
        try:
            result = await timeout_guard.run(skill.execute(context))
            # 过滤敏感数据
            result.output = sensitive_filter.filter(result.output)
            return result
        finally:
            skill._state = SkillState.ACTIVATED

    def toggle(self, name: str) -> bool:
        """切换 Skill 启用/禁用状态。返回切换后的状态。"""
        if name not in self._skills:
            raise ValueError(f"Skill '{name}' 不存在")
        if name in self._disabled:
            self._disabled.discard(name)
        else:
            self._disabled.add(name)
        self._persist()
        return self.is_enabled(name)

    def is_enabled(self, name: str) -> bool:
        return name not in self._disabled

    def configure_guards(self, overrides: dict[str, Any]) -> None:
        """更新全局守卫配置。"""
        self._guard_config.update(overrides)

    def _persist(self) -> None:
        """持久化启用/禁用状态到文件。"""
        _PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PERSIST_PATH.write_text(
            json.dumps({"disabled": list(self._disabled)}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_persisted(self) -> None:
        """从文件加载启用/禁用状态。"""
        if _PERSIST_PATH.exists():
            try:
                data = json.loads(_PERSIST_PATH.read_text(encoding="utf-8"))
                self._disabled = set(data.get("disabled", []))
            except Exception:
                pass

    @classmethod
    def reset(cls) -> None:
        """重置单例（用于测试）。"""
        cls._instance = None
