"""
🌤️ 天气预报员 Agent

职责：查询目的地天气预报，给出穿衣和出行建议
知识点：create_react_agent、MCP 工具集成、数据解读与建议生成
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from config import config


@tool
def get_weather_forecast_tool(city: str, days: int = 3) -> str:
    """查询真实天气预报。

    Args:
        city: 城市、区县或目的地名称
        days: 预报天数
    """
    # Open-Meteo 支持未来最多 16 天左右的预报。
    # 工具内部会把异常包装成 error 字段，Agent 需要如实告诉用户。
    from mcp_servers.weather_server import get_weather_forecast
    return get_weather_forecast(city, days)


@tool
def get_air_quality_tool(city: str) -> str:
    """查询空气质量。

    Args:
        city: 城市、区县或目的地名称
    """
    # 空气质量同样走 Open-Meteo，适合给老人/孩子/户外活动做提醒。
    from mcp_servers.weather_server import get_air_quality
    return get_air_quality(city)


def create_weather_forecaster_agent(mcp_tools: list = None):
    """创建天气预报员 Agent。

    Args:
        mcp_tools: 从 MCP Server 获取的天气工具列表

    知识点：
    - 职责单一原则：每个 Agent 专注一个领域
    - 数据解读：不只是返回原始数据，还要给出有意义的建议
    """
    # 即使外部没有传入 MCP 工具，也默认具备天气和空气质量查询能力。
    tools = (mcp_tools or []) + [get_weather_forecast_tool, get_air_quality_tool]

    return create_react_agent(
        model=config.get_llm(),
        tools=tools,
        name="weather_forecaster",
        prompt="""你是天气预报员 🌤️，负责为用户提供目的地天气信息和实用建议。

你的职责：
1. 查询目的地的天气预报（温度、降水、风力等）
2. 查询空气质量信息
3. 根据天气情况给出穿衣建议
4. 根据天气调整行程建议（如雨天备选方案）
5. 提醒特殊天气注意事项

输出格式：
1. 📊 天气概览（温度范围、天气状况）
2. 👔 穿衣建议（根据温度和天气）
3. 🌂 出行提醒（是否带伞、防晒等）
4. ⚠️ 特殊提醒（高温预警、暴雨预警等）
5. 📅 行程调整建议（如果天气不佳，建议调整顺序）

注意：
- 使用工具查询真实天气数据
- 穿衣建议要具体（如"短袖+薄外套"而非"适当穿衣"）
- 如果天气服务返回 error 字段，要明确告诉用户天气查询失败，并给出出行前二次确认建议""",
    )
