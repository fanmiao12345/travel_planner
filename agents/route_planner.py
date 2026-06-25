"""
🗺️ 路线规划师 Agent

职责：根据用户需求，规划合理的游玩路线和行程安排
知识点：create_react_agent、工具绑定、专业 prompt 设计
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from config import config
from tools.date_utils import get_current_datetime, get_date_range, calculate_duration
from tools.geo_utils import get_city_coordinates, calculate_distance


@tool
async def search_destination_guide(destination: str, days: int = 3, style: str = "经典") -> str:
    """搜索全国任意目的地的旅游攻略。

    Args:
        destination: 目的地城市或地区
        days: 出游天数
        style: 旅行风格
    """
    # 路线规划不要依赖内置模板，先走搜索工具拿目的地资料。
    from mcp_servers.search_server import search_travel_guide
    return await search_travel_guide(destination, days, style)


@tool
async def search_hot_places(destination: str, count: int = 5) -> str:
    """搜索目的地最近热门、网红打卡、新晋出圈地点。

    Args:
        destination: 目的地城市或地区
        count: 返回数量
    """
    from mcp_servers.search_server import search_trending_places
    return await search_trending_places(destination, count)


@tool
async def search_activity_schedule(destination: str, event_name: str, date_hint: str = "") -> str:
    """搜索活动、节庆、赛事、展会、演唱会等真实举办时间和地点。

    Args:
        destination: 目的地城市、区县或景区
        event_name: 活动名称或关键词
        date_hint: 用户提到的日期线索，例如“暑假”“国庆”“明天”“2026年7月”
    """
    # 活动时间是强事实字段，不能由日期工具往后推。
    # 这里统一交给搜索 MCP 去找官方/票务/公告类来源。
    from mcp_servers.search_server import search_event_schedule
    return await search_event_schedule(destination, event_name, date_hint)


@tool
def plan_map_route(origin: str, destination: str, waypoints: str = "", departure_time: str = "") -> str:
    """查询真实地图驾车路线或景点间路线。

    Args:
        origin: 起点
        destination: 终点
        waypoints: 途经点，多个地点可用逗号、分号或箭头分隔
        departure_time: 出发时间线索
    """
    # 跨城自驾和景点间移动使用地图路线工具，不使用直线距离估算。
    from mcp_servers.transport_server import plan_driving_route
    return plan_driving_route(origin, destination, waypoints, departure_time)


def create_route_planner_agent():
    """创建路线规划师 Agent。

    知识点：
    - create_react_agent: LangGraph 预构建的 ReAct Agent
    - tools: 工具列表，Agent 可自主决定调用哪个工具
    - prompt: 系统提示词，定义 Agent 的角色和行为
    """
    tools = [
        # 搜索类工具负责事实资料：攻略、热门地点、活动档期。
        search_destination_guide,
        search_hot_places,
        search_activity_schedule,
        # 地图类工具负责真实移动时间和路线。
        plan_map_route,
        # 日期/地理本地工具只做辅助计算，不替代搜索和地图。
        get_current_datetime,
        get_date_range,
        calculate_duration,
        get_city_coordinates,
        calculate_distance,
    ]

    return create_react_agent(
        model=config.get_llm(),
        tools=tools,
        name="route_planner",
        prompt="""你是路线规划师 🗺️，负责为用户规划合理的出游路线和行程。

你的职责：
1. 分析用户的出游需求（目的地、天数、风格）
2. 利用工具获取城市距离、日期信息和目的地资料
3. 生成详细的每日行程安排（上午/下午/晚上）
4. 使用地图路线工具核实跨城自驾、景点间移动顺序和大致车程
5. 根据旅行风格调整行程（经典/文艺/冒险/亲子/穷游）
6. 对全国任意目的地，必须先搜索当地攻略和最近热门/网红打卡点，再组织行程
7. 如果用户提到参加某个活动、节庆、赛事、展会、演唱会、音乐节、庙会等，必须先调用 search_activity_schedule 查询真实举办时间、地点和来源

输出要求：
- 每天的行程要有明确的时间段安排
- 标注关键景点的门票价格和游览时长
- 如果用户提到“最近很火、网红、热门、新晋、打卡”，必须调用搜索工具并说明信息来源是搜索摘要
- 如果用户是为某个活动出行，必须围绕查到的活动时间安排；没有查到确切日期时，要明确写“未能确认活动时间”，不能从当前日期往后推
- 自驾或跨区域移动时，要调用 plan_map_route，并基于返回距离/时长排序路线；如果地图工具返回 error，要说明无法核实路线
- 给出实用的游览小贴士
- 最后汇总总路线和关键信息

注意：
- 你需要主动调用搜索工具获取信息，不要凭空编造。
- 不要把出发地误当目的地；例如“从北京到张家口的蔚县”目的地是“蔚县”。
- 不要使用模板化景点A/景点B；资料不足时直接说明不足并列出需要确认的信息。
- 如果搜索结果不足，要明确说明资料不足，并给出需要用户确认的事项。""",
    )
