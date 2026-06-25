"""
L3 语义记忆 — JSON 文件用户画像

存储用户旅行偏好、到访城市、风格等持久化信息。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import Memory, MemoryProvider, MemoryType

_DEFAULT_PROFILE: dict[str, Any] = {
    "travel_preferences": {},  # e.g. {"hotel_type": "民宿", "food_spice": "微辣"}
    "visited_cities": [],      # e.g. ["北京", "成都"]
    "style": "",               # e.g. "穷游" / "奢华"
    "notes": [],               # 自由文本笔记
}


class SemanticMemory(MemoryProvider):
    """JSON 文件语义记忆。"""

    def __init__(self, file_path: str = "data/user_profile.json") -> None:
        self._file_path = Path(file_path)
        self._profile: dict[str, Any] = {}

    async def initialize(self) -> None:
        """加载或创建用户画像。"""
        if self._file_path.exists():
            try:
                self._profile = json.loads(self._file_path.read_text(encoding="utf-8"))
            except Exception:
                self._profile = dict(_DEFAULT_PROFILE)
        else:
            self._profile = dict(_DEFAULT_PROFILE)
            await self._save()

    async def get_profile(self) -> dict[str, Any]:
        """获取用户画像。"""
        if not self._profile:
            await self.initialize()
        return dict(self._profile)

    async def update(self, insights: dict[str, Any]) -> None:
        """深度合并更新用户画像。"""
        if not self._profile:
            await self.initialize()
        self._deep_merge(self._profile, insights)
        await self._save()

    async def store(self, content: str, metadata: dict[str, Any]) -> str:
        """存储一条笔记到 notes[]。上限 50 条。"""
        if not self._profile:
            await self.initialize()
        notes = self._profile.setdefault("notes", [])
        notes.append(content[:500])
        if len(notes) > 50:
            self._profile["notes"] = notes[-50:]
        await self._save()
        return f"note-{len(self._profile['notes'])}"

    async def recall(self, query: str, top_k: int = 5) -> list[Memory]:
        """大小写不敏感子串匹配检索。"""
        if not self._profile:
            await self.initialize()
        query_lower = query.lower()
        results: list[Memory] = []

        # 搜索 notes
        for i, note in enumerate(reversed(self._profile.get("notes", []))):
            if query_lower in note.lower():
                results.append(Memory(
                    id=f"semantic-note-{i}",
                    content=note,
                    memory_type=MemoryType.SEMANTIC,
                    metadata={"source": "notes"},
                    score=1.0,
                ))
            if len(results) >= top_k:
                break

        # 搜索 visited_cities
        if len(results) < top_k:
            for city in self._profile.get("visited_cities", []):
                if query_lower in city.lower():
                    results.append(Memory(
                        id=f"semantic-city-{city}",
                        content=f"曾到访: {city}",
                        memory_type=MemoryType.SEMANTIC,
                        metadata={"source": "visited_cities"},
                        score=0.8,
                    ))

        return results[:top_k]

    async def clear(self) -> None:
        """重置为默认画像。"""
        self._profile = dict(_DEFAULT_PROFILE)
        await self._save()

    async def _save(self) -> None:
        """持久化到文件。"""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(
            json.dumps(self._profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        """深度合并: dict 递归合并，list 去重追加，其他直接覆盖。"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                SemanticMemory._deep_merge(base[key], value)
            elif key in base and isinstance(base[key], list) and isinstance(value, list):
                existing = set(str(x) for x in base[key])
                for item in value:
                    if str(item) not in existing:
                        base[key].append(item)
                        existing.add(str(item))
            else:
                base[key] = value
