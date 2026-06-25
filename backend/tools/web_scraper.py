"""
Web 抓取工具 — httpx + readability-lxml

带 SSRF 防护: URL scheme 白名单 + 私有网络阻止。
"""

from __future__ import annotations

import ipaddress
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
    """校验 URL 安全性。"""
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
    return url


# ── 抓取逻辑 ─────────────────────────────────────────────

def _extract_content(html: str) -> tuple[str, str]:
    """从 HTML 提取标题和正文。尝试 readability，回退到正则。"""
    try:
        from readability import Document
        doc = Document(html)
        title = doc.title()
        content = doc.summary()
        # 简单去 HTML 标签
        import re
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()
        return title, content[:5000]
    except Exception:
        pass
    # 回退: 正则提取
    import re
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    # 提取 body 文本
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.IGNORECASE | re.DOTALL)
    body = body_match.group(1) if body_match else html
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip()
    return title, text[:5000]


async def _web_scraper(url: str) -> dict[str, str]:
    """抓取网页内容。带 SSRF 防护。"""
    _validate_url(url)

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text

    title, content = _extract_content(html)
    return {"url": url, "title": title, "content": content}


# ── 工具定义 ─────────────────────────────────────────────

web_scraper_tool = ToolDef(
    name="web_scraper",
    description="抓取指定 URL 的网页内容。带 SSRF 防护。",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要抓取的 URL"},
        },
        "required": ["url"],
    },
    func=lambda url: _web_scraper(url),
    capabilities=["web", "scrape"],
)


def register_web_scraper_tools() -> None:
    """注册 Web 抓取工具到 ToolRegistry。"""
    registry = ToolRegistry()
    try:
        registry.register(web_scraper_tool)
    except ValueError:
        pass
