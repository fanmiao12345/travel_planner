"""
出游计划平台 — UI 组件

知识点：
  - Streamlit 组件化
  - Plotly 图表
  - 数据可视化
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from html import escape


def render_header():
    """渲染页面头部"""
    st.markdown("""
    <div class="tp-header">
        <div>
            <div class="tp-kicker">Travel Planner</div>
            <h1>出游计划工作台</h1>
            <p>把目的地、人数、日期和偏好交给智能体，方案会带上来源和质量检查。</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_agent_status(phase: str, completed: list[str]):
    """渲染智能体工作状态面板"""
    agents = [
        ("🗺️", "路线规划师", "route_planner"),
        ("🌤️", "天气预报员", "weather_forecaster"),
        ("🚂", "交通顾问", "transport_advisor"),
        ("🏨", "住宿管家", "accommodation_manager"),
        ("🍜", "美食达人", "food_advisor"),
        ("💰", "省钱精算师", "budget_optimizer"),
    ]

    completed_set = set(completed)
    active_key = None
    if phase not in {"idle", "reviewing", "done"}:
        active_key = next((key for _, _, key in agents if key not in completed_set), None)
    items = []
    for icon, name, key in agents:
        if key in completed_set:
            status = "done"
            label = "完成"
        elif phase == key or key == active_key:
            status = "active"
            label = "执行中"
        else:
            status = "pending"
            label = "待处理"
        items.append(
            f"""
            <div class="tp-agent tp-agent-{status}">
                <div class="tp-agent-icon">{escape(icon)}</div>
                <div class="tp-agent-main">
                    <div class="tp-agent-name">{escape(name)}</div>
                    <div class="tp-agent-status">{label}</div>
                </div>
            </div>
            """
        )

    st.markdown(
        '<div class="tp-section-title">协作进度</div>'
        f'<div class="tp-agent-grid">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def render_trip_overview(state: dict):
    """渲染结果页顶部概要，帮助用户先抓住结论。"""
    if not state:
        return
    dates = state.get("dates", {}) if isinstance(state.get("dates"), dict) else {}
    quality = state.get("quality_report", {}) if isinstance(state.get("quality_report"), dict) else {}
    source_count = len(state.get("evidence_sources", []) or [])
    values = [
        ("目的地", state.get("destination") or "未识别"),
        ("日期", f"{dates.get('start', '未定')} - {dates.get('end', '未定')}"),
        ("人数", f"{state.get('people_count', 1)} 人"),
        ("预算", f"¥{state.get('budget', 0):,.0f}" if isinstance(state.get("budget"), (int, float)) else str(state.get("budget", "未定"))),
        ("来源", f"{source_count} 条"),
        ("评分", f"{quality.get('score', 0)}/100" if quality else "待生成"),
    ]
    blocks = "".join(
        f"""
        <div class="tp-stat">
            <div class="tp-stat-label">{escape(label)}</div>
            <div class="tp-stat-value">{escape(value)}</div>
        </div>
        """
        for label, value in values
    )
    st.markdown(f'<div class="tp-overview">{blocks}</div>', unsafe_allow_html=True)


def render_budget_chart(budget_breakdown: dict):
    """渲染预算饼图"""
    if not budget_breakdown:
        return

    # budget_breakdown 可能包含 summary、react_trace 等非数字字段。
    # 饼图只接收数值项，避免 Plotly 因字符串字段报错。
    numeric_items = {
        key: value
        for key, value in budget_breakdown.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    if not numeric_items:
        summary = budget_breakdown.get("summary") if isinstance(budget_breakdown, dict) else None
        if summary:
            st.info(summary)
        return

    labels = list(numeric_items.keys())
    values = list(numeric_items.values())

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.3,
        textinfo="label+percent",
        marker_colors=px.colors.qualitative.Set2,
    )])
    fig.update_layout(
        title="💰 预算分配",
        height=400,
        showlegend=True,
    )
    st.plotly_chart(fig, width="stretch")


def render_weather_card(weather_info: dict):
    """渲染天气信息卡片"""
    if not weather_info:
        return

    st.markdown("### 🌤️ 天气预报")
    if isinstance(weather_info, dict):
        # 工具返回结构通常包含 current 和 forecast；
        # 如果工具失败，weather_info 可能只有 error，下面会显示 N/A。
        current = weather_info.get("current", {})
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("温度", f"{current.get('temp', 'N/A')}°C")
        with col2:
            st.metric("体感", f"{current.get('feels_like', 'N/A')}°C")
        with col3:
            st.metric("天气", current.get("condition", "N/A"))

        forecast = weather_info.get("forecast", [])
        if forecast:
            st.markdown("**未来几天：**")
            for day in forecast:
                st.write(f"📅 {day.get('date', '')}: {day.get('condition', '')} | "
                         f"🌡️ {day.get('temp_min', '')}°C ~ {day.get('temp_max', '')}°C | "
                         f"🌧️ 降水概率 {day.get('precipitation', 0)}%")
    else:
        st.write(str(weather_info))


def render_transport_table(transport_options: list):
    """渲染交通方案表格"""
    if not transport_options:
        return

    st.markdown("### 🚗 交通方案")
    for option in transport_options:
        # 不同 Agent 可能返回纯文本总结，也可能返回结构化 JSON。
        # UI 需要兼容两种形态，避免因为一个 Agent 输出格式变化导致页面崩溃。
        if isinstance(option, str):
            st.write(option)
        elif isinstance(option, dict):
            with st.expander(f"{option.get('route', '路线')} - 最低 ¥{option.get('cheapest', {}).get('price', 'N/A')}"):
                render_key_value_block(option)


def render_key_value_block(data: dict, level: int = 0):
    """用普通文本展示结构化数据，避免 st.json 自带复制按钮触发剪贴板弹窗。"""
    for key, value in data.items():
        label = str(key)
        if isinstance(value, dict):
            st.markdown(f"{'&nbsp;' * level * 4}**{escape(label)}**", unsafe_allow_html=True)
            render_key_value_block(value, level + 1)
        elif isinstance(value, list):
            st.markdown(f"{'&nbsp;' * level * 4}**{escape(label)}**", unsafe_allow_html=True)
            for item in value:
                if isinstance(item, dict):
                    render_key_value_block(item, level + 1)
                else:
                    st.markdown(f"{'&nbsp;' * (level + 1) * 4}- {escape(str(item))}", unsafe_allow_html=True)
        else:
            st.markdown(
                f"{'&nbsp;' * level * 4}<span style='color:#667085'>{escape(label)}：</span>{escape(str(value))}",
                unsafe_allow_html=True,
            )


def render_accommodation_list(accommodation_options: list):
    """渲染住宿方案列表"""
    if not accommodation_options:
        return

    st.markdown("### 🏨 住宿推荐")
    for opt in accommodation_options:
        if isinstance(opt, str):
            st.write(opt)
        elif isinstance(opt, dict):
            # MCP 酒店工具的标准字段是 hotels；只展示前三个，保持页面紧凑。
            hotels = opt.get("hotels", [])
            for hotel in hotels[:3]:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        stars = "⭐" * hotel.get("star", 0) if hotel.get("star", 0) > 0 else "🏠"
                        st.write(f"**{hotel.get('name', '')}** {stars}")
                        tags = " ".join(f"`{t}`" for t in hotel.get("tags", []))
                        st.caption(f"📍 {hotel.get('location', '')} {tags}")
                    with col2:
                        st.metric("价格", f"¥{hotel.get('price', 0)}/晚")
                    with col3:
                        st.metric("评分", f"{hotel.get('rating', 0)}")


def render_food_recommendations(food_recommendations: list):
    """渲染美食推荐"""
    if not food_recommendations:
        return

    st.markdown("### 🍜 美食推荐")
    for rec in food_recommendations:
        if isinstance(rec, str):
            st.write(rec)
        elif isinstance(rec, dict):
            restaurants = rec.get("restaurants", [])
            for r in restaurants[:5]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{r.get('name', '')}** - {r.get('cuisine', '')}")
                    st.caption(f"特色: {r.get('specialty', '')} | 📍 {r.get('location', '')}")
                with col2:
                    st.write(f"¥{r.get('avg_price', 0)}/人")
                    st.write(f"⭐ {r.get('rating', 0)}")


def render_plan_timeline(route_plan: dict):
    """渲染行程时间线"""
    if not route_plan:
        return

    st.markdown("### 行程安排")
    if isinstance(route_plan, dict) and "content" in route_plan:
        st.markdown(route_plan["content"])
    elif isinstance(route_plan, str):
        st.markdown(route_plan)


def render_saving_tips(suggestions: list):
    """渲染省钱建议"""
    if not suggestions:
        return

    st.markdown("### 💡 省钱贴士")
    for tip in suggestions:
        if isinstance(tip, str):
            st.markdown(f"- {tip}")


def render_final_plan(final_plan: dict):
    """渲染最终出游计划"""
    if not final_plan:
        return

    st.markdown("## 最终出游计划")

    # final_plan 由 summarize 节点生成，约定 content 是 Markdown 文本。
    content = final_plan.get("content", "")
    if content:
        st.markdown(content)
    else:
        st.info("计划生成中...")


def render_evidence_panel(evidence_sources: list, quality_report: dict):
    """渲染证据来源和质量检查面板。"""
    st.markdown("### 来源与质量检查")

    if quality_report:
        score = quality_report.get("score", 0)
        st.progress(min(max(score, 0), 100) / 100)
        st.caption(f"证据覆盖评分：{score}/100")
        warnings = quality_report.get("warnings", [])
        if warnings:
            for warning in warnings:
                st.warning(warning)
        else:
            st.success("关键查询链路已覆盖。")

        checks = quality_report.get("checks", {})
        if checks:
            with st.expander("检查项"):
                for key, value in checks.items():
                    st.write(f"{'✅' if value else '⚠️'} {key}: {value}")

    if not evidence_sources:
        st.info("暂无工具返回的可引用来源。")
        return

    st.markdown("### 已收集来源")
    for item in evidence_sources:
        source_id = item.get("id", "")
        title = item.get("title") or item.get("category") or "来源"
        source = item.get("source") or item.get("source_type") or "tool"
        tool = item.get("tool") or ""
        url = item.get("url")
        label = f"[{source_id}] {title}" if source_id else title
        with st.expander(label):
            st.caption(f"来源：{source} · 工具：{tool} · 类型：{item.get('category', '')}")
            if url:
                st.markdown(f"[打开来源]({url})")
            snippet = item.get("snippet")
            if snippet:
                st.write(snippet)
            dates = item.get("date_candidates")
            if dates:
                st.write("日期候选：", "、".join(dates))
