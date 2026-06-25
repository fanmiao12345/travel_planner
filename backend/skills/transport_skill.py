"""
交通方案 Skill — 封装 transport_advisor agent
"""

from __future__ import annotations

from .base import BaseSkill, SkillContext, SkillResult
from .registry import SkillRegistry


class TransportSkill(BaseSkill):
    name = "transport"
    description = "搜索航班、火车、自驾路线，对比交通方案"
    version = "1.0.0"
    dependencies: list[str] = []

    async def execute(self, context: SkillContext) -> SkillResult:
        from agents.transport_advisor import create_transport_advisor_agent
        from backend.core.config import get_settings

        agent = create_transport_advisor_agent()
        settings = get_settings()
        llm = settings.get_llm()
        agent_with_llm = agent.with_config({"configurable": {"llm": llm}})

        result = await agent_with_llm.ainvoke({
            "messages": [{"role": "user", "content": context.task}]
        })
        output = result["messages"][-1].content if result.get("messages") else str(result)
        return SkillResult(output=output, metadata={"skill": self.name})


SkillRegistry().register(TransportSkill())
