"""
🍜 美食达人 Agent

职责：推荐当地美食和餐饮方案
知识点：create_react_agent、场景化推荐
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from config import config


@tool
async def search_local_food(destination: str, people_count: int = 1) -> str:
    """联网搜索目的地当地美食、餐厅、适合多人用餐的建议。

    Args:
        destination: 目的地城市、区县或景区
        people_count: 出游人数
    """
    # 对区县/小众目的地，美食信息通常不在本地样例表里，
    # 因此必须先搜索当地特色、餐厅和多人用餐信息。
    from mcp_servers.search_server import web_search
    query = f"{destination} 当地美食 必吃 特色菜 餐厅 {people_count}人 团餐 旅行攻略"
    return await web_search(query)


def create_food_advisor_agent(mcp_tools: list = None):
    """创建美食达人 Agent。

    Args:
        mcp_tools: 从 MCP Server 获取的餐饮工具列表（search_restaurants, get_food_guide）
    """
    # 未来可以通过 mcp_tools 注入真实餐厅 API；当前默认有搜索能力。
    tools = (mcp_tools or []) + [search_local_food]

    return create_react_agent(
        model=config.get_llm(),
        tools=tools,
        name="food_advisor",
        prompt="""你是美食达人 🍜，负责为用户推荐当地美食和餐饮方案。

你的职责：
1. 查询目的地的特色美食和推荐餐厅
2. 根据用户的预算推荐合适的餐饮
3. 规划每日餐饮安排（早餐/午餐/晚餐）
4. 推荐当地小吃街和特色美食
5. 给出就餐时间建议（避开高峰期）
6. 对不熟悉的目的地，必须先搜索当地美食资料，再给建议

推荐策略：
- 预算充裕：推荐当地知名餐厅和特色菜品
- 预算紧张：推荐小吃街、苍蝇馆子、当地人常去的店
- 第一次去：推荐必吃榜单和经典菜品
- 美食爱好者：推荐隐藏美食和小众餐厅

输出格式：
1. 🍽️ 必吃美食清单（当地特色Top 5）
2. 🏪 推荐餐厅（2-3家，含价格、评分、特色菜）
3. 🗓️ 每日餐饮安排（早/午/晚推荐）
4. 🛒 美食街/小吃街推荐
5. 💡 就餐小贴士（避坑指南、最佳就餐时间）

注意：
- 使用工具查询真实餐厅数据
- 推荐要具体（菜名+价格），不要泛泛而谈
- 考虑用户行程，推荐景点附近的餐厅""",
    )
