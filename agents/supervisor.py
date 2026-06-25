"""
🎯 主控智能体 (Supervisor Agent)

职责：理解用户意图 → 路由分发 → 汇总结果 → 反思优化
知识点：
  - Supervisor 多智能体编排模式
  - 路由分发逻辑
  - 反思机制（生成→评估→迭代）
  - 条件边路由
"""

from typing import Literal
from langchain_core.messages import SystemMessage
from langgraph.types import Command

from config import config
from agents.state import TravelState
from tools.date_utils import today_date
from tools.evidence import (
    attach_evidence_ids,
    build_quality_report,
    format_evidence_for_prompt,
    format_quality_markdown,
    format_sources_markdown,
)


# ============================================
# Supervisor 路由节点
# ============================================

async def supervisor_node(state: TravelState) -> Command[Literal[
    "route_planner", "transport_advisor", "weather_forecaster",
    "accommodation_manager", "food_advisor", "budget_optimizer",
    "summarize", "human_review"
]]:
    """
    Supervisor 节点 — 分析当前状态，决定下一步路由。

    知识点：
    - Command[Literal[...]]: 定义路由目标的类型约束
    - Command(goto=..., update=...): 路由到下一个节点并更新状态
    - 条件路由：根据状态动态选择下一个执行节点
    """
    # current_phase / iteration_count 保留给 UI 展示和反思迭代扩展使用。
    # 当前路由主要根据"哪些专家结果还没有生成"来决定下一步。
    phase = state.get("current_phase", "planning")
    iteration = state.get("iteration_count", 0)

    def has_content(value) -> bool:
        """判断节点结果是否真的有内容，避免空壳 dict 被当成已完成。"""
        if isinstance(value, dict):
            return any(bool(v) for k, v in value.items() if k != "react_trace")
        return bool(value)

    # 构建上下文摘要
    has_route = has_content(state.get("route_plan"))
    has_transport = has_content(state.get("transport_options"))
    has_weather = has_content(state.get("weather_info"))
    has_hotel = has_content(state.get("accommodation_options"))
    has_food = has_content(state.get("food_recommendations"))
    has_budget = has_content(state.get("budget_breakdown"))

    # 路由顺序是保守的串行流程：
    # 先规划路线，再补天气/交通/住宿/美食/预算，最后汇总。
    # 这样比让 LLM 每次决定路由更稳定，也避免重复执行同一智能体。
    if state.get("final_plan") and not state.get("is_approved"):
        goto = "human_review"
    elif not has_route:
        goto = "route_planner"
    elif not has_weather:
        goto = "weather_forecaster"
    elif not has_transport:
        goto = "transport_advisor"
    elif not has_hotel:
        goto = "accommodation_manager"
    elif not has_food:
        goto = "food_advisor"
    elif not has_budget:
        goto = "budget_optimizer"
    else:
        goto = "summarize"

    return Command(
        goto=goto,
        update={
            "current_phase": "querying" if goto not in ["summarize", "human_review"] else "reviewing",
            "messages": [SystemMessage(content=f"[Supervisor] 路由到: {goto}")],
        },
    )


# ============================================
# 汇总节点
# ============================================

async def summarize_node(state: TravelState) -> dict:
    """
    汇总节点 — 将所有 Agent 的结果整合为最终出游计划。

    知识点：
    - 读取状态中各 Agent 的输出
    - 使用 LLM 生成结构化的最终方案
    """
    # 汇总节点只做整合，不再查新资料。
    # 前面的专业 Agent 已经把 route_plan、weather_info 和 evidence_sources 写入状态。
    llm = config.get_llm()
    evidence_sources = attach_evidence_ids(state.get("evidence_sources", []))
    quality_report = build_quality_report({**state, "evidence_sources": evidence_sources})
    evidence_block = format_evidence_for_prompt(evidence_sources)

    summary_prompt = f"""你是旅游规划汇总师，需要将各个专家的分析整合为一份完整的出游计划。

用户需求: {state.get('user_request', '')}
出发地: {state.get('origin', '')}
目的地: {state.get('destination', '')}
天数: {state.get('dates', {}).get('days', '未指定')}天
预算: ¥{state.get('budget', 0)}
人数: {state.get('people_count', 1)}人

--- 路线规划 ---
{state.get('route_plan', '暂无')}

--- 天气信息 ---
{state.get('weather_info', '暂无')}

--- 交通方案 ---
{state.get('transport_options', '暂无')}

--- 住宿方案 ---
{state.get('accommodation_options', '暂无')}

--- 美食推荐 ---
{state.get('food_recommendations', '暂无')}

--- 预算分析 ---
{state.get('budget_breakdown', '暂无')}

--- 省钱建议 ---
{state.get('optimization_suggestions', '暂无')}

--- 可引用来源 ---
{evidence_block}

请生成一份完整、美观的出游计划，包含：
1. 📋 行程总览
2. 📅 详细日程（Day 1, Day 2, ...）
3. 🚗 交通安排
4. 🏨 住宿推荐
5. 🍽️ 美食指南
6. 💰 预算明细
7. 💡 省钱贴士
8. ⚠️ 注意事项

硬性要求：
- 数据来源只能使用上面“可引用来源”中真实存在的 [S1] 编号和 URL，禁止自行编造官网、链接、票务平台或来源名称。
- 活动时间、开放时间、门票/预约规则、景区公告、赛事/展会/演唱会档期等强事实，必须优先引用官网、文旅部门、景区公告、主办方或权威票务来源。
- 如果只有普通攻略/社媒/搜索摘要，没有官网或官方公告支持，必须写“需以官网/官方公告二次确认”，不能写成确定事实。
- 景点、活动时间、网红地、餐厅、住宿片区、天气和自驾路线等事实性内容，能引用来源时必须使用 [S1] 这种来源编号。
- 没有来源支持的内容不能写成确定事实，必须标注"需二次确认"。
- 如果用户提到活动/节庆/赛事/展会/演唱会，而证据里没有活动档期来源，必须明确写"活动时间未确认"，不能从当前日期顺推。
- 如果用户说自驾，而证据里没有地图路线 API 结果，必须提示路线未核实。
- 不要输出"著名景点1/2/3"或泛化模板。
"""

    # 使用 astream 实现 token 级流式输出（120 秒超时）
    import asyncio as _asyncio
    full_content = ""
    try:
        async def _stream_summary():
            nonlocal full_content
            async for chunk in llm.astream([SystemMessage(content=summary_prompt)]):
                if chunk.content:
                    full_content += chunk.content
        await _asyncio.wait_for(_stream_summary(), timeout=120)
    except _asyncio.TimeoutError:
        pass
    except Exception:
        pass
    # 兜底：如果流式输出为空，用 ainvoke 获取完整结果
    if not full_content.strip():
        try:
            response = await _asyncio.wait_for(
                llm.ainvoke([SystemMessage(content=summary_prompt)]), timeout=120
            )
            full_content = response.content
        except _asyncio.TimeoutError:
            full_content = "⏰ 汇总超时，各专家的分析结果已保存，请查看上方详细信息。"
    final_content = (
        full_content
        + format_sources_markdown(evidence_sources)
        + format_quality_markdown(quality_report)
    )

    return {
        "final_plan": {"content": final_content},
        "evidence_sources": evidence_sources,
        "quality_report": quality_report,
        "current_phase": "reviewing",
        "messages": [SystemMessage(content="[汇总] 出游计划已生成，等待用户确认")],
    }


# ============================================
# 解析需求节点
# ============================================

async def parse_request_node(state: TravelState) -> dict:
    """
    解析用户需求节点 — 从自然语言中提取结构化信息。

    知识点：
    - LLM 结构化信息提取
    - 状态初始化
    """
    import json
    import re
    from datetime import timedelta

    def parse_locally(text: str) -> dict:
        """LLM 解析失败时的本地兜底解析。

        注意：这不是"模拟规划"，只负责抽取出发地、目的地、人数、预算等
        基础字段，避免模型接口短暂失败时整个工作流完全不可用。
        """
        cities = [
            "北京", "上海", "广州", "深圳", "成都", "杭州", "武汉", "西安", "重庆", "南京",
            "三亚", "大理", "丽江", "厦门", "昆明", "桂林", "拉萨", "青岛", "长沙",
            "天津", "苏州", "无锡", "常州", "宁波", "温州", "福州", "泉州", "漳州",
            "合肥", "南昌", "济南", "烟台", "威海", "淄博", "郑州", "洛阳", "开封",
            "太原", "大同", "呼和浩特", "包头", "沈阳", "大连", "长春", "哈尔滨",
            "贵阳", "遵义", "南宁", "北海", "海口", "珠海", "佛山", "东莞",
            "兰州", "敦煌", "西宁", "银川", "乌鲁木齐", "喀什", "阿勒泰",
            "张家界", "凤凰", "婺源", "黄山", "景德镇", "平遥", "延吉", "秦皇岛",
            "张家口", "蔚县", "暖泉", "宣化", "崇礼",
        ]
        info = {
            "origin": "",
            "destination": "",
            "days": 3,
            "budget": 5000,
            "people_count": 1,
            "travel_style": "经典",
            "start_date": "",
            "end_date": "",
        }

        route_match = re.search(
            r"(?P<date>今天|明天|后天)?从(?P<origin>[\u4e00-\u9fa5A-Za-z]{2,12})(?:出发)?(?:去|到|前往)(?P<dest>[\u4e00-\u9fa5A-Za-z]{2,20})",
            text,
        )
        if route_match:
            # 处理"从北京到张家口的蔚县"这类表达：
            # origin=北京，destination=张家口的蔚县，后面再清洗成"蔚县"。
            info["origin"] = route_match.group("origin")
            info["destination"] = route_match.group("dest")

        mentioned = sorted(
            [city for city in cities if city in text],
            key=lambda city: text.index(city),
        )
        if mentioned and not info["destination"]:
            # 没有明确"从 A 到 B"时，用文本中出现的城市顺序做弱推断。
            # 最后出现的地点通常是目的地，最先出现的地点通常是出发地。
            info["destination"] = mentioned[-1]
            if len(mentioned) >= 2:
                info["origin"] = mentioned[0]

        if not info["destination"]:
            dest_match = re.search(
                r"(?:去|到|前往|想玩|想去)(?P<dest>[\u4e00-\u9fa5A-Za-z]{2,12})(?:玩|旅游|旅行|自由行|自驾|打卡|住|[0-9])",
                text,
            )
            if dest_match:
                info["destination"] = dest_match.group("dest")

        for key in ["origin", "destination"]:
            # 清理"张家口的蔚县""蔚县，11个人"这类尾巴，
            # 保证下游搜索和地图工具拿到更干净的地点名。
            value = info[key]
            if "的" in value:
                value = value.split("的")[-1]
            value = re.split(r"(?:，|。|,|\.|、|\s|应该|可以|要|玩|吃|住|自驾|开车|路线|景点)", value)[0]
            info[key] = re.sub(r"(玩|旅游|旅行|自由行|自驾|打卡|最近|很火|网红|地方)$", "", value).strip()

        days_match = re.search(r"(\d+)\s*天(?:\d+\s*晚)?|(\d+)\s*日游", text)
        if days_match:
            info["days"] = int(next(g for g in days_match.groups() if g))

        budget_match = re.search(r"预算\s*(\d+(?:\.\d+)?)\s*(万|千|元)?", text)
        if budget_match:
            amount = float(budget_match.group(1))
            unit = budget_match.group(2) or "元"
            if unit == "万":
                amount *= 10000
            elif unit == "千":
                amount *= 1000
            info["budget"] = amount

        people_match = re.search(r"(\d+)\s*(?:人|个人|大人)", text)
        if people_match:
            info["people_count"] = int(people_match.group(1))

        for style in ["文艺", "冒险", "亲子", "穷游", "经典"]:
            if style in text:
                info["travel_style"] = style
                break

        date_match = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", text)
        base = today_date()
        if date_match:
            info["start_date"] = date_match.group(1)
        elif "明天" in text:
            info["start_date"] = (base + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "后天" in text:
            info["start_date"] = (base + timedelta(days=2)).strftime("%Y-%m-%d")
        elif "今天" in text:
            info["start_date"] = base.strftime("%Y-%m-%d")
        else:
            info["start_date"] = base.strftime("%Y-%m-%d")

        start = today_date()
        try:
            # end_date 按"行程天数"推算。这里推算的是旅行日期范围，
            # 不是活动举办时间；活动时间必须由 search_event_schedule 查询。
            from datetime import datetime
            start = datetime.strptime(info["start_date"], "%Y-%m-%d")
        except ValueError:
            info["start_date"] = base.strftime("%Y-%m-%d")
        info["end_date"] = (start + timedelta(days=max(info["days"] - 1, 0))).strftime("%Y-%m-%d")
        return info

    llm = config.get_llm()

    parse_prompt = f"""从以下用户描述中提取出游信息，以JSON格式返回：

用户描述：{state['user_request']}

需要提取的字段：
- origin: 出发城市
- destination: 目的地城市
- start_date: 出发日期（YYYY-MM-DD，如果未提及则为空字符串）
- end_date: 返回日期（YYYY-MM-DD，如果未提及则为空字符串）
- days: 出游天数（如果未提及则根据日期推算，都没有则默认3）
- budget: 总预算（元，如果未提及则默认5000）
- people_count: 出游人数（如果未提及则默认1）
- travel_style: 旅行风格（经典/文艺/冒险/亲子/穷游，默认经典）

只返回JSON，不要其他文字。"""

    from langchain_core.messages import HumanMessage

    try:
        # 首选模型解析，因为自然语言表达很多样：
        # "五一后两天""一家三口""预算一万五"等都更适合交给模型。
        # 使用 astream 实现 token 级流式输出，让用户实时看到解析过程。
        # 设置 15 秒超时，避免 LLM 响应慢导致整个流程卡住。
        import asyncio as _asyncio
        full_content = ""
        try:
            async def _stream_parse():
                nonlocal full_content
                async for chunk in llm.astream([HumanMessage(content=parse_prompt)]):
                    if chunk.content:
                        full_content += chunk.content
            await _asyncio.wait_for(_stream_parse(), timeout=15)
        except _asyncio.TimeoutError:
            full_content = ""  # 超时则回退到本地解析
        except Exception:
            pass
        # 兜底：如果流式输出为空，用 ainvoke 获取完整结果
        if not full_content.strip():
            try:
                response = await _asyncio.wait_for(
                    llm.ainvoke([HumanMessage(content=parse_prompt)]), timeout=15
                )
                full_content = response.content
            except _asyncio.TimeoutError:
                full_content = ""
        info = json.loads(full_content.strip().replace("```json", "").replace("```", ""))
    except Exception:
        # 模型不可用、超时或返回非 JSON 时，退回本地正则解析。
        info = parse_locally(state["user_request"])

    if not info.get("start_date"):
        # LLM 没给日期时，用本地规则补今天/明天/后天等基础日期。
        local_info = parse_locally(state["user_request"])
        info["start_date"] = local_info["start_date"]
        info["end_date"] = local_info["end_date"]
    if not info.get("end_date"):
        local_info = parse_locally(state["user_request"])
        info["end_date"] = local_info["end_date"]

    return {
        "origin": info.get("origin", ""),
        "destination": info.get("destination", ""),
        "dates": {
            "start": info.get("start_date", ""),
            "end": info.get("end_date", ""),
            "days": info.get("days", 3),
        },
        "budget": info.get("budget", 5000),
        "people_count": info.get("people_count", 1),
        "travel_style": info.get("travel_style", "经典"),
        "current_phase": "planning",
        "messages": [SystemMessage(content=f"[解析] 目的地:{info.get('destination')} | 天数:{info.get('days')} | 预算:¥{info.get('budget')} | 人数:{info.get('people_count')}")],
    }


# ============================================
# 人机交互审核节点
# ============================================

async def human_review_node(state: TravelState) -> dict:
    """
    人机交互审核节点 — 暂停执行，等待用户确认。

    知识点：
    - interrupt(): 暂停图执行，返回值给调用者
    - Command(resume=...): 调用者通过 Command 恢复执行
    - Human-in-the-loop 模式
    """
    from langgraph.types import interrupt

    # interrupt 会暂停图执行，将消息发送给用户
    user_response = interrupt({
        "type": "plan_review",
        "message": "📋 出游计划已生成，请审阅：",
        "plan": state.get("final_plan", {}).get("content", "暂无"),
        "question": "您对这个出游计划满意吗？可以回复：\n1. '确认' - 接受方案\n2. '修改：xxx' - 提出修改意见\n3. '重新规划' - 重新开始",
    })

    # user_response 是用户通过 Command(resume=...) 传入的值
    if isinstance(user_response, str):
        if "确认" in user_response or "满意" in user_response or "ok" in user_response.lower():
            return {
                "is_approved": True,
                "current_phase": "done",
                "messages": [SystemMessage(content="[审核] ✅ 用户确认通过")],
            }
        elif "重新" in user_response:
            return {
                "route_plan": {"__clear__": True},
                "transport_options": ["__CLEAR__"],
                "weather_info": {"__clear__": True},
                "accommodation_options": ["__CLEAR__"],
                "food_recommendations": ["__CLEAR__"],
                "budget_breakdown": {"__clear__": True},
                "optimization_suggestions": ["__CLEAR__"],
                "evidence_sources": ["__CLEAR__"],
                "quality_report": {"__clear__": True},
                "final_plan": {"__clear__": True},
                "is_approved": False,
                "current_phase": "planning",
                "iteration_count": state.get("iteration_count", 0) + 1,
                "messages": [SystemMessage(content="[审核] 🔄 用户要求重新规划")],
            }
        else:
            # 反思优化
            return {
                "route_plan": {"__clear__": True},
                "transport_options": ["__CLEAR__"],
                "weather_info": {"__clear__": True},
                "accommodation_options": ["__CLEAR__"],
                "food_recommendations": ["__CLEAR__"],
                "budget_breakdown": {"__clear__": True},
                "optimization_suggestions": ["__CLEAR__"],
                "evidence_sources": ["__CLEAR__"],
                "quality_report": {"__clear__": True},
                "final_plan": {"__clear__": True},
                "is_approved": False,
                "current_phase": "planning",
                "iteration_count": state.get("iteration_count", 0) + 1,
                "user_request": state["user_request"] + f"\n\n用户修改意见：{user_response}",
                "messages": [SystemMessage(content=f"[审核] 📝 用户反馈: {user_response}")],
            }

    return {
        "is_approved": False,
        "current_phase": "done",
        "messages": [SystemMessage(content="[审核] 计划完成")],
    }
