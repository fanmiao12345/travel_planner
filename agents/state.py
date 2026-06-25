"""
出游计划平台 — 状态定义

知识点：
  - TypedDict 定义状态结构
  - Annotated 类型注解 + reducer 函数
  - add_messages 消息累加器
  - 自定义 reducer（merge_dict、append_list）
  - 状态设计模式：最小化状态、职责分离
"""

from typing import Annotated, TypedDict
import operator
from langgraph.graph.message import add_messages


# ============================================
# 自定义 Reducer 函数
# ============================================

def merge_dict(existing: dict, new: dict) -> dict:
    """合并字典 reducer — 新值覆盖旧值的同名键"""
    if existing is None:
        return new or {}
    if new is None:
        return existing
    # 后写入的节点结果覆盖同名字段，适合 route_plan/weather_info 这类结构化对象。
    return {**existing, **new}


def append_unique(existing: list, new: list) -> list:
    """追加去重 reducer — 避免重复项"""
    if existing is None:
        return new or []
    if new is None:
        return existing

    def item_key(item):
        """给证据类 dict 一个稳定去重键，其它类型退回字符串键。"""
        if isinstance(item, dict):
            return (
                item.get("url") or "",
                item.get("title") or "",
                item.get("tool") or "",
                item.get("category") or "",
            )
        return str(item)

    # 证据来源会在汇总阶段补充 id 字段，不能用完整 dict 字符串去重。
    seen = set(item_key(item) for item in existing)
    result = list(existing)
    for item in new:
        key = item_key(item)
        if key not in seen:
            result.append(item)
            seen.add(key)
        elif isinstance(item, dict) and item.get("id"):
            # 汇总阶段会给证据补引用编号。遇到同一来源时合并回已有项，
            # 这样 UI 可以显示 [S1]，同时不会多出重复来源。
            for index, existing_item in enumerate(result):
                if item_key(existing_item) == key and isinstance(existing_item, dict):
                    result[index] = {**existing_item, **item}
                    break
    return result


# ============================================
# 旅游规划状态定义
# ============================================

class TravelState(TypedDict):
    """
    旅游规划系统的全局状态。

    知识点：每个字段的 Annotated 第二个参数是 reducer 函数，
    决定了多个节点写入同一字段时如何合并。
    - add_messages: 消息追加+去重（基于 message ID）
    - operator.add: 列表拼接
    - merge_dict: 字典合并
    - 无 reducer: 直接覆盖（last write wins）
    """

    # ---- 对话层 ----
    messages: Annotated[list, add_messages]
    """对话消息历史。add_messages 保证消息按 ID 去重和追加。"""

    # ---- 用户需求 ----
    user_request: str
    """用户的原始出游需求描述（无 reducer，直接覆盖）"""

    origin: str
    """出发城市"""

    destination: str
    """目的地城市"""

    dates: Annotated[dict, merge_dict]
    """日期信息 {"start": "2025-07-01", "end": "2025-07-03", "days": 3}"""

    budget: float
    """总预算（元）"""

    people_count: int
    """出游人数"""

    travel_style: str
    """旅行风格（经典/文艺/冒险/亲子/穷游）"""

    # ---- 各 Agent 输出 ----
    route_plan: Annotated[dict, merge_dict]
    """路线规划师的输出"""

    transport_options: Annotated[list, operator.add]
    """交通方案列表。operator.add 实现跨节点累加。"""

    weather_info: Annotated[dict, merge_dict]
    """天气预报信息"""

    accommodation_options: Annotated[list, operator.add]
    """住宿方案列表"""

    food_recommendations: Annotated[list, operator.add]
    """美食推荐列表"""

    budget_breakdown: Annotated[dict, merge_dict]
    """预算明细分解"""

    optimization_suggestions: Annotated[list, operator.add]
    """省钱优化建议"""

    # ---- 证据与可观测性 ----
    evidence_sources: Annotated[list, append_unique]
    """从工具返回结果中抽取出的证据来源，例如搜索链接、地图 API、天气 API。"""

    quality_report: Annotated[dict, merge_dict]
    """最终方案的轻量质量检查结果，帮助发现没有真实查询的薄弱环节。"""

    # ---- 流程控制 ----
    current_phase: str
    """当前执行阶段：planning / querying / optimizing / reviewing / done"""

    is_approved: bool
    """人机交互：用户是否审批通过"""

    iteration_count: int
    """反思迭代次数"""

    final_plan: Annotated[dict, merge_dict]
    """最终整合的出游计划"""


# ============================================
# 辅助函数
# ============================================

def create_initial_state(user_request: str) -> TravelState:
    """创建初始状态（所有字段给默认值）。

    知识点：状态初始化模式 — 保证所有 reducer 字段有合理的初始值。
    """
    # 所有 reducer 字段都给空 dict/list 初值，避免节点第一次合并时遇到 None。
    return TravelState(
        messages=[],
        user_request=user_request,
        origin="",
        destination="",
        dates={},
        budget=0.0,
        people_count=1,
        travel_style="经典",
        route_plan={},
        transport_options=[],
        weather_info={},
        accommodation_options=[],
        food_recommendations=[],
        budget_breakdown={},
        optimization_suggestions=[],
        evidence_sources=[],
        quality_report={},
        current_phase="planning",
        is_approved=False,
        iteration_count=0,
        final_plan={},
    )
