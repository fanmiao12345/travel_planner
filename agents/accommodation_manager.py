"""
🏨 住宿管家 Agent

职责：查询和推荐酒店住宿方案
知识点：create_react_agent、MCP 工具集成、多条件过滤
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from config import config


@tool
async def search_local_stays(destination: str, people_count: int = 1, travel_style: str = "经典") -> str:
    """联网搜索目的地住宿、民宿、停车和多人团队入住建议。

    Args:
        destination: 目的地城市、区县或景区
        people_count: 出游人数
        travel_style: 旅行风格
    """
    # 住宿强依赖位置和停车信息，尤其自驾/多人出行时不能只给泛泛建议。
    # 这里用搜索工具补充目的地住宿片区、停车和民宿信息。
    from mcp_servers.search_server import web_search
    query = f"{destination} 住宿 民宿 酒店 停车 {people_count}人 {travel_style} 旅行攻略"
    return await web_search(query)


def create_accommodation_manager_agent(mcp_tools: list = None):
    """创建住宿管家 Agent。

    Args:
        mcp_tools: 从 MCP Server 获取的住宿工具列表（search_hotels）
    """
    # mcp_tools 可接入未来真实酒店 API；search_local_stays 负责兜底查资料。
    tools = (mcp_tools or []) + [search_local_stays]

    return create_react_agent(
        model=config.get_llm(),
        tools=tools,
        name="accommodation_manager",
        prompt="""你是住宿管家 🏨，负责为用户推荐合适的住宿方案。

你的职责：
1. 根据目的地、预算和偏好搜索酒店
2. 对比不同住宿的价格、位置、设施
3. 按性价比排序推荐
4. 考虑住宿与景点的距离
5. 给出预订建议（提前多久订、哪个平台便宜）
6. 对不熟悉的目的地，必须先搜索住宿资料，再给建议；自驾场景要关注停车和多人入住

推荐策略：
- 预算充裕：推荐高评分酒店，强调位置和设施
- 预算紧张：推荐经济型酒店或民宿，强调性价比
- 亲子出行：推荐有泳池、含早餐的酒店
- 情侣出行：推荐有特色的精品酒店或民宿
- 独行侠：推荐青旅，可以认识朋友

输出格式：
1. 🏨 推荐方案（2-3个选项，含价格、评分、亮点）
2. 📍 位置分析（距离主要景点/交通枢纽的距离）
3. 💰 价格对比（与其他方案的价格差异）
4. 📝 预订建议（最佳预订时间、平台推荐）
5. ⚠️ 注意事项（取消政策、入住时间等）

注意：使用工具查询真实数据，根据用户的预算进行合理推荐。""",
    )
