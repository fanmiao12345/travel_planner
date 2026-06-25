"""
出游计划平台 — 主图构建器

知识点：
  - StateGraph 状态图构建
  - 节点（node）定义与注册
  - 边（edge）和条件边（conditional_edge）
  - START / END 入口和出口
  - 并行节点执行
  - 图编译与配置
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_core.messages import SystemMessage

from agents.state import TravelState
from agents.supervisor import (
    supervisor_node, summarize_node, parse_request_node, human_review_node
)
from agents.route_planner import create_route_planner_agent
from agents.transport_advisor import create_transport_advisor_agent
from agents.weather_forecaster import create_weather_forecaster_agent
from agents.accommodation_manager import create_accommodation_manager_agent
from agents.food_advisor import create_food_advisor_agent
from agents.budget_optimizer import create_budget_optimizer_agent
from tools.evidence import collect_evidence_from_messages


# ============================================
# 辅助节点函数（将 Agent 包装为图节点）
# ============================================

def _preview_text(value, limit: int = 180) -> str:
    """Return a compact single-line preview for logs."""
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _format_react_trace(messages: list) -> str:
    """Extract an auditable Action/Observation trace from ReAct messages.

    This exposes tool decisions and results without asking the model to reveal
    hidden chain-of-thought.
    """
    lines = []
    for msg in messages:
        # LangGraph ReAct agent 的 AIMessage 里会携带 tool_calls。
        # 我们只记录工具名和参数摘要，不展示模型隐藏推理。
        tool_calls = getattr(msg, "tool_calls", None) or []
        for call in tool_calls:
            name = call.get("name", "unknown_tool")
            args = call.get("args", {})
            lines.append(f"Action: 调用工具 `{name}`，参数 {_preview_text(args, 120)}")

        msg_type = getattr(msg, "type", "")
        class_name = msg.__class__.__name__
        if msg_type == "tool" or class_name == "ToolMessage":
            # ToolMessage 是工具执行后的 Observation。
            # 截断到较短长度，避免日志被大段 JSON 淹没。
            name = getattr(msg, "name", "tool")
            content = getattr(msg, "content", "")
            lines.append(f"Observation: `{name}` 返回 {_preview_text(content, 160)}")

    if not lines:
        return "Action: 未触发工具调用，直接基于已解析需求和上下文生成。"
    return "\n".join(lines[-10:])

def _make_agent_node(agent, output_key: str, phase_msg: str):
    """
    将 ReAct Agent 包装为 StateGraph 节点。

    知识点：
    - Agent 适配器模式：将 Agent 的输入输出适配到 StateGraph 的状态格式
    - 闭包：捕获 agent 和 output_key
    - 类型适配：根据状态字段的类型（dict/list/str）包装输出
    """
    # 判断输出字段在状态中的类型
    _list_keys = {"transport_options", "accommodation_options", "food_recommendations", "optimization_suggestions"}
    _dict_keys = {"route_plan", "weather_info", "budget_breakdown", "final_plan", "dates"}

    async def agent_node(state: TravelState) -> dict:
        import asyncio as _asyncio

        # 从状态中提取相关上下文
        # 这里的 context 是每个专业 Agent 都能看到的"任务 brief"。
        # 专业 Agent 自己再根据 prompt 决定要调用哪些工具。
        context = f"""当前任务信息：
出发地: {state.get('origin', '未指定')}
目的地: {state.get('destination', '未指定')}
出发日期: {state.get('dates', {}).get('start', '未指定')}
返回日期: {state.get('dates', {}).get('end', '未指定')}
天数: {state.get('dates', {}).get('days', '未指定')}
预算: ¥{state.get('budget', '未指定')}
人数: {state.get('people_count', 1)}
风格: {state.get('travel_style', '经典')}
请只使用上述日期或工具返回的日期，不要自行编造当前时间。
内部执行方式: ReAct/tool-calling。先判断需要哪些工具，再读取工具结果，最后生成面向用户的答案；不要输出隐藏推理链，只输出可验证的依据和结论。
"""

        # 调用 Agent（120 秒超时，避免单个 Agent 卡住整个流程）
        try:
            result = await _asyncio.wait_for(agent.ainvoke({
                "messages": [("system", context), ("user", state.get("user_request", "请帮我规划出游"))]
            }), timeout=120)
        except _asyncio.TimeoutError:
            output = f"⏰ {phase_msg}超时（120秒），已跳过。请稍后重试或简化需求。"
            if output_key in _dict_keys:
                return {output_key: {"content": output, "react_trace": "Timeout"}, "messages": [SystemMessage(content=output)]}
            elif output_key in _list_keys:
                return {output_key: [output], "messages": [SystemMessage(content=output)]}
            else:
                return {output_key: output, "messages": [SystemMessage(content=output)]}
        react_trace = _format_react_trace(result.get("messages", []))
        evidence_sources = collect_evidence_from_messages(result.get("messages", []), agent_name=output_key)

        # 提取 Agent 的最终回复
        last_message = result["messages"][-1]
        output = last_message.content if hasattr(last_message, "content") else str(last_message)

        # 根据字段类型包装输出，避免 reducer 报错
        # TravelState 里有些字段是 dict reducer，有些是 list reducer。
        # 这里必须保持字段形状一致，否则 LangGraph 合并状态时会出错。
        if output_key in _dict_keys:
            wrapped = {"content": output, "react_trace": react_trace}
        elif output_key in _list_keys:
            wrapped = [output]
        else:
            wrapped = output

        return {
            output_key: wrapped,
            "evidence_sources": evidence_sources,
            # messages 字段用于聊天区/执行日志展示；真正业务数据写入 output_key。
            "messages": [SystemMessage(content=f"[{phase_msg} · ReAct]\n{react_trace}\n\nFinal: {_preview_text(output, 240)}")],
        }

    return agent_node


def _parallel_query_node(state: TravelState) -> dict:
    """
    并行查询节点 — 同时获取天气、交通、住宿、餐饮信息。

    知识点：
    - 并行执行：在一个节点内并发调用多个 Agent
    - asyncio.gather: 并发执行多个异步任务
    - 错误隔离：一个 Agent 失败不影响其他 Agent
    """
    import asyncio

    # 这个节点会被条件边跳过，实际并行由子图实现
    return {"current_phase": "querying"}


# ============================================
# Agent 节点工厂
# ============================================

def _create_agent_nodes():
    """创建所有 Agent 节点（延迟初始化，避免循环导入）"""
    # Agent 创建会读取当前模型配置，因此用函数延迟构造。
    # 当 UI 改了模型配置后 reset_graph() 会删除旧实例，下一次请求重新创建。
    route_agent = create_route_planner_agent()
    transport_agent = create_transport_advisor_agent()
    weather_agent = create_weather_forecaster_agent()
    accommodation_agent = create_accommodation_manager_agent()
    food_agent = create_food_advisor_agent()
    budget_agent = create_budget_optimizer_agent()

    return {
        "route_planner": _make_agent_node(route_agent, "route_plan", "路线规划"),
        "transport_advisor": _make_agent_node(transport_agent, "transport_options", "交通查询"),
        "weather_forecaster": _make_agent_node(weather_agent, "weather_info", "天气查询"),
        "accommodation_manager": _make_agent_node(accommodation_agent, "accommodation_options", "住宿查询"),
        "food_advisor": _make_agent_node(food_agent, "food_recommendations", "美食推荐"),
        "budget_optimizer": _make_agent_node(budget_agent, "budget_breakdown", "预算分析"),
    }


# ============================================
# 主图构建
# ============================================

def build_travel_graph(with_checkpointer: bool = True, with_store: bool = True):
    """
    构建出游规划的主工作流图。

    知识点：
    - StateGraph(TypedDict): 用 TypedDict 定义状态结构
    - add_node(): 注册节点
    - add_edge(): 添加普通边
    - add_conditional_edges(): 添加条件边
    - graph.compile(): 编译图，附加 checkpointer/store
    - START / END: 入口和出口伪节点

    图结构：
    START → parse_request → supervisor → [路由] → agent → supervisor
                                                → summarize → human_review → END
    """
    # 创建 Agent 节点
    agent_nodes = _create_agent_nodes()

    # 构建状态图
    graph = StateGraph(TravelState)

    # ---- 注册节点 ----
    graph.add_node("parse_request", parse_request_node)          # 需求解析
    graph.add_node("supervisor", supervisor_node)                 # 主控路由
    graph.add_node("summarize", summarize_node)                   # 汇总
    graph.add_node("human_review", human_review_node)             # 人机审核

    # 注册 6 个专业 Agent 节点
    for name, node_fn in agent_nodes.items():
        graph.add_node(name, node_fn)

    # ---- 定义边 ----

    # 入口：START → 解析需求
    graph.add_edge(START, "parse_request")

    # 解析完成 → Supervisor
    graph.add_edge("parse_request", "supervisor")

    # Supervisor 的路由由 Command(goto=...) 在 supervisor_node 内部决定
    # 所以 supervisor 节点不需要 add_conditional_edges —— Command 已经指定了 goto

    # 每个 Agent 执行完 → 回到 Supervisor
    for agent_name in agent_nodes:
        graph.add_edge(agent_name, "supervisor")

    # 汇总 → 人机审核
    graph.add_edge("summarize", "human_review")

    # 人机审核后的路由
    def after_review(state: TravelState) -> Literal["supervisor", "__end__"]:
        """审核后的条件路由"""
        if state.get("is_approved"):
            return END
        if state.get("iteration_count", 0) >= 3:
            return END  # 最多迭代3次
        return "supervisor"

    graph.add_conditional_edges("human_review", after_review)

    # ---- 编译图 ----
    compile_kwargs = {}

    if with_checkpointer:
        # 知识点：Checkpointer 提供线程级状态持久化
        compile_kwargs["checkpointer"] = MemorySaver()

    if with_store:
        # 知识点：Store 提供跨线程的长期记忆
        compile_kwargs["store"] = InMemoryStore()

    return graph.compile(**compile_kwargs)


# ============================================
# 便捷函数
# ============================================

def get_graph():
    """获取编译后的图实例（单例模式）"""
    if not hasattr(get_graph, "_instance"):
        get_graph._instance = build_travel_graph()
    return get_graph._instance


def reset_graph():
    """重置图实例（用于测试）"""
    if hasattr(get_graph, "_instance"):
        delattr(get_graph, "_instance")
