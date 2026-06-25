"""
预算优化 Skill — 封装 budget_optimizer agent
"""

from __future__ import annotations

from .base import BaseSkill, SkillContext, SkillResult
from .registry import SkillRegistry


class BudgetSkill(BaseSkill):
    name = "budget"
    description = "生成预算报告，对比消费方案，提供省钱建议"
    version = "1.0.0"
    dependencies: list[str] = ["transport", "accommodation", "food"]

    async def execute(self, context: SkillContext) -> SkillResult:
        from agents.budget_optimizer import create_budget_optimizer_agent
        from backend.core.config import get_settings

        agent = create_budget_optimizer_agent()
        settings = get_settings()
        llm = settings.get_llm()
        agent_with_llm = agent.with_config({"configurable": {"llm": llm}})

        result = await agent_with_llm.ainvoke({
            "messages": [{"role": "user", "content": context.task}]
        })
        output = result["messages"][-1].content if result.get("messages") else str(result)
        return SkillResult(output=output, metadata={"skill": self.name})


SkillRegistry().register(BudgetSkill())
