"""
Web 搜索工具 — Tavily 优先，Bing 回退

带 SSRF 防护: 仅允许 http/https scheme，阻止内网地址。
"""

from __future__ import annotations

import ipaddress
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import ToolDef
from .registry import ToolRegistry

# ── SSRF 防护 ────────────────────────────────────────────

_ALLOWED_SCHEMES = {"http", "https"}
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _validate_url(url: str) -> str:
    """校验 URL 安全性。通过则返回规范化 URL，否则抛出 ValueError。"""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"不允许的 URL scheme: {parsed.scheme}")
    hostname = parsed.hostname or ""
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _PRIVATE_NETWORKS:
            if addr in net:
                raise ValueError(f"禁止访问内网地址: {hostname}")
    except ValueError as e:
        if "禁止" in str(e):
            raise
        # hostname 不是 IP，跳过 IP 校验
    return url


# ── 搜索后端 ─────────────────────────────────────────────

async def _tavily_search(query: str) -> list[dict[str, str]]:
    """Tavily API 搜索。"""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        raise ValueError("TAVILY_API_KEY 未设置")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": 5,
                "include_answer": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", "")[:500],
        })
    return results


async def _bing_search(query: str) -> list[dict[str, str]]:
    """Bing 搜索（HTML 抓取回退）。"""
    url = f"https://cn.bing.com/search?q={query}"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text

    results = []
    # 简单正则提取搜索结果
    for match in re.finditer(
        r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
        html,
    ):
        href, title = match.groups()
        title = re.sub(r"<[^>]+>", "", title).strip()
        if title and "bing.com" not in href:
            results.append({"title": title, "url": href, "content": ""})
        if len(results) >= 5:
            break
    return results


async def _web_search(query: str) -> list[dict[str, str]]:
    """Web 搜索: Tavily → Bing → 静态兜底。"""
    try:
        return await _tavily_search(query)
    except Exception:
        pass
    try:
        return await _bing_search(query)
    except Exception:
        pass
    return [{"title": "搜索不可用", "url": "", "content": "请配置 TAVILY_API_KEY 或检查网络连接"}]


# ── 工具定义 ─────────────────────────────────────────────

web_search_tool = ToolDef(
    name="web_search",
    description="搜索互联网获取信息。Tavily 优先，Bing 回退。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
        },
        "required": ["query"],
    },
    func=lambda query: _web_search(query),
    capabilities=["search", "web"],
)

travel_guide_search_tool = ToolDef(
    name="search_travel_guide",
    description="搜索目的地旅游攻略",
    parameters={
        "type": "object",
        "properties": {
            "destination": {"type": "string", "description": "目的地"},
            "days": {"type": "integer", "description": "旅行天数"},
            "style": {"type": "string", "description": "旅行风格"},
        },
        "required": ["destination"],
    },
    func=lambda destination, days=3, style="": _web_search(f"{destination} {days}天旅游攻略 {style}"),
    capabilities=["search", "travel"],
)


def register_web_search_tools() -> None:
    """注册 Web 搜索工具到 ToolRegistry。"""
    registry = ToolRegistry()
    for tool in [web_search_tool, travel_guide_search_tool]:
        try:
            registry.register(tool)
        except ValueError:
            pass  # 已注册
