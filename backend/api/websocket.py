"""
WebSocket 连接管理器
"""

from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 连接管理器。"""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                pass

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            pass
