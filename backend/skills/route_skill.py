"""
路线规划 Skill — 封装 route_planner agent
"""

from __future__ import annotations

from .base import BaseSkill, SkillContext, SkillResult
from .registry import SkillRegistry


class RouteSkill(BaseSkill):
    name = "route"
    description = "规划旅行路线，搜索热门景点、活动日程、驾车路线"
    version = "1.0.0"
    dependencies: list[str] = ["weather"]

    async def execute(self, context: SkillContext) -> SkillResult:
        from agents.route_planner import create_route_planner_agent
        from backend.core.config import get_settings

        agent = create_route_planner_agent()
        settings = get_settings()
        llm = settings.get_llm()
        agent_with_llm = agent.with_config({"configurable": {"llm": llm}})

        result = await agent_with_llm.ainvoke({
            "messages": [{"role": "user", "content": context.task}]
        })
        output = result["messages"][-1].content if result.get("messages") else str(result)
        return SkillResult(output=output, metadata={"skill": self.name})


SkillRegistry().register(RouteSkill())
