"""
会话管理器 — 内存存储
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    session_id: str
    thread_id: str
    created_at: float = field(default_factory=time.time)
    messages: list[dict[str, str]] = field(default_factory=list)
    travel_state: dict[str, Any] = field(default_factory=dict)
    completed_agents: list[str] = field(default_factory=list)
    current_phase: str = ""
    awaiting_review: bool = False


class SessionManager:
    """会话管理器（内存）。"""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, thread_id: str | None = None) -> Session:
        sid = str(uuid.uuid4())
        tid = thread_id or sid
        session = Session(session_id=sid, thread_id=tid)
        self._sessions[sid] = session
        return session

    def get_or_create(self, session_id: str, thread_id: str | None = None) -> Session:
        """按前端传入的 session_id 获取或创建会话。

        SSE 接口使用 LangGraph thread_id 作为前端 session_id。如果这里每次
        new 一个 SessionManager 或随机生成 sid，报告/地图/恢复状态都会找不到
        同一个会话。
        """
        if session_id in self._sessions:
            return self._sessions[session_id]
        sid = session_id or str(uuid.uuid4())
        session = Session(session_id=sid, thread_id=thread_id or sid)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list_all(self) -> list[Session]:
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None
