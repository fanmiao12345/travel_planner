"""
FastAPI 应用工厂

- Lifespan: 初始化 EvalStore, DriftDetector, EvalPipeline, MemoryManager, WorkspaceManager
- 自注册: import skills/ 模块触发 SkillRegistry.register()
- CORS: allow_origins=["*"]
- 挂载 routes + WebSocket
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .websocket import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期: 启动时初始化，关闭时清理。"""
    from backend.core.config import get_settings
    from backend.evaluation.store import EvalStore
    from backend.evaluation.drift import DriftDetector
    from backend.evaluation.pipeline import EvaluationPipeline
    from backend.memory.manager import MemoryManager
    from backend.workspace.manager import WorkspaceManager
    from backend.session.manager import SessionManager

    settings = get_settings()

    # 初始化评估存储
    eval_store = EvalStore(db_path=settings.eval_db_path)
    await eval_store.initialize()
    app.state.eval_store = eval_store

    # 初始化漂移检测
    drift = DriftDetector(threshold=settings.eval_drift_threshold, min_samples=settings.eval_drift_min_samples)
    app.state.drift_detector = drift

    # 初始化评估管线
    pipeline = EvaluationPipeline(
        store=eval_store, drift_detector=drift,
        auto_judge=settings.eval_auto_judge, auto_optimize=settings.eval_auto_optimize,
    )
    app.state.eval_pipeline = pipeline

    # 初始化记忆管理器
    memory = MemoryManager(
        working_window=settings.memory_working_window,
        memory_db_path=settings.memory_db_path,
        semantic_path=settings.semantic_memory_path,
    )
    await memory.initialize()
    app.state.memory = memory

    # 初始化工作区管理器
    workspace = WorkspaceManager(base_path=settings.workspace_path)
    app.state.workspace = workspace

    # 初始化会话管理器
    app.state.session_manager = SessionManager()

    # 初始化 WebSocket 管理器
    app.state.ws_manager = ConnectionManager()

    # 自注册: 导入 Skill 模块触发 SkillRegistry.register()
    from backend.skills import (  # noqa: F401
        weather_skill, route_skill, transport_skill,
        accommodation_skill, food_skill, budget_skill,
    )

    # 注册 MCP 工具桥接
    from backend.tools.mcp_bridge import register_mcp_tools
    register_mcp_tools()

    # 注册 web_search / web_scraper 工具
    from backend.tools.web_search import register_web_search_tools
    from backend.tools.web_scraper import register_web_scraper_tools
    register_web_search_tools()
    register_web_scraper_tools()

    yield

    # 清理
    await memory.close()
    await eval_store.close()


def create_app() -> FastAPI:
    """FastAPI 应用工厂。"""
    app = FastAPI(
        title="出游计划自动规划多智能体平台",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST 路由
    app.include_router(router)

    # WebSocket
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        ws_manager: ConnectionManager = websocket.app.state.ws_manager
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                await ws_manager.send_personal(websocket, {"type": "ack", "data": data})
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    # 健康检查
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
