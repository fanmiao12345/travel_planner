"""
记忆管理器门面

统一三层记忆接口: WorkingMemory / EpisodicMemory / SemanticMemory。
"""

from __future__ import annotations

from typing import Any

from .episodic import EpisodicMemory
from .semantic import SemanticMemory
from .working import WorkingMemory


class MemoryManager:
    """记忆管理器门面。"""

    def __init__(
        self,
        working_window: int = 20,
        memory_db_path: str = ":memory:",
        semantic_path: str = "data/user_profile.json",
    ) -> None:
        self.working = WorkingMemory(window_size=working_window)
        self.episodic = EpisodicMemory(db_path=memory_db_path)
        self.semantic = SemanticMemory(file_path=semantic_path)

    async def initialize(self) -> None:
        """初始化所有记忆层。"""
        await self.episodic.initialize()
        await self.semantic.initialize()

    async def close(self) -> None:
        """关闭所有记忆层。"""
        await self.episodic.close()

    def add_turn(self, role: str, content: str) -> None:
        """添加一轮对话到工作记忆。"""
        self.working.add(role, content)

    def get_working_messages(self) -> list[dict[str, str]]:
        """获取工作记忆消息列表。"""
        return self.working.get_messages()

    def get_working_context(self) -> str:
        """获取工作记忆上下文字符串。"""
        return self.working.get_context_string()

    async def store_episodic(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """存储到情节记忆。"""
        return await self.episodic.store(content, metadata or {})

    async def recall_episodic(self, query: str, top_k: int = 5) -> list:
        """从情节记忆检索。"""
        return await self.episodic.recall(query, top_k)

    async def compress_episodic(self, max_items: int = 20, max_chars: int = 1200) -> str:
        """压缩情节记忆为摘要。"""
        return await self.episodic.compress(max_items, max_chars)

    async def get_profile(self) -> dict[str, Any]:
        """获取用户画像。"""
        return await self.semantic.get_profile()

    async def update_profile(self, insights: dict[str, Any]) -> None:
        """更新用户画像。"""
        await self.semantic.update(insights)

    async def prefetch_context(self, query: str) -> str:
        """预取上下文: 用户画像 + 情节记忆检索结果。"""
        parts: list[str] = []

        # 用户画像
        profile = await self.semantic.get_profile()
        if profile.get("visited_cities"):
            parts.append(f"曾到访城市: {', '.join(profile['visited_cities'])}")
        if profile.get("travel_preferences"):
            prefs = ", ".join(f"{k}={v}" for k, v in profile["travel_preferences"].items())
            parts.append(f"旅行偏好: {prefs}")
        if profile.get("style"):
            parts.append(f"旅行风格: {profile['style']}")

        # 情节记忆
        memories = await self.episodic.recall(query, top_k=3)
        for m in memories:
            if m.score > 0.3:
                parts.append(f"[历史] {m.content[:200]}")

        return "\n".join(parts) if parts else ""
