"""
🚂 交通顾问 Agent

职责：查询和推荐机票、火车票等交通方案
知识点：create_react_agent、MCP 工具集成、多源数据对比
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from config import config


@tool
def plan_driving_route_tool(origin: str, destination: str, waypoints: str = "", departure_time: str = "") -> str:
    """查询真实地图驾车路线。

    Args:
        origin: 起点
        destination: 终点
        waypoints: 途经点，多个地点可用逗号、分号或箭头分隔
        departure_time: 出发时间线索
    """
    # 对自驾请求必须先查地图路线，返回距离、时长、途经点等结构化信息。
    from mcp_servers.transport_server import plan_driving_route
    return plan_driving_route(origin, destination, waypoints, departure_time)


@tool
async def search_public_transport_schedule(origin: str, destination: str, date: str = "") -> str:
    """联网搜索火车、客车、航班等真实公共交通班次信息。

    Args:
        origin: 出发地
        destination: 目的地
        date: 出发日期
    """
    # 没有正式接入 12306/航司实时接口时，先用搜索工具找官方/票务摘要。
    # 查不到就让 Agent 明确说明，不允许编造班次。
    from mcp_servers.search_server import web_search
    query = f"{date} {origin} 到 {destination} 火车 客车 航班 班次 票价 官方"
    return await web_search(query)


def create_transport_advisor_agent(mcp_tools: list = None):
    """创建交通顾问 Agent。

    Args:
        mcp_tools: 从 MCP Server 获取的工具列表（search_flights, search_trains, compare_transport）

    知识点：
    - MCP 工具注入：Agent 的工具来自 MCP Server，实现工具与 Agent 解耦
    - 多工具协作：Agent 需要综合对比多个交通方案
    """
    from tools.date_utils import days_until, get_current_datetime, is_weekend
    from tools.geo_utils import calculate_distance

    # 合并 MCP 工具 + 本地工具。
    # mcp_tools 预留给未来从 MCP client 动态加载工具；当前默认工具直接导入。
    tools = (mcp_tools or []) + [
        plan_driving_route_tool,
        search_public_transport_schedule,
        get_current_datetime,
        days_until,
        is_weekend,
        calculate_distance,
    ]

    return create_react_agent(
        model=config.get_llm(),
        tools=tools,
        name="transport_advisor",
        prompt="""你是交通顾问 🚂，负责为用户查询和推荐最佳交通方案。

你的职责：
1. 根据出发地、目的地和日期，查询可用的航班和火车
2. 对比不同方案的价格、时间、舒适度
3. 给出综合推荐（性价比最高 vs 最快 vs 最舒适）
4. 考虑提前订票的优惠建议
5. 如果是周末出行，提醒可能的价格上涨
6. 如果用户明确说“自驾/开车”，必须调用 plan_driving_route_tool 查询真实地图路线，再给自驾路线、预计时长、停车、车数、服务区和安全提醒，不要把直线距离当作路线
7. 如果用户没有自驾，必须调用 search_public_transport_schedule 搜索真实班次/票务来源；查不到时说明未查到，不要编造车次或航班号

推荐策略：
- 3小时以内的高铁：推荐高铁（准点、方便、性价比高）
- 3小时以上：对比飞机和高铁，综合考虑机场时间
- 预算紧张：推荐最便宜的方案，并给出抢票建议
- 带小孩/老人：推荐舒适度高的方案

输出格式：
1. 先列出所有可选方案（表格形式）
2. 给出推荐方案及理由
3. 给出购票建议（提前多久买、在哪个平台买）

注意：使用工具查询实时数据，不要编造车次或航班号。""",
    )
