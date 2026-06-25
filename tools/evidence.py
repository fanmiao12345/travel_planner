"""Evidence extraction and lightweight plan quality checks.

这个模块借鉴 deepresearch-agent 的证据链思路，但保持轻量：
- 不引入数据库，证据只随一次 TravelState 流转。
- 不替代搜索工具，只从工具返回结果中抽取 URL/API 来源。
- 汇总阶段根据证据覆盖情况给出可解释的质量检查。
"""

from __future__ import annotations

import json
import re
from typing import Any


URL_RE = re.compile(r"https?://[^\s\"'<>，。；、)）]+")
ACTIVITY_WORDS = ("活动", "节庆", "赛事", "展会", "演唱会", "音乐节", "庙会", "马拉松", "比赛")
OFFICIAL_HINTS = ("gov.cn", ".gov", "官网", "官方", "文旅", "文化和旅游", "主办方", "票务", "公告")


def _safe_json(value: Any) -> Any:
    """Best-effort JSON parser for tool outputs."""
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _short(text: Any, limit: int = 220) -> str:
    """Return compact single-line text for evidence snippets."""
    value = str(text or "").replace("\n", " ").strip()
    return value[:limit] + ("..." if len(value) > limit else "")


def is_official_source(url: str = "", title: str = "", snippet: str = "") -> bool:
    """Heuristic official-source detector used for evidence quality checks."""
    text = f"{url} {title} {snippet}".lower()
    return any(hint.lower() in text for hint in OFFICIAL_HINTS)


def _source_type(source: str, tool_name: str) -> str:
    """Classify a source so the quality report can check coverage."""
    text = f"{source} {tool_name}".lower()
    if any(key in text for key in ("amap", "osrm", "driving", "route")):
        return "route_api"
    if any(key in text for key in ("open-meteo", "weather", "air_quality")):
        return "weather_api"
    if any(key in text for key in ("tavily", "duckduckgo", "search", "web")):
        return "web_search"
    return "tool"


def _append_web_items(
    evidence: list[dict[str, Any]],
    items: list[Any],
    agent_name: str,
    tool_name: str,
    source: str,
    category: str,
) -> None:
    """Extract title/url/snippet evidence entries from search-like lists."""
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or item.get("url") or category
        url = item.get("url") or item.get("FirstURL") or ""
        snippet = item.get("snippet") or item.get("content") or item.get("reason") or ""
        if not title and not url and not snippet:
            continue
        evidence.append({
            "agent": agent_name,
            "tool": tool_name,
            "category": category,
            "source": source or "search",
            "source_type": _source_type(source or "search", tool_name),
            "title": _short(title, 120),
            "url": url,
            "snippet": _short(snippet),
            "date_candidates": item.get("date_candidates", []),
            "is_official": bool(item.get("is_official")) or is_official_source(url, title, snippet),
        })


def extract_evidence_from_value(
    value: Any,
    agent_name: str = "",
    tool_name: str = "",
) -> list[dict[str, Any]]:
    """Extract evidence entries from a tool output or arbitrary value."""
    data = _safe_json(value)
    evidence: list[dict[str, Any]] = []

    if isinstance(data, dict):
        source = str(data.get("source") or data.get("provider") or "")

        if isinstance(data.get("results"), list):
            _append_web_items(evidence, data["results"], agent_name, tool_name, source, "search_result")

        if isinstance(data.get("places"), list):
            _append_web_items(evidence, data["places"], agent_name, tool_name, source, "trending_place")

        if isinstance(data.get("candidates"), list):
            _append_web_items(evidence, data["candidates"], agent_name, tool_name, source, "event_candidate")

        if source in {"amap", "osrm", "openstreetmap"} or "distance_km" in data or "duration_min" in data:
            query = data.get("query", {}) if isinstance(data.get("query"), dict) else {}
            title = f"{query.get('origin') or data.get('origin', {}).get('name') or '起点'} → {query.get('destination') or data.get('destination', {}).get('name') or '终点'} 驾车路线"
            evidence.append({
                "agent": agent_name,
                "tool": tool_name,
                "category": "driving_route",
                "source": source or "route_tool",
                "source_type": "route_api",
                "title": _short(title, 120),
                "url": "",
                "snippet": _short(f"距离 {data.get('distance_km', '未知')} km，预计 {data.get('duration_min', '未知')} 分钟。"),
            })

        if "forecast" in data or "current" in data:
            evidence.append({
                "agent": agent_name,
                "tool": tool_name,
                "category": "weather",
                "source": "Open-Meteo",
                "source_type": "weather_api",
                "title": _short(f"{data.get('city') or data.get('requested_city') or '目的地'} 天气预报", 120),
                "url": "https://open-meteo.com/",
                "snippet": _short(data),
            })

        if "aqi" in data or "pm25" in data:
            evidence.append({
                "agent": agent_name,
                "tool": tool_name,
                "category": "air_quality",
                "source": "Open-Meteo Air Quality",
                "source_type": "weather_api",
                "title": _short(f"{data.get('city') or data.get('requested_city') or '目的地'} 空气质量", 120),
                "url": "https://open-meteo.com/en/docs/air-quality-api",
                "snippet": _short(data),
            })

    elif isinstance(value, str):
        for url in URL_RE.findall(value):
            evidence.append({
                "agent": agent_name,
                "tool": tool_name,
                "category": "url",
                "source": "text",
                "source_type": "web_search",
                "title": url,
                "url": url,
                "snippet": "",
            })

    return dedupe_evidence(evidence)


def collect_evidence_from_messages(messages: list[Any], agent_name: str) -> list[dict[str, Any]]:
    """Extract evidence from LangGraph ReAct ToolMessage objects."""
    evidence: list[dict[str, Any]] = []
    for msg in messages:
        msg_type = getattr(msg, "type", "")
        class_name = msg.__class__.__name__
        if msg_type != "tool" and class_name != "ToolMessage":
            continue
        evidence.extend(extract_evidence_from_value(
            getattr(msg, "content", ""),
            agent_name=agent_name,
            tool_name=getattr(msg, "name", "") or "tool",
        ))
    return dedupe_evidence(evidence)


def dedupe_evidence(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate sources by URL when possible, otherwise by title/tool."""
    result: list[dict[str, Any]] = []
    positions: dict[tuple[str, str, str, str], int] = {}
    for item in sources or []:
        url = str(item.get("url") or "")
        key = (
            url,
            str(item.get("title") or ""),
            str(item.get("tool") or ""),
            str(item.get("category") or ""),
        )
        if key in positions:
            if item.get("id"):
                index = positions[key]
                result[index] = {**result[index], **item}
            continue
        positions[key] = len(result)
        result.append(item)
    return result


def attach_evidence_ids(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach stable display IDs used by the final plan prompt."""
    result = []
    for index, item in enumerate(dedupe_evidence(sources), start=1):
        with_id = dict(item)
        with_id["id"] = with_id.get("id") or f"S{index}"
        result.append(with_id)
    return result


def format_evidence_for_prompt(sources: list[dict[str, Any]], limit: int = 18) -> str:
    """Format evidence entries for LLM summarization."""
    if not sources:
        return "暂无可引用来源。凡是未被工具证据支持的信息，都必须标注“需二次确认”。"
    lines = []
    for item in sources[:limit]:
        url = f" {item.get('url')}" if item.get("url") else ""
        lines.append(
            f"[{item.get('id')}] {item.get('title') or item.get('category')} "
            f"({item.get('source')}/{item.get('tool')}){url} - {_short(item.get('snippet'), 140)}"
        )
    return "\n".join(lines)


def format_sources_markdown(sources: list[dict[str, Any]], limit: int = 20) -> str:
    """Append a human-readable source list to the final plan."""
    if not sources:
        return "\n\n## 参考来源\n\n暂无工具返回的可引用来源，以上未标注来源的信息请出行前二次确认。"
    lines = ["\n\n## 参考来源"]
    for item in sources[:limit]:
        title = item.get("title") or item.get("category") or "来源"
        url = item.get("url")
        suffix = f"：{url}" if url else f"（{item.get('source') or item.get('source_type') or 'tool'}）"
        lines.append(f"- [{item.get('id')}] {title}{suffix}")
    return "\n".join(lines)


def build_quality_report(state: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic quality report for the generated trip plan."""
    sources = attach_evidence_ids(state.get("evidence_sources", []))
    request = str(state.get("user_request", ""))
    source_types = {item.get("source_type") for item in sources}
    agents_with_evidence = {item.get("agent") for item in sources}
    tools = {item.get("tool") for item in sources}

    checks = {
        "has_web_sources": bool([item for item in sources if item.get("url")]),
        "has_official_sources": bool([item for item in sources if item.get("is_official")]),
        "has_route_api": "route_api" in source_types,
        "has_weather_api": "weather_api" in source_types,
        "has_route_plan": bool(state.get("route_plan")),
        "has_transport_plan": bool(state.get("transport_options")),
        "has_food_plan": bool(state.get("food_recommendations")),
        "has_stay_plan": bool(state.get("accommodation_options")),
        "activity_required": any(word in request for word in ACTIVITY_WORDS),
        "activity_checked": any(
            item.get("category") == "event_candidate" or "activity" in str(item.get("tool", "")).lower() or "event" in str(item.get("tool", "")).lower()
            for item in sources
        ),
    }

    warnings = []
    if not checks["has_web_sources"]:
        warnings.append("没有可引用的网页来源，景点、活动、餐饮和住宿建议需要出行前二次确认。")
    if not checks["has_official_sources"]:
        warnings.append("未看到官网/官方公告/主办方/权威票务来源，活动时间、开放规则和票务信息必须二次确认。")
    if "自驾" in request or "开车" in request:
        if not checks["has_route_api"]:
            warnings.append("用户要求自驾，但未看到地图路线 API 证据。")
    if not checks["has_weather_api"]:
        warnings.append("未看到天气 API 证据，天气建议可能不完整。")
    if checks["activity_required"] and not checks["activity_checked"]:
        warnings.append("用户提到活动/赛事/展会等，但未看到活动档期查询证据。")

    # 核心检查按可执行性加权，避免只因没有 URL 就全盘失败。
    weighted = [
        checks["has_route_plan"],
        checks["has_transport_plan"],
        checks["has_food_plan"],
        checks["has_stay_plan"],
        checks["has_web_sources"],
        checks["has_route_api"] if ("自驾" in request or "开车" in request) else True,
        checks["has_weather_api"],
        checks["activity_checked"] if checks["activity_required"] else True,
    ]
    score = round(sum(1 for item in weighted if item) / len(weighted) * 100)

    return {
        "score": score,
        "source_count": len(sources),
        "agents_with_evidence": sorted(item for item in agents_with_evidence if item),
        "tools_used": sorted(item for item in tools if item),
        "checks": checks,
        "warnings": warnings,
    }


def format_quality_markdown(report: dict[str, Any]) -> str:
    """Format quality report for the final plan."""
    if not report:
        return ""
    lines = [
        "\n\n## 方案质量检查",
        f"- 证据覆盖评分：{report.get('score', 0)}/100",
        f"- 已收集来源：{report.get('source_count', 0)} 条",
    ]
    warnings = report.get("warnings") or []
    if warnings:
        lines.append("- 需要注意：" + "；".join(warnings))
    else:
        lines.append("- 检查结果：关键查询链路已覆盖。")
    return "\n".join(lines)
