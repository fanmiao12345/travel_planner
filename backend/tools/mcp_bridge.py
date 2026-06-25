"""
MCP 工具桥接器

将 mcp_servers/ 中的工具注册到 ToolRegistry，
使 Skill 系统可以通过统一接口调用 MCP 工具。
"""

from __future__ import annotations

from .base import ToolDef
from .registry import ToolRegistry


def register_mcp_tools() -> None:
    """将所有 MCP server 工具桥接到 ToolRegistry。"""
    registry = ToolRegistry()

    # ── 天气工具 ─────────────────────────────────────────
    from mcp_servers.weather_server import get_weather_forecast, get_air_quality

    weather_tools = [
        ToolDef(
            name="mcp_get_weather_forecast",
            description="查询城市天气预报（Open-Meteo API）",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                    "days": {"type": "integer", "description": "天数", "default": 3},
                },
                "required": ["city"],
            },
            func=get_weather_forecast,
            capabilities=["weather", "travel"],
        ),
        ToolDef(
            name="mcp_get_air_quality",
            description="查询城市空气质量（Open-Meteo API）",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                },
                "required": ["city"],
            },
            func=get_air_quality,
            capabilities=["weather", "travel"],
        ),
    ]

    # ── 交通工具 ─────────────────────────────────────────
    from mcp_servers.transport_server import (
        search_flights,
        search_trains,
        compare_transport,
        plan_driving_route,
    )

    transport_tools = [
        ToolDef(
            name="mcp_search_flights",
            description="搜索航班信息",
            parameters={
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "出发城市"},
                    "destination": {"type": "string", "description": "到达城市"},
                    "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
                },
                "required": ["origin", "destination"],
            },
            func=search_flights,
            capabilities=["transport", "travel"],
        ),
        ToolDef(
            name="mcp_search_trains",
            description="搜索火车信息",
            parameters={
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "出发城市"},
                    "destination": {"type": "string", "description": "到达城市"},
                    "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
                },
                "required": ["origin", "destination"],
            },
            func=search_trains,
            capabilities=["transport", "travel"],
        ),
        ToolDef(
            name="mcp_compare_transport",
            description="对比交通方案",
            parameters={
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "出发城市"},
                    "destination": {"type": "string", "description": "到达城市"},
                    "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
                },
                "required": ["origin", "destination"],
            },
            func=compare_transport,
            capabilities=["transport", "travel"],
        ),
        ToolDef(
            name="mcp_plan_driving_route",
            description="规划驾车路线（高德/OSRM）",
            parameters={
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "出发地"},
                    "destination": {"type": "string", "description": "目的地"},
                    "waypoints": {"type": "string", "description": "途经点"},
                    "departure_time": {"type": "string", "description": "出发时间"},
                },
                "required": ["origin", "destination"],
            },
            func=plan_driving_route,
            capabilities=["transport", "travel"],
        ),
    ]

    # ── 住宿/餐饮工具 ────────────────────────────────────
    from mcp_servers.accommodation_server import (
        search_hotels,
        search_restaurants,
        get_food_guide,
    )

    accommodation_tools = [
        ToolDef(
            name="mcp_search_hotels",
            description="搜索酒店",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市"},
                    "checkin": {"type": "string", "description": "入住日期"},
                    "checkout": {"type": "string", "description": "离店日期"},
                    "budget": {"type": "string", "description": "预算"},
                },
                "required": ["city"],
            },
            func=search_hotels,
            capabilities=["accommodation", "travel"],
        ),
        ToolDef(
            name="mcp_search_restaurants",
            description="搜索餐厅",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市"},
                    "cuisine": {"type": "string", "description": "菜系"},
                    "budget_per_meal": {"type": "string", "description": "每餐预算"},
                },
                "required": ["city"],
            },
            func=search_restaurants,
            capabilities=["food", "travel"],
        ),
        ToolDef(
            name="mcp_get_food_guide",
            description="获取城市美食攻略",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市"},
                },
                "required": ["city"],
            },
            func=get_food_guide,
            capabilities=["food", "travel"],
        ),
    ]

    # ── 搜索工具 ─────────────────────────────────────────
    from mcp_servers.search_server import (
        web_search,
        search_travel_guide,
        search_trending_places,
        search_event_schedule,
    )

    search_tools = [
        ToolDef(
            name="mcp_web_search",
            description="通用 Web 搜索（Tavily/DuckDuckGo）",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
            func=web_search,
            capabilities=["search", "web"],
        ),
        ToolDef(
            name="mcp_search_travel_guide",
            description="搜索旅游攻略",
            parameters={
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "目的地"},
                    "days": {"type": "integer", "description": "天数"},
                    "style": {"type": "string", "description": "风格"},
                },
                "required": ["destination"],
            },
            func=search_travel_guide,
            capabilities=["search", "travel"],
        ),
        ToolDef(
            name="mcp_search_trending_places",
            description="搜索热门景点",
            parameters={
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "目的地"},
                    "count": {"type": "integer", "description": "数量"},
                },
                "required": ["destination"],
            },
            func=search_trending_places,
            capabilities=["search", "travel"],
        ),
        ToolDef(
            name="mcp_search_event_schedule",
            description="搜索活动日程",
            parameters={
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "目的地"},
                    "event_name": {"type": "string", "description": "活动名"},
                    "date_hint": {"type": "string", "description": "日期提示"},
                },
                "required": ["destination"],
            },
            func=search_event_schedule,
            capabilities=["search", "travel"],
        ),
    ]

    # ── 注册所有工具 ─────────────────────────────────────
    all_tools = weather_tools + transport_tools + accommodation_tools + search_tools
    for tool in all_tools:
        try:
            registry.register(tool)
        except ValueError:
            pass  # 已注册
