"""
天气查询 Skill — 封装 weather_forecaster agent
"""

from __future__ import annotations

from .base import BaseSkill, SkillContext, SkillResult
from .registry import SkillRegistry


class WeatherSkill(BaseSkill):
    name = "weather"
    description = "查询目的地天气预报和空气质量，提供穿衣和出行建议"
    version = "1.0.0"
    dependencies: list[str] = []

    async def execute(self, context: SkillContext) -> SkillResult:
        from agents.weather_forecaster import create_weather_forecaster_agent
        from backend.core.config import get_settings

        agent = create_weather_forecaster_agent()
        settings = get_settings()
        llm = settings.get_llm()
        agent_with_llm = agent.with_config({"configurable": {"llm": llm}})

        result = await agent_with_llm.ainvoke({
            "messages": [{"role": "user", "content": context.task}]
        })
        output = result["messages"][-1].content if result.get("messages") else str(result)
        return SkillResult(output=output, metadata={"skill": self.name})


# 自注册
SkillRegistry().register(WeatherSkill())
