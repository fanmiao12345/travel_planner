"""
出游计划平台 — 子图定义

知识点：
  - 子图嵌套：将复杂工作流拆分为可复用的子图
  - 并行执行子图
  - 子图与主图的状态共享
"""

import asyncio
from typing import Any
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage

from agents.state import TravelState


def create_parallel_query_subgraph():
    """
    创建并行查询子图 — 同时执行天气、交通、住宿、餐饮查询。

    知识点：
    - 子图作为节点：子图可以作为主图的一个节点
    - 并行执行：使用 asyncio.gather 并发执行多个 Agent
    - 错误隔离：一个查询失败不影响其他查询
    """

    async def parallel_query(state: TravelState) -> dict:
        """并行查询所有信息"""
        from agents.weather_forecaster import create_weather_forecaster_agent
        from agents.transport_advisor import create_transport_advisor_agent
        from agents.accommodation_manager import create_accommodation_manager_agent
        from agents.food_advisor import create_food_advisor_agent

        # 子图演示“并发查询”模式：多个专业 Agent 拿同一份上下文同时执行。
        # 当前主图走更可控的串行 Supervisor 路由；这个子图保留给后续性能优化。
        context = f"""目的地: {state.get('destination', '未指定')}
出发地: {state.get('origin', '未指定')}
天数: {state.get('dates', {}).get('days', 3)}
预算: ¥{state.get('budget', 5000)}
人数: {state.get('people_count', 1)}
"""
        user_msg = state.get("user_request", "请帮我查询信息")

        # 创建 Agent
        weather_agent = create_weather_forecaster_agent()
        transport_agent = create_transport_advisor_agent()
        accommodation_agent = create_accommodation_manager_agent()
        food_agent = create_food_advisor_agent()

        # 并行执行。return_exceptions 没有直接使用，是因为 run_agent 内部已经捕获异常，
        # 这样一个查询失败不会影响其他查询结果返回。
        async def run_agent(agent, name):
            try:
                result = await agent.ainvoke({
                    "messages": [("system", context), ("user", user_msg)]
                })
                return name, result["messages"][-1].content
            except Exception as e:
                return name, f"查询失败: {str(e)}"

        results = await asyncio.gather(
            run_agent(weather_agent, "weather"),
            run_agent(transport_agent, "transport"),
            run_agent(accommodation_agent, "accommodation"),
            run_agent(food_agent, "food"),
        )

        # 汇总结果时要保持 TravelState 字段形状一致：
        # weather_info 是 dict，其余几个推荐项是 list。
        updates = {}
        for name, content in results:
            if name == "weather":
                updates["weather_info"] = {"content": content}
            elif name == "transport":
                updates["transport_options"] = [content]
            elif name == "accommodation":
                updates["accommodation_options"] = [content]
            elif name == "food":
                updates["food_recommendations"] = [content]

        updates["messages"] = [SystemMessage(content="[并行查询] 天气/交通/住宿/餐饮信息已获取")]
        return updates

    # 构建子图
    subgraph = StateGraph(TravelState)
    subgraph.add_node("parallel_query", parallel_query)
    subgraph.add_edge(START, "parallel_query")
    subgraph.add_edge("parallel_query", END)

    return subgraph.compile()
