"""
REST API 路由

旅行规划端点 + Skill 管理 + 评估端点 + 工作区端点
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

router = APIRouter()


# ── 旅行规划端点 ──────────────────────────────────────────

@router.post("/api/travel/plan")
async def plan_travel(request: Request):
    """同步提交旅行规划。"""
    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    query = body.get("query", "")
    session_id = body.get("session_id", "")

    from backend.harness.travel_harness import TravelPlannerHarness
    from graph.builder import get_graph

    thread_id = session_id or str(uuid.uuid4())
    session = request.app.state.session_manager.get_or_create(thread_id)
    session.current_phase = "planning"
    session.awaiting_review = False

    harness = TravelPlannerHarness(thread_id=thread_id, graph=get_graph())
    result = await harness.run_request(query)
    session.travel_state = dict(result.final_state)
    session.completed_agents = list(result.completed_nodes)
    session.current_phase = result.final_state.get("current_phase", session.current_phase)
    session.awaiting_review = bool(result.awaiting_review)

    return {
        "session_id": harness.thread_id,
        "state": result.final_state,
        "completed_agents": result.completed_nodes,
        "awaiting_review": result.awaiting_review,
    }


@router.post("/api/travel/plan/stream")
async def plan_travel_stream(request: Request):
    """SSE 流式推送旅行规划进度。"""
    import logging
    logger = logging.getLogger(__name__)

    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    query = body.get("query", "")
    session_id = body.get("session_id", "")

    from backend.harness.travel_harness import TravelPlannerHarness
    from graph.builder import get_graph

    queue: asyncio.Queue = asyncio.Queue()
    thread_id = session_id or str(uuid.uuid4())
    session = request.app.state.session_manager.get_or_create(thread_id)
    session.current_phase = "planning"
    session.awaiting_review = False

    logger.info(f"[PLAN] Created/Get session: {thread_id}")

    # 节点中文名映射
    NODE_LABELS = {
        "parse_request": "📝 解析需求",
        "supervisor": "🧠 智能调度",
        "route_planner": "🗺️ 路线规划",
        "transport_advisor": "🚄 交通查询",
        "weather_forecaster": "🌤️ 天气预报",
        "accommodation_manager": "🏨 住宿推荐",
        "food_advisor": "🍜 美食推荐",
        "budget_optimizer": "💰 预算分析",
        "summarize": "📋 汇总方案",
        "human_review": "👤 人工审核",
    }

    async def run_and_signal():
        from backend.evaluation.collector import MetricsCollector
        collector = MetricsCollector()
        task_id = f"task-{thread_id[:8]}"
        eval_store = request.app.state.eval_store

        def save_current_metrics(
            accuracy: float = 0.0,
            status: str = "completed",
            final_state: dict[str, Any] | None = None,
            finish: bool = False,
        ):
            """保存当前指标到数据库。"""
            metrics = (
                collector.finish_task(task_id, accuracy=accuracy)
                if finish else collector.snapshot_task(task_id, accuracy=accuracy)
            )
            # 用真实工具调用数，不再用 evidence_count 兜底
            eval_store.save_task_metrics({
                "task_id": metrics.task_id,
                "accuracy": metrics.accuracy,
                "total_latency_ms": metrics.total_latency_ms,
                "step_latencies": metrics.step_latencies,
                "total_tokens": metrics.total_tokens,
                "tool_call_count": metrics.tool_call_count,
                "tool_success_count": metrics.tool_success_count,
                "tool_success_rate": metrics.tool_success_rate,
                "agent_count": metrics.agent_count,
                "iteration_count": metrics.iteration_count,
                "status": status,
            })

        try:
            harness = TravelPlannerHarness(
                thread_id=thread_id, graph=get_graph(),
                metrics_collector=collector,
            )
            # 先发送 session_id
            await queue.put({"type": "session", "session_id": thread_id})

            # 开始记录指标
            collector.start_task(task_id)
            # 立即保存一次（status=in_progress），让仪表盘马上能看到任务
            save_current_metrics(accuracy=0.0, status="in_progress")

            completed_agents: set[str] = set()
            async for event in harness.stream_request(query):
                label = NODE_LABELS.get(event.node_name, event.node_name)
                msg = event.message or ""

                if event.event_type == "node_start":
                    msg = f"{label} 正在执行..."
                elif event.event_type == "node_complete":
                    msg = f"{label} 已完成" + (f"（耗时 {event.elapsed:.1f}s）" if event.elapsed else "")
                    # 只对专业 Agent 节点计数（不重复计 supervisor/parse/summarize/review）
                    agent_nodes = {"route_planner", "weather_forecaster", "transport_advisor",
                                   "accommodation_manager", "food_advisor", "budget_optimizer"}
                    if event.node_name in agent_nodes and event.node_name not in completed_agents:
                        collector.record_agent_spawn(task_id)
                    completed_agents.add(event.node_name)
                    # 从 _metrics 提取最新的 token/tool 数据
                    metrics_data = harness.final_state.get("_metrics", {})
                    t = collector._tasks.get(task_id)
                    if t and metrics_data:
                        t["tokens"] = metrics_data.get("input_tokens", 0) + metrics_data.get("output_tokens", 0)
                        t["tool_calls"] = metrics_data.get("tool_calls", 0)
                        t["tool_successes"] = t["tool_calls"]
                    # 每完成一个节点就保存一次，让仪表盘实时更新
                    save_current_metrics(accuracy=0.5, status="in_progress")
                elif event.event_type == "token":
                    await queue.put({
                        "type": "token",
                        "node": event.node_name,
                        "message": msg,
                        "completed": event.completed_nodes,
                    })
                    continue
                elif event.event_type == "tool_call":
                    # 记录工具调用
                    collector.record_tool_call(task_id)
                    await queue.put({
                        "type": "tool_call",
                        "node": event.node_name,
                        "message": msg,
                        "completed": event.completed_nodes,
                    })
                    continue

                await queue.put({
                    "type": event.event_type,
                    "node": event.node_name,
                    "message": msg,
                    "elapsed": event.elapsed,
                    "completed": event.completed_nodes,
                })

            # 保存 final_state 到应用级 session，供报告/地图/后续恢复使用。
            final_state = dict(harness.final_state)

            # 从 _metrics 累加字段提取真实 token 和工具调用数据
            metrics_data = final_state.get("_metrics", {})
            real_input_tokens = metrics_data.get("input_tokens", 0)
            real_output_tokens = metrics_data.get("output_tokens", 0)
            real_tool_calls = metrics_data.get("tool_calls", 0)

            # 计算真实准确率：基于完成的 Agent 数量和是否有最终方案
            expected_agents = {"route_planner", "weather_forecaster", "transport_advisor",
                               "accommodation_manager", "food_advisor", "budget_optimizer"}
            completed_set = completed_agents & expected_agents
            agent_completion_rate = len(completed_set) / len(expected_agents) if expected_agents else 0
            has_final_plan = 1.0 if final_state.get("final_plan") else 0.0
            accuracy = round(agent_completion_rate * 0.7 + has_final_plan * 0.3, 2)

            # 用真实数据更新 collector
            t = collector._tasks.get(task_id)
            if t:
                t["tokens"] = real_input_tokens + real_output_tokens
                t["tool_calls"] = real_tool_calls
                t["tool_successes"] = real_tool_calls  # 假设都成功（失败的会抛异常）

            save_current_metrics(accuracy=accuracy, status="completed", final_state=final_state, finish=True)

            session.travel_state = final_state
            session.completed_agents = list(final_state.get("_completed", []))
            session.current_phase = final_state.get("current_phase", session.current_phase)
            session.awaiting_review = bool(final_state.get("final_plan")) and not bool(final_state.get("is_approved"))

            await queue.put({"type": "_done"})
        except Exception as e:
            # 异常时也要保存已收集的指标
            try:
                save_current_metrics(accuracy=0.0, status="failed", finish=True)
            except Exception:
                pass
            await queue.put({"type": "_error", "message": str(e)})
        finally:
            # 无论何种原因退出（正常完成、异常、协程取消），都确保最终状态写入。
            # 避免用户切换页面导致 SSE 断开后，任务永远停在"进行中"。
            try:
                existing = eval_store.get_task(task_id)
                if existing and existing.get("status") == "in_progress":
                    final_state = dict(harness.final_state)
                    expected_agents = {"route_planner", "weather_forecaster", "transport_advisor",
                                       "accommodation_manager", "food_advisor", "budget_optimizer"}
                    completed_set = completed_agents & expected_agents
                    agent_completion_rate = len(completed_set) / len(expected_agents) if expected_agents else 0
                    has_final_plan = 1.0 if final_state.get("final_plan") else 0.0
                    accuracy = round(agent_completion_rate * 0.7 + has_final_plan * 0.3, 2)
                    save_current_metrics(accuracy=accuracy, status="completed", final_state=final_state, finish=True)
            except Exception:
                pass

    asyncio.create_task(run_and_signal())

    async def event_generator():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                if item.get("type") in ("_done", "_error"):
                    break
            except asyncio.TimeoutError:
                # 心跳：保持连接活跃
                yield f'data: {{"type": "heartbeat"}}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/travel/resume")
async def resume_travel(request: Request):
    """人工审核后恢复旅行规划。"""
    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    session_id = body.get("session_id", "")
    response = body.get("response", "确认")

    from backend.harness.travel_harness import TravelPlannerHarness
    from graph.builder import get_graph
    from harness.travel_harness import merge_travel_state

    session = request.app.state.session_manager.get(session_id)

    # 会话不存在（后端重启后内存丢失）
    if not session:
        return {"error": "SESSION_EXPIRED", "message": "会话已过期，请重新提交旅行需求"}

    previous_state = dict(session.travel_state or {})

    harness = TravelPlannerHarness(thread_id=session_id, graph=get_graph(), initial_state=previous_state)
    result = await harness.run_resume(response)
    merged_state = merge_travel_state(previous_state, result.final_state)
    session.travel_state = merged_state
    session.completed_agents = list(result.completed_nodes)
    session.current_phase = merged_state.get("current_phase", "done")
    session.awaiting_review = bool(result.awaiting_review)

    return {
        "session_id": session_id,
        "state": merged_state,
        "completed_agents": result.completed_nodes,
        "awaiting_review": result.awaiting_review,
    }


@router.post("/api/travel/resume/stream")
async def resume_travel_stream(request: Request):
    """SSE 流式恢复旅行规划。"""
    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    session_id = body.get("session_id", "")
    response = body.get("response", "确认")

    from backend.harness.travel_harness import TravelPlannerHarness
    from graph.builder import get_graph
    from harness.travel_harness import merge_travel_state

    queue: asyncio.Queue = asyncio.Queue()
    sm = request.app.state.session_manager
    session = sm.get(session_id)

    # 会话不存在（后端重启后内存丢失），返回明确错误
    if not session:
        async def event_generator():
            yield f'data: {{"type": "_error", "message": "SESSION_EXPIRED"}}\n\n'
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    previous_state = dict(session.travel_state or {})

    async def run_and_signal():
        try:
            harness = TravelPlannerHarness(thread_id=session_id, graph=get_graph(), initial_state=previous_state)

            final_state: dict[str, Any] = {}
            completed: list[str] = []

            async def consume_resume():
                nonlocal final_state, completed
                async for event in harness.stream_resume(response):
                    final_state = dict(event.final_state or final_state or {})
                    completed = list(event.completed_nodes or completed)
                    await queue.put({
                        "type": event.event_type,
                        "node": event.node_name,
                        "message": event.message,
                        "elapsed": event.elapsed,
                        "completed": event.completed_nodes,
                        "update": event.update,
                        "state": event.final_state,
                    })

            await asyncio.wait_for(consume_resume(), timeout=45)

            # 保存恢复后的状态。resume 往往只返回"确认"相关字段，必须合并到原计划，
            # 否则报告生成时会丢失 final_plan / route_plan 等核心数据。
            final_state = final_state or dict(harness.final_state)
            merged_state = merge_travel_state(previous_state, final_state)
            session.travel_state = merged_state
            session.completed_agents = completed
            session.current_phase = merged_state.get("current_phase", "done")
            session.awaiting_review = False

            await queue.put({
                "type": "resume_complete",
                "node": "human_review",
                "message": "方案已确认",
                "completed": completed,
                "state": merged_state,
                "awaiting_review": False,
            })
            await queue.put({"type": "_done"})
        except asyncio.TimeoutError:
            await queue.put({"type": "_error", "message": "确认方案超时，请刷新后重试"})
        except Exception as e:
            await queue.put({"type": "_error", "message": str(e)})

    asyncio.create_task(run_and_signal())

    async def event_generator():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"heartbeat\"}\n\n"
                continue
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item.get("type") in ("_done", "_error"):
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── 会话管理 ──────────────────────────────────────────────

@router.get("/api/session/{session_id}/validate")
async def validate_session(session_id: str, request: Request):
    """验证会话是否仍然有效（用于前端检测后端重启）。"""
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if not session:
        return {"valid": False, "reason": "session_not_found"}
    return {"valid": True, "awaiting_review": session.awaiting_review}


@router.get("/api/sessions")
async def list_sessions(request: Request):
    import logging
    logger = logging.getLogger(__name__)
    sm = request.app.state.session_manager
    sessions = sm.list_all()
    logger.info(f"[SESSIONS] Listing {len(sessions)} sessions")
    return [{"session_id": s.session_id, "created_at": s.created_at} for s in sessions]


# ── Skill 管理 ────────────────────────────────────────────

@router.get("/api/skills")
async def list_skills():
    from backend.skills.registry import SkillRegistry
    registry = SkillRegistry()
    return registry.list_metadata()


@router.post("/api/skills/{name}/toggle")
async def toggle_skill(name: str):
    from backend.skills.registry import SkillRegistry
    registry = SkillRegistry()
    enabled = registry.toggle(name)
    return {"name": name, "enabled": enabled}


# ── 评估端点 ──────────────────────────────────────────────

@router.get("/api/metrics")
async def get_metrics(request: Request):
    store = request.app.state.eval_store
    return store.get_all_metrics()


@router.get("/api/tasks")
async def list_tasks(request: Request):
    store = request.app.state.eval_store
    return store.get_all_metrics()


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    store = request.app.state.eval_store
    task = store.get_task(task_id)
    if not task:
        return {"error": "task not found"}
    trajectory = store.get_trajectory(task_id)
    return {**task, "trajectory": trajectory}


@router.get("/api/drift-alerts")
async def get_drift_alerts(request: Request):
    store = request.app.state.eval_store
    return store.get_drift_alerts()


@router.get("/api/optimization/log")
async def get_optimization_log(request: Request):
    store = request.app.state.eval_store
    return store.get_optimization_log()


# ── 报告 & 路线图 ─────────────────────────────────────────

@router.post("/api/travel/report")
async def generate_report(request: Request):
    """生成 Word 旅行报告。"""
    import logging
    logger = logging.getLogger(__name__)

    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    session_id = body.get("session_id", "")

    sm = request.app.state.session_manager
    session = sm.get(session_id)

    logger.info(f"[REPORT] Requested session_id: {session_id}")
    logger.info(f"[REPORT] Session found: {session is not None}")
    if session:
        logger.info(f"[REPORT] travel_state keys: {list(session.travel_state.keys()) if session.travel_state else 'EMPTY'}")

    if not session or not session.travel_state:
        return {"error": "未找到旅行计划数据，请先完成规划"}

    from backend.api.report import generate_report_docx
    docx_bytes = generate_report_docx(session.travel_state)
    destination = session.travel_state.get("destination") or "旅行计划"
    return {
        "filename": f"旅行计划报告_{destination}.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "content_base64": base64.b64encode(docx_bytes).decode("ascii"),
    }


@router.post("/api/travel/route-data")
async def get_route_data(request: Request):
    """提取路线坐标数据，用于前端地图渲染。"""
    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    session_id = body.get("session_id", "")

    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if not session or not session.travel_state:
        return {"error": "未找到旅行计划数据"}

    state = session.travel_state
    locations = []
    routes = []
    seen_names = set()

    # 1. 从 evidence_sources 提取含坐标的数据
    for e in state.get("evidence_sources", []) or []:
        if not isinstance(e, dict):
            continue
        # 检查是否是 driving_route 类型
        snippet = e.get("snippet", "")
        if "distance_km" in snippet or "duration_min" in snippet:
            # 尝试从 snippet 中提取地名（已有结构化数据在 tool 输出中）
            pass

    # 2. 从目的地/出发地获取坐标
    import re
    origin = state.get("origin", "")
    destination = state.get("destination", "")

    # 地理编码函数
    async def geocode(place: str):
        """尝试获取地名坐标。"""
        import httpx
        # 先查静态表
        try:
            from tools.geo_utils import CITY_COORDS
            for city, (lat, lng) in CITY_COORDS.items():
                if city in place or place in city:
                    return {"name": place, "lat": lat, "lng": lng}
        except Exception:
            pass
        # OSM Nominatim
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": place, "format": "json", "limit": 1, "accept-language": "zh-CN"},
                    headers={"User-Agent": "travel-planner/1.0"},
                )
                data = resp.json()
                if data:
                    return {"name": place, "lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        except Exception:
            pass
        return None

    # 3. 从 route_plan 文本中提取景点地名
    route_text = ""
    route_plan = state.get("route_plan", {})
    if isinstance(route_plan, dict):
        route_text = route_plan.get("content", "")
    elif isinstance(route_plan, str):
        route_text = route_plan

    # 提取中文地名（2-6个字，后面可能跟"公园"、"广场"等）
    place_patterns = [
        r'(?:景点|前往|参观|游览|到达)[：:]?\s*([^\n,，。.]{2,10}?)(?:[，,。.\n]|$)',
        r'(?:第[一二三四五六七八九十\d]天)[^\n]*?[：:]\s*([^\n]{2,30})',
    ]
    extracted_places = []
    for pattern in place_patterns:
        matches = re.findall(pattern, route_text)
        for m in matches:
            # 清理：去掉序号、括号等
            cleaned = re.sub(r'^\d+[\.\)、]\s*', '', m.strip())
            cleaned = re.sub(r'[\(\)（）【】]', '', cleaned)
            if 2 <= len(cleaned) <= 15 and cleaned not in seen_names:
                extracted_places.append(cleaned)
                seen_names.add(cleaned)

    # 4. 对所有地点进行地理编码
    all_places = []
    if origin and origin not in seen_names:
        all_places.append(origin)
        seen_names.add(origin)
    if destination and destination not in seen_names:
        all_places.append(destination)
        seen_names.add(destination)
    all_places.extend(extracted_places[:10])  # 最多 10 个景点

    for place in all_places:
        result = await geocode(place)
        if result:
            is_endpoint = place in (origin, destination)
            result["type"] = "origin" if place == origin else ("destination" if place == destination else "waypoint")
            locations.append(result)

    # 5. 构建路线（按顺序连接）
    for i in range(len(locations) - 1):
        routes.append({
            "from": locations[i]["name"],
            "to": locations[i + 1]["name"],
            "from_lat": locations[i]["lat"],
            "from_lng": locations[i]["lng"],
            "to_lat": locations[i + 1]["lat"],
            "to_lng": locations[i + 1]["lng"],
        })

    return {"locations": locations, "routes": routes}


# ── 工作区端点 ────────────────────────────────────────────

@router.get("/api/workspace")
async def get_workspace(request: Request):
    ws = request.app.state.workspace
    return {"path": ws.base_path}


@router.post("/api/workspace")
async def set_workspace(request: Request):
    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    ws = request.app.state.workspace
    ws.set_base(body.get("path", "./output"))
    return {"path": ws.base_path}


@router.get("/api/workspace/files")
async def list_workspace_files(request: Request, path: str = ""):
    ws = request.app.state.workspace
    try:
        return ws.list_files(path)
    except ValueError as e:
        return {"error": str(e)}


@router.get("/api/workspace/file")
async def read_workspace_file(request: Request, path: str = ""):
    ws = request.app.state.workspace
    try:
        content = ws.read_file(path)
        return {"path": path, "content": content}
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}


@router.post("/api/workspace/save")
async def save_workspace_file(request: Request):
    raw = await request.body()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    ws = request.app.state.workspace
    try:
        saved = ws.save_file(body.get("path", ""), body.get("content", ""))
        return {"path": saved}
    except ValueError as e:
        return {"error": str(e)}
