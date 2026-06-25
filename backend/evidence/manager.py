"""
证据管理器门面

从搜索/抓取结果自动捕获证据，构建 LLM 上下文引用块。
"""

from __future__ import annotations

from typing import Any

from .store import Evidence, EvidenceStore


class EvidenceManager:
    """证据管理器门面。"""

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    async def capture_from_search(
        self, search_results: list[dict[str, str]], query: str = ""
    ) -> list[str]:
        """从搜索结果批量捕获证据。返回证据 ID 列表。"""
        ids: list[str] = []
        for item in search_results:
            url = item.get("url", "")
            if not url:
                continue
            is_new = await self._store.dedup(url)
            if not is_new:
                continue
            eid = await self._store.store(
                source_url=url,
                original_text=item.get("content", ""),
                summary=item.get("title", "")[:500],
                source_type="web_search",
                metadata={"query": query},
            )
            ids.append(eid)
        return ids

    async def capture_from_scrape(
        self, scrape_result: dict[str, str], query: str = ""
    ) -> str | None:
        """从抓取结果捕获证据。返回证据 ID。"""
        url = scrape_result.get("url", "")
        if not url:
            return None
        return await self._store.store(
            source_url=url,
            original_text=scrape_result.get("content", ""),
            summary=scrape_result.get("title", "")[:500],
            source_type="web_scraper",
            metadata={"query": query},
        )

    async def build_context_for_llm(self, evidence_ids: list[str] | None = None) -> str:
        """构建 LLM 上下文引用块。"""
        if evidence_ids:
            evidences = await self._store.get_by_ids(evidence_ids)
        else:
            evidences = await self._store.get_all()

        if not evidences:
            return ""

        lines = ["[Evidence Database -- cite these using [EXXXX] notation]"]
        for e in evidences:
            pct = int(e.credibility_score * 100)
            lines.append(f"[{e.evidence_id}] {e.summary} -- {e.source_url} (credibility: {pct}%)")
            if e.original_text:
                lines.append(f"  Summary: {e.original_text[:200]}")
        return "\n".join(lines)

    async def get_citation_table(self, cited_ids: list[str]) -> list[dict[str, str]]:
        """获取引用表格数据。"""
        evidences = await self._store.get_by_ids(cited_ids)
        return [
            {
                "id": e.evidence_id,
                "url": e.source_url,
                "summary": e.summary,
                "credibility": f"{int(e.credibility_score * 100)}%",
            }
            for e in evidences
        ]

    async def close(self) -> None:
        await self._store.close()
