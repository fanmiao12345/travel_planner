"""
住宿推荐 Skill — 封装 accommodation_manager agent
"""

from __future__ import annotations

from .base import BaseSkill, SkillContext, SkillResult
from .registry import SkillRegistry


class AccommodationSkill(BaseSkill):
    name = "accommodation"
    description = "搜索酒店和住宿推荐，按预算和风格筛选"
    version = "1.0.0"
    dependencies: list[str] = []

    async def execute(self, context: SkillContext) -> SkillResult:
        from agents.accommodation_manager import create_accommodation_manager_agent
        from backend.core.config import get_settings

        agent = create_accommodation_manager_agent()
        settings = get_settings()
        llm = settings.get_llm()
        agent_with_llm = agent.with_config({"configurable": {"llm": llm}})

        result = await agent_with_llm.ainvoke({
            "messages": [{"role": "user", "content": context.task}]
        })
        output = result["messages"][-1].content if result.get("messages") else str(result)
        return SkillResult(output=output, metadata={"skill": self.name})


SkillRegistry().register(AccommodationSkill())
