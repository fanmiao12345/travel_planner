"""
证据 SQLite 存储 + 可信度评分

按域名启发式评分:
- 0.85: 官方旅游网站, gov.cn, wikipedia
- 0.6: 默认
- 0.4: 社交媒体 (zhihu, weibo, xiaohongshu)
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any


# ── 可信度评分 ────────────────────────────────────────────

_HIGH_CREDIBILITY = {"gov.cn", "wikipedia.org", "official", "travelchina.org.cn", "cnta.gov.cn"}
_LOW_CREDIBILITY = {"zhihu.com", "weibo.com", "xiaohongshu.com", "douyin.com", "bilibili.com"}


def _score_url(url: str) -> float:
    """根据 URL 域名评估可信度。"""
    url_lower = url.lower()
    for domain in _HIGH_CREDIBILITY:
        if domain in url_lower:
            return 0.85
    for domain in _LOW_CREDIBILITY:
        if domain in url_lower:
            return 0.4
    return 0.6


# ── 证据数据结构 ──────────────────────────────────────────

@dataclass
class Evidence:
    evidence_id: str      # "E0001", "E0002", ...
    source_url: str
    captured_at: float
    original_text: str    # 截断到 5000 字符
    summary: str          # 截断到 500 字符
    credibility_score: float
    source_type: str      # "web_search" | "web_scraper" | "manual"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> tuple:
        return (
            self.evidence_id, self.source_url, self.captured_at,
            self.original_text, self.summary, self.credibility_score,
            self.source_type, json.dumps(self.metadata, ensure_ascii=False),
        )

    @classmethod
    def from_row(cls, row: tuple) -> Evidence:
        return cls(
            evidence_id=row[0], source_url=row[1], captured_at=row[2],
            original_text=row[3], summary=row[4], credibility_score=row[5],
            source_type=row[6], metadata=json.loads(row[7]),
        )


# ── 证据存储 ─────────────────────────────────────────────

class EvidenceStore:
    """SQLite 证据存储。"""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._counter = 0

    async def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                captured_at REAL NOT NULL,
                original_text TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                credibility_score REAL NOT NULL DEFAULT 0.6,
                source_type TEXT NOT NULL DEFAULT 'manual',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.commit()
        # 恢复计数器
        cursor = self._conn.execute("SELECT COUNT(*) FROM evidence")
        self._counter = cursor.fetchone()[0]

    async def store(
        self,
        source_url: str,
        original_text: str,
        summary: str = "",
        credibility_score: float | None = None,
        source_type: str = "manual",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if not self._conn:
            await self.initialize()
        self._counter += 1
        eid = f"E{self._counter:04d}"
        if credibility_score is None:
            credibility_score = _score_url(source_url)
        evidence = Evidence(
            evidence_id=eid, source_url=source_url, captured_at=time.time(),
            original_text=original_text[:5000], summary=summary[:500],
            credibility_score=credibility_score, source_type=source_type,
            metadata=metadata or {},
        )
        self._conn.execute(  # type: ignore[union-attr]
            "INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            evidence.to_row(),
        )
        self._conn.commit()  # type: ignore[union-attr]
        return eid

    async def get(self, evidence_id: str) -> Evidence | None:
        if not self._conn:
            return None
        cursor = self._conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,))
        row = cursor.fetchone()
        return Evidence.from_row(row) if row else None

    async def get_all(self) -> list[Evidence]:
        if not self._conn:
            return []
        cursor = self._conn.execute("SELECT * FROM evidence ORDER BY captured_at DESC")
        return [Evidence.from_row(row) for row in cursor.fetchall()]

    async def search(self, query: str, top_k: int = 10) -> list[Evidence]:
        """关键词搜索证据。"""
        if not self._conn:
            return []
        query_lower = query.lower()
        cursor = self._conn.execute("SELECT * FROM evidence")
        results: list[Evidence] = []
        for row in cursor:
            evidence = Evidence.from_row(row)
            if (query_lower in evidence.original_text.lower() or
                query_lower in evidence.summary.lower()):
                results.append(evidence)
            if len(results) >= top_k:
                break
        return results

    async def dedup(self, url: str) -> bool:
        """检查 URL 是否已存在。返回 True 如果是新的。"""
        if not self._conn:
            return True
        cursor = self._conn.execute("SELECT 1 FROM evidence WHERE source_url = ?", (url,))
        return cursor.fetchone() is None

    async def get_by_ids(self, evidence_ids: list[str]) -> list[Evidence]:
        if not self._conn:
            return []
        placeholders = ",".join("?" for _ in evidence_ids)
        cursor = self._conn.execute(
            f"SELECT * FROM evidence WHERE evidence_id IN ({placeholders})", evidence_ids
        )
        return [Evidence.from_row(row) for row in cursor.fetchall()]

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
