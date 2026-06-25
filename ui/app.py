"""
出游计划自动规划平台 — Streamlit 主应用

知识点：
  - Streamlit 异步集成
  - 会话状态管理
  - 流式输出展示
  - 人机交互流程
"""

import sys
import os
import asyncio
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo
import streamlit as st

if sys.platform.startswith("win"):
    # Windows 默认 ProactorEventLoop 容易和某些异步 HTTP/Streamlit 场景冲突，
    # SelectorEventLoop 在本项目里更稳定。
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 添加项目根目录到 path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

# 必须在导入 config 之前加载 .env
from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, ".env"), override=True)

from ui.components import (
    render_header, render_agent_status, render_budget_chart,
    render_weather_card, render_transport_table, render_accommodation_list,
    render_food_recommendations, render_plan_timeline, render_saving_tips,
    render_final_plan, render_evidence_panel, render_trip_overview,
)


# ============================================
# 页面配置
# ============================================
st.set_page_config(
    page_title="出游计划自动规划平台",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义样式
st.markdown("""
<style>
    .stApp {
        max-width: 1180px;
        margin: 0 auto;
        background: #f7f8fb;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }
    .tp-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding: 1.2rem 0 0.8rem 0;
        border-bottom: 1px solid #e6e8ef;
        margin-bottom: 1rem;
    }
    .tp-header h1 {
        margin: 0.15rem 0 0.2rem 0;
        font-size: 2rem;
        letter-spacing: 0;
        color: #172033;
    }
    .tp-header p {
        margin: 0;
        color: #677084;
        font-size: 0.95rem;
    }
    .tp-kicker {
        color: #f04452;
        font-weight: 700;
        font-size: 0.8rem;
        text-transform: uppercase;
    }
    .tp-section-title {
        font-weight: 700;
        color: #172033;
        margin: 0.75rem 0 0.5rem 0;
    }
    .tp-agent-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.55rem;
        margin-bottom: 0.8rem;
    }
    .tp-agent {
        min-height: 66px;
        border: 1px solid #e2e6ef;
        border-radius: 8px;
        background: #ffffff;
        padding: 0.65rem 0.75rem;
        display: flex;
        gap: 0.65rem;
        align-items: center;
    }
    .tp-agent-icon {
        width: 34px;
        height: 34px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f1f4f9;
        font-size: 1.1rem;
        flex: 0 0 auto;
    }
    .tp-agent-name {
        color: #172033;
        font-weight: 650;
        line-height: 1.15;
    }
    .tp-agent-status {
        color: #7a8498;
        font-size: 0.8rem;
        margin-top: 0.18rem;
    }
    .tp-agent-done {
        border-color: #bbefd2;
        background: #f3fff8;
    }
    .tp-agent-active {
        border-color: #ffd38b;
        background: #fff9eb;
    }
    .tp-agent-active .tp-agent-status {
        color: #a15c00;
    }
    .tp-overview {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 0.55rem;
        margin: 0.5rem 0 1rem 0;
    }
    .tp-stat {
        background: #ffffff;
        border: 1px solid #e2e6ef;
        border-radius: 8px;
        padding: 0.75rem;
        min-height: 72px;
    }
    .tp-stat-label {
        color: #7a8498;
        font-size: 0.78rem;
        margin-bottom: 0.28rem;
    }
    .tp-stat-value {
        color: #172033;
        font-weight: 700;
        font-size: 0.98rem;
        overflow-wrap: anywhere;
    }
    .tp-logbox {
        border: 1px solid #e2e6ef;
        background: #ffffff;
        border-radius: 8px;
        max-height: 420px;
        overflow-y: auto;
        padding: 0.35rem;
    }
    .tp-log {
        padding: 0.5rem 0.55rem;
        border-bottom: 1px solid #eef1f6;
        color: #344054;
        font-size: 0.86rem;
        line-height: 1.45;
    }
    .tp-log:last-child {
        border-bottom: 0;
    }
    .tp-log-success {
        border-left: 3px solid #28b463;
    }
    .tp-log-warning {
        border-left: 3px solid #f59f00;
    }
    .tp-log-error {
        border-left: 3px solid #e03131;
    }
    .tp-log-info {
        border-left: 3px solid #4c6ef5;
    }
    .tp-empty {
        border: 1px dashed #cdd4e3;
        background: #ffffff;
        border-radius: 8px;
        padding: 1rem;
        color: #667085;
    }
    /* Streamlit 的 JSON/代码块复制按钮会调用浏览器 Clipboard API，
       在部分浏览器里会频繁弹权限窗。这里隐藏这些程序化复制入口，
       用户仍然可以像普通网页一样选中文字后 Ctrl+C。 */
    button[title="Copy to clipboard"],
    button[aria-label="Copy to clipboard"],
    [data-testid="stCodeBlock"] button,
    [data-testid="stJson"] button,
    .stCodeBlock button {
        display: none !important;
    }
    @media (max-width: 900px) {
        .tp-agent-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .tp-overview {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
</style>
""", unsafe_allow_html=True)


# ============================================
# 初始化会话状态
# ============================================
# Streamlit 每次交互都会重新运行脚本，所有跨 rerun 的数据都必须放进 session_state。
if "messages" not in st.session_state:
    st.session_state.messages = []
if "travel_state" not in st.session_state:
    st.session_state.travel_state = None
if "completed_agents" not in st.session_state:
    st.session_state.completed_agents = []
if "current_phase" not in st.session_state:
    st.session_state.current_phase = "idle"
if "graph" not in st.session_state:
    st.session_state.graph = None
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "travel-session-1"
if "awaiting_review" not in st.session_state:
    st.session_state.awaiting_review = False
if "pending_user_input" not in st.session_state:
    st.session_state.pending_user_input = None


# ============================================
# 智能体元信息（图标 + 名称）
# ============================================
AGENT_META = {
    "parse_request":           ("🔍", "需求解析器"),
    "supervisor":              ("🎯", "主控调度器"),
    "route_planner":           ("🗺️", "路线规划师"),
    "weather_forecaster":      ("🌤️", "天气预报员"),
    "transport_advisor":       ("🚂", "交通顾问"),
    "accommodation_manager":   ("🏨", "住宿管家"),
    "food_advisor":            ("🍜", "美食达人"),
    "budget_optimizer":        ("💰", "省钱精算师"),
    "summarize":               ("📋", "方案汇总师"),
    "human_review":            ("👤", "人工审核"),
}

WORKFLOW_STEPS = [
    "parse_request",
    "supervisor",
    "route_planner",
    "weather_forecaster",
    "transport_advisor",
    "accommodation_manager",
    "food_advisor",
    "budget_optimizer",
    "summarize",
]


MODEL_PROVIDERS = {
    "OpenAI": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "needs_key": True,
        "help": "OpenAI 官方接口，需要 API Key。",
    },
    "Ollama 本地": {
        "provider": "ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
        "needs_key": False,
        "help": "Ollama 的 OpenAI 兼容接口，通常不需要 API Key。",
    },
    "LM Studio 本地": {
        "provider": "lmstudio",
        "base_url": "http://127.0.0.1:1234/v1",
        "model": "local-model",
        "needs_key": False,
        "help": "LM Studio 本地 OpenAI 兼容服务，通常不需要 API Key。",
    },
    "vLLM / Xinference": {
        "provider": "local-openai-compatible",
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "qwen2.5-7b-instruct",
        "needs_key": False,
        "help": "自部署 OpenAI 兼容服务，可按实际地址和模型名修改。",
    },
    "自定义 OpenAI 兼容": {
        "provider": "custom",
        "base_url": os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")),
        "model": os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
        "needs_key": False,
        "help": "适合第三方代理、公司网关或其它 OpenAI 兼容接口。",
    },
}


def set_env_if_changed(name: str, value: str) -> bool:
    """Set an environment variable and report whether it changed."""
    value = value or ""
    changed = os.getenv(name, "") != value
    os.environ[name] = value
    return changed


def render_workflow_progress(placeholder, completed: list[str]):
    """Render a stable one-row-per-agent progress panel."""
    completed_set = set(completed)
    active_node = next((node for node in WORKFLOW_STEPS if node not in completed_set), None)

    # 先清空 placeholder 再重画，避免同一智能体重复显示多行。
    placeholder.empty()
    with placeholder.container():
        st.markdown("### 执行进度")
        items = []
        for node_name in WORKFLOW_STEPS:
            icon, label = AGENT_META.get(node_name, ("🤖", node_name))
            if node_name in completed_set:
                status = "done"
                text = "完成"
            elif node_name == active_node:
                status = "active"
                text = "执行中"
            else:
                status = "pending"
                text = "待处理"
            items.append(
                f"""
                <div class="tp-agent tp-agent-{status}">
                    <div class="tp-agent-icon">{escape(icon)}</div>
                    <div class="tp-agent-main">
                        <div class="tp-agent-name">{escape(label)}</div>
                        <div class="tp-agent-status">{text}</div>
                    </div>
                </div>
                """
            )
        st.markdown(f'<div class="tp-agent-grid">{"".join(items)}</div>', unsafe_allow_html=True)


def summarize_update(node_name: str, update: dict, elapsed: float | None = None) -> str:
    """Create a compact human-readable summary for a graph update."""
    parts = []
    if elapsed is not None:
        parts.append(f"耗时 {elapsed:.1f}s")

    if node_name == "parse_request":
        dates = update.get("dates", {})
        parts.append(
            "解析结果："
            f"出发地 {update.get('origin') or '未识别'}，"
            f"目的地 {update.get('destination') or '未识别'}，"
            f"{dates.get('days', '未知')}天，"
            f"{update.get('people_count', 1)}人，"
            f"预算 ¥{update.get('budget', 0)}"
        )
    elif node_name == "supervisor":
        msg = ""
        for item in update.get("messages", []):
            if hasattr(item, "content"):
                msg = item.content
        parts.append(msg or "已完成路由判断")
    elif node_name == "route_planner":
        route_plan = update.get("route_plan", {})
        content = route_plan.get("content", "") if isinstance(route_plan, dict) else str(route_plan)
        parts.append(f"生成行程摘要：{content[:120]}{'...' if len(content) > 120 else ''}")
    elif node_name == "weather_forecaster":
        weather = update.get("weather_info", {})
        if isinstance(weather, dict):
            summary = weather.get("summary") or weather.get("city") or "天气信息已生成"
            parts.append(f"天气结果：{summary}")
        else:
            parts.append("天气信息已生成")
    elif node_name == "transport_advisor":
        options = update.get("transport_options", [])
        first = options[0] if options else "交通方案已生成"
        parts.append(f"交通结果：{str(first)[:140]}{'...' if len(str(first)) > 140 else ''}")
    elif node_name == "accommodation_manager":
        options = update.get("accommodation_options", [])
        count = 0
        if options and isinstance(options[0], dict):
            count = len(options[0].get("hotels", []))
        parts.append(f"住宿结果：找到 {count} 个候选" if count else "住宿建议已生成")
    elif node_name == "food_advisor":
        foods = update.get("food_recommendations", [])
        count = 0
        if foods and isinstance(foods[0], dict):
            count = len(foods[0].get("restaurants", []))
        parts.append(f"美食结果：找到 {count} 个候选" if count else "美食建议已生成")
    elif node_name == "budget_optimizer":
        budget = update.get("budget_breakdown", {})
        summary = budget.get("summary") if isinstance(budget, dict) else ""
        parts.append(summary or "预算分析已生成")
    elif node_name == "summarize":
        final_plan = update.get("final_plan", {})
        content = final_plan.get("content", "") if isinstance(final_plan, dict) else ""
        source_count = len(update.get("evidence_sources", []) or [])
        quality = update.get("quality_report", {}) or {}
        quality_score = quality.get("score")
        extra = f"；来源 {source_count} 条"
        if quality_score is not None:
            extra += f"；质量评分 {quality_score}/100"
        parts.append(f"最终方案已汇总：{content[:120]}{'...' if len(content) > 120 else ''}{extra}")
    else:
        changed_keys = [key for key in update.keys() if key != "messages"]
        parts.append("更新字段：" + "、".join(changed_keys) if changed_keys else "节点已完成")

    return "；".join(part for part in parts if part)


def extract_react_trace(update: dict) -> str:
    """Find ReAct Action/Observation trace from a node update."""
    # 优先从结构化业务字段中找 react_trace；
    # 找不到再从 messages 文本里解析。
    for key, value in update.items():
        if key == "messages":
            continue
        if isinstance(value, dict) and value.get("react_trace"):
            return str(value["react_trace"])

    for msg in update.get("messages", []):
        content = getattr(msg, "content", "")
        if " · ReAct]" in content:
            return content.split("\n\nFinal:", 1)[0].split("\n", 1)[-1].strip()
    return ""


def render_execution_log(placeholder, logs: list[dict]):
    """Render detailed streaming execution logs."""
    placeholder.empty()
    with placeholder.container():
        st.markdown("### 执行细节")
        if not logs:
            st.markdown('<div class="tp-empty">等待工作流开始...</div>', unsafe_allow_html=True)
            return
        rows = []
        for log in logs[-18:]:
            level = log.get("level", "info")
            text = f"{log.get('time', '')} · {log.get('text', '')}"
            rows.append(f'<div class="tp-log tp-log-{escape(level)}">{escape(text)}</div>')
        st.markdown(f'<div class="tp-logbox">{"".join(rows)}</div>', unsafe_allow_html=True)


# ============================================
# 异步辅助函数
# ============================================

def run_async(coro):
    """运行异步函数（兼容 Streamlit 的同步环境）"""
    return asyncio.run(coro)


async def process_travel_request(user_input: str):
    """
    处理用户的出游请求 — 调用 LangGraph 工作流。

    流式展示：每完成一个 Agent 节点，立即在 UI 上显示结果。
    使用 Streamlit 的 placeholder + status 实现实时更新。
    """
    from harness import TravelPlannerHarness

    completed = []
    execution_logs = []
    current_phase = "planning"
    final_state = {}
    # UI 不直接调用 graph.astream，而是消费 harness 事件。
    # 这样 CLI、测试、未来 API 服务都可以复用同一套执行逻辑。
    harness = TravelPlannerHarness(thread_id=st.session_state.thread_id)

    # 创建占位符用于实时更新进度和执行细节。
    progress_col, log_col = st.columns([0.9, 1.1])
    with progress_col:
        progress_placeholder = st.empty()
    with log_col:
        log_placeholder = st.empty()
    render_workflow_progress(progress_placeholder, completed)
    render_execution_log(log_placeholder, execution_logs)

    async for event in harness.stream_request(user_input):
        if event.event_type == "interrupt":
            # human_review_node 暂停后进入这里，页面展示审核按钮。
            current_phase = "reviewing"
            st.session_state.awaiting_review = True
            final_state = event.final_state
            execution_logs.append({
                "time": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S"),
                "level": "warning",
                "text": event.message or "流程已暂停，等待用户审核或修改意见",
            })
            render_execution_log(log_placeholder, execution_logs)
            continue

        if event.event_type == "end":
            final_state = event.final_state
            completed = event.completed_nodes
            continue

        node_name = event.node_name
        icon, label = AGENT_META.get(node_name, ("🤖", node_name))

        if event.event_type == "node_start":
            # harness 补发的开始事件，用于实时显示“哪个智能体正在干活”。
            execution_logs.append({
                "time": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S"),
                "level": "info",
                "text": f"{icon} {label} 开始执行",
            })
            render_workflow_progress(progress_placeholder, completed)
            render_execution_log(log_placeholder, execution_logs)
            continue

        if event.event_type == "node_complete":
            # 节点完成事件携带 update，UI 在这里合并最终状态并展示摘要。
            update = event.update
            completed = event.completed_nodes
            final_state = event.final_state

            # 提取该节点的输出文本
            output_text = ""
            if "messages" in update:
                for msg in update["messages"]:
                    if hasattr(msg, "content") and msg.content:
                        output_text = msg.content

            # 更新阶段
            if "current_phase" in update:
                current_phase = update["current_phase"]

            execution_logs.append({
                "time": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S"),
                "level": "success",
                "text": f"{icon} {label} 完成：{summarize_update(node_name, update, event.elapsed)}",
            })
            react_trace = extract_react_trace(update)
            if react_trace:
                # ReAct 轨迹只展示 Action/Observation 摘要，不展示隐藏推理。
                for line in react_trace.splitlines()[:4]:
                    execution_logs.append({
                        "time": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S"),
                        "level": "info",
                        "text": f"{icon} {label} ReAct：{line}",
                    })

            render_workflow_progress(progress_placeholder, completed)
            render_execution_log(log_placeholder, execution_logs)

            # 中间节点的长文本已经在结果区和执行细节里展示，不再塞进聊天历史，
            # 否则用户下一次打开页面会先看到一大串内部过程。

    st.session_state.completed_agents = completed
    st.session_state.current_phase = current_phase
    st.session_state.travel_state = final_state

    return final_state


async def resume_with_review(user_response: str):
    """恢复人机交互 — 传递用户反馈"""
    from harness import TravelPlannerHarness

    final_state = st.session_state.travel_state if isinstance(st.session_state.travel_state, dict) else {}
    # 恢复审核必须使用同一个 thread_id，LangGraph checkpointer 才能找到暂停点。
    harness = TravelPlannerHarness(
        thread_id=st.session_state.thread_id,
        initial_state=final_state,
    )

    async for event in harness.stream_resume(user_response):
        if event.event_type == "interrupt":
            st.session_state.awaiting_review = True
            final_state = event.final_state
            continue
        if event.event_type == "end":
            final_state = event.final_state
            continue
        if event.event_type != "node_complete":
            continue

        final_state = event.final_state

    st.session_state.travel_state = final_state
    if isinstance(final_state, dict):
        st.session_state.current_phase = final_state.get("current_phase", "done")
    st.session_state.awaiting_review = False


# ============================================
# 侧边栏
# ============================================
with st.sidebar:
    st.markdown("## 设置")
    st.caption(f"当前时间：{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')}")

    with st.expander("模型与工具", expanded=True):
        # 模型配置写入环境变量，config.get_llm() 每次创建模型时会读取最新值。
        provider_names = list(MODEL_PROVIDERS.keys())
        current_provider = os.getenv("LLM_PROVIDER", "openai")
        provider_index = 0
        for index, name in enumerate(provider_names):
            if MODEL_PROVIDERS[name]["provider"] == current_provider:
                provider_index = index
                break

        provider_label = st.selectbox("模型提供方", provider_names, index=provider_index)
        provider = MODEL_PROVIDERS[provider_label]
        st.caption(provider["help"])

        default_base_url = os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", provider["base_url"])) or provider["base_url"]
        default_model = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", provider["model"])) or provider["model"]
        default_api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))

        base_url = st.text_input("Base URL", value=default_base_url, help="OpenAI 兼容接口地址")
        model_name = st.text_input("模型名", value=default_model)
        api_key = st.text_input(
            "API Key（本地模型可留空）",
            value=default_api_key,
            type="password",
        )
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.5,
            value=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            step=0.1,
        )

        tavily_key = st.text_input(
            "Tavily API Key",
            value=os.getenv("TAVILY_API_KEY", ""),
            type="password",
        )
        amap_key = st.text_input(
            "高德地图 API Key",
            value=os.getenv("AMAP_API_KEY", ""),
            type="password",
        )

    model_settings_changed = False
    model_settings_changed |= set_env_if_changed("LLM_PROVIDER", provider["provider"])
    model_settings_changed |= set_env_if_changed("LLM_BASE_URL", base_url.strip())
    model_settings_changed |= set_env_if_changed("OPENAI_BASE_URL", base_url.strip())
    model_settings_changed |= set_env_if_changed("LLM_MODEL", model_name.strip())
    model_settings_changed |= set_env_if_changed("OPENAI_MODEL", model_name.strip())
    model_settings_changed |= set_env_if_changed("LLM_API_KEY", api_key.strip())
    model_settings_changed |= set_env_if_changed("OPENAI_API_KEY", api_key.strip())
    model_settings_changed |= set_env_if_changed("LLM_TEMPERATURE", str(temperature))
    set_env_if_changed("TAVILY_API_KEY", tavily_key.strip())
    set_env_if_changed("AMAP_API_KEY", amap_key.strip())

    if provider["needs_key"] and not api_key.strip():
        st.warning("当前模型提供方通常需要 API Key。")

    if model_settings_changed:
        # 模型或 Base URL 变化后重置 graph 单例，避免旧 agent 继续持有旧模型实例。
        try:
            from graph.builder import reset_graph
            reset_graph()
        except Exception:
            pass
        st.session_state.thread_id = f"travel-session-{datetime.now().timestamp()}"
        st.caption("模型配置已更新，新的请求会使用当前设置。")

    st.markdown("---")
    if st.button("🧹 清空当前会话", width="stretch"):
        try:
            from graph.builder import reset_graph
            reset_graph()
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.travel_state = None
        st.session_state.completed_agents = []
        st.session_state.current_phase = "idle"
        st.session_state.awaiting_review = False
        st.session_state.thread_id = f"travel-session-{datetime.now().timestamp()}"
        st.rerun()

    st.markdown("---")

    # 示例请求
    st.markdown("## 示例")
    examples = [
        "明天从北京到蔚县，11人，自驾，玩3天，喜欢古城和小吃",
        "从上海到三亚5天4晚，2人，预算15000元",
        "西安3日游，一个人，预算3000元，喜欢历史",
    ]
    for ex in examples:
        if st.button(ex, width="stretch"):
            st.session_state.pending_user_input = ex
            st.rerun()


# ============================================
# 主界面
# ============================================
render_header()

# 智能体状态面板
render_agent_status(st.session_state.current_phase, st.session_state.completed_agents)

# 对话区域
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        agent = msg.get("agent", "")
        agent_icon = msg.get("agent_icon", "🤖")
        agent_label = msg.get("agent_label", agent)

        if role == "user":
            with st.chat_message("user"):
                st.write(content)
        elif role == "system":
            st.caption(f"📡 {content}")
        else:
            with st.chat_message("assistant"):
                if agent_label:
                    st.caption(f"{agent_icon} **{agent_label}**")
                st.markdown(content)


# 用户输入
typed_input = st.chat_input("描述你的出游计划，例如：我想从北京去成都玩3天，预算5000元")
user_input = st.session_state.pending_user_input or typed_input
st.session_state.pending_user_input = None

if user_input:
    # 显示用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.write(user_input)

    # 处理请求 — 在 assistant 消息区域内实时展示
    with st.chat_message("assistant"):
        try:
            result = run_async(process_travel_request(user_input))
            st.success("🎉 **全部智能体协作完成！** 请查看下方详细结果。")
        except Exception as e:
            st.error(f"❌ 处理出错: {str(e)}")
            st.info("💡 提示：请检查侧边栏里的模型提供方、Base URL、模型名和 API Key（本地模型可留空）")

    # 检查是否需要人机审核
    if st.session_state.current_phase == "reviewing":
        st.session_state.awaiting_review = True

# 人机交互审核
if st.session_state.awaiting_review:
    st.markdown("---")
    st.markdown("### 📋 计划审核")
    st.info("出游计划已生成，请审阅后回复：")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ 确认方案", width="stretch"):
            st.session_state.messages.append({"role": "user", "content": "确认"})
            with st.spinner("处理中..."):
                run_async(resume_with_review("确认"))
            st.rerun()
    with col2:
        feedback = st.text_input("修改意见", placeholder="例如：住宿换成更便宜的")
        if st.button("📝 提交修改", width="stretch") and feedback:
            st.session_state.messages.append({"role": "user", "content": f"修改：{feedback}"})
            with st.spinner("重新规划中..."):
                run_async(resume_with_review(f"修改：{feedback}"))
            st.rerun()
    with col3:
        if st.button("🔄 重新规划", width="stretch"):
            st.session_state.messages.append({"role": "user", "content": "重新规划"})
            with st.spinner("重新规划中..."):
                run_async(resume_with_review("重新规划"))
            st.rerun()

# 展示详细结果面板
if st.session_state.travel_state:
    state = st.session_state.travel_state
    if not isinstance(state, dict):
        st.session_state.travel_state = None
        st.warning("计划状态已重置，请重新提交一次出游需求。")
        st.stop()

    st.markdown("---")
    render_trip_overview(state)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "总览", "天气", "交通", "住宿", "美食", "预算", "来源"
    ])

    with tab1:
        render_final_plan(state.get("final_plan", {}))
        with st.expander("路线规划师原始输出"):
            render_plan_timeline(state.get("route_plan", {}))

    with tab2:
        render_weather_card(state.get("weather_info", {}))

    with tab3:
        render_transport_table(state.get("transport_options", []))

    with tab4:
        render_accommodation_list(state.get("accommodation_options", []))

    with tab5:
        render_food_recommendations(state.get("food_recommendations", []))

    with tab6:
        render_budget_chart(state.get("budget_breakdown", {}))
        render_saving_tips(state.get("optimization_suggestions", []))

    with tab7:
        render_evidence_panel(state.get("evidence_sources", []), state.get("quality_report", {}))
