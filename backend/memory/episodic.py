"""
L2 情节记忆 — SQLite + hash 嵌入 + 余弦相似度 + 时间衰减

轻量级向量检索，无需外部 embedding 模型。
使用 hash-based bag-of-words 嵌入 (64 维)。
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
import uuid
from typing import Any

from .base import Memory, MemoryProvider, MemoryType


def _terms(text: str) -> list[str]:
    """分词 + 简单词干化。"""
    words = re.findall(r"[a-zA-Z一-鿿]+", text.lower())
    # 简单词干: 去掉常见后缀
    result = []
    for w in words:
        if len(w) > 3:
            for suffix in ("ing", "tion", "ment", "ness", "ers", "ies", "ed", "er", "ly", "s"):
                if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                    w = w[: -len(suffix)]
                    break
        result.append(w)
    return result


def _hash_embed(text: str, dim: int = 64) -> list[float]:
    """Hash-based bag-of-words 嵌入。返回 L2 归一化向量。"""
    vec = [0.0] * dim
    for term in _terms(text):
        h = hash(term) % dim
        vec[h] += 1.0
    # L2 归一化
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class EpisodicMemory(MemoryProvider):
    """SQLite 情节记忆。"""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        """初始化数据库表。"""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                embedding TEXT NOT NULL DEFAULT '[]',
                decay_factor REAL NOT NULL DEFAULT 1.0,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    async def store(self, content: str, metadata: dict[str, Any]) -> str:
        """存储一条记忆。返回 UUID。"""
        if not self._conn:
            await self.initialize()
        mem_id = str(uuid.uuid4())
        embedding = _hash_embed(content)
        now = time.time()
        self._conn.execute(  # type: ignore[union-attr]
            "INSERT INTO memories (id, content, metadata, embedding, decay_factor, created_at) VALUES (?, ?, ?, ?, 1.0, ?)",
            (mem_id, content[:5000], json.dumps(metadata, ensure_ascii=False), json.dumps(embedding), now),
        )
        self._conn.commit()  # type: ignore[union-attr]
        return mem_id

    async def recall(self, query: str, top_k: int = 5) -> list[Memory]:
        """检索相关记忆（余弦相似度 × 时间衰减）。"""
        if not self._conn:
            await self.initialize()
        query_vec = _hash_embed(query)
        now = time.time()

        cursor = self._conn.execute("SELECT id, content, metadata, embedding, decay_factor, created_at FROM memories")  # type: ignore[union-attr]
        results: list[tuple[float, Memory]] = []
        for row in cursor:
            mem_id, content, metadata_json, embedding_json, decay_factor, created_at = row
            embedding = json.loads(embedding_json)
            sim = _cosine_similarity(query_vec, embedding)
            # 指数时间衰减: half_life = 1 天
            age_hours = (now - created_at) / 3600.0
            time_decay = math.exp(-0.693 * age_hours / 24.0)
            score = sim * decay_factor * time_decay
            metadata = json.loads(metadata_json)
            results.append((score, Memory(
                id=mem_id, content=content, memory_type=MemoryType.EPISODIC,
                metadata=metadata, score=score,
            )))

        results.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in results[:top_k]]

    async def apply_decay(self, half_life_seconds: float = 86400) -> None:
        """对所有记忆应用时间衰减。"""
        if not self._conn:
            return
        now = time.time()
        self._conn.execute(
            "UPDATE memories SET decay_factor = decay_factor * 0.95 WHERE ? - created_at > ?",
            (now, half_life_seconds),
        )
        self._conn.commit()

    async def compress(self, max_items: int = 20, max_chars: int = 1200) -> str:
        """压缩记忆为摘要文本。"""
        memories = await self.recall("", top_k=max_items)
        lines = []
        total = 0
        for m in memories:
            if total + len(m.content) > max_chars:
                break
            lines.append(m.content)
            total += len(m.content)
        return "\n---\n".join(lines)

    async def clear(self) -> None:
        """清空所有记忆。"""
        if self._conn:
            self._conn.execute("DELETE FROM memories")
            self._conn.commit()

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn:
            self._conn.close()
            self._conn = None
