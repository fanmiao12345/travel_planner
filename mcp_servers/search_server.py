"""
通用搜索 MCP 服务器 — Tavily(主) + DuckDuckGo(备)

知识点：
  - 降级策略（主API失败自动切换备用）
  - 搜索结果结构化
  - 旅行场景特化搜索
"""

import json
import os
import re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("search-server")

# ============================================
# 无外部搜索服务时的结构化降级提示
# ============================================
FALLBACK_SEARCH_RESULTS = {
    "成都旅游攻略": {
        "query": "成都旅游攻略",
        "results": [
            {"title": "2025成都三日游最佳攻略", "url": "https://travel.example.com/chengdu-3days",
             "snippet": "第一天：武侯祠→锦里→宽窄巷子；第二天：都江堰→青城山；第三天：大熊猫基地→春熙路"},
            {"title": "成都必去景点TOP10", "url": "https://travel.example.com/chengdu-top10",
             "snippet": "大熊猫繁育研究基地、武侯祠、锦里古街、宽窄巷子、都江堰、青城山、杜甫草堂、春熙路、太古里、文殊院"},
            {"title": "成都美食不完全指南", "url": "https://food.example.com/chengdu",
             "snippet": "火锅推荐小龙坎、大龙燚；串串推荐玉林串串香；小吃推荐龙抄手、陈麻婆豆腐"},
        ],
    },
    "三亚自由行": {
        "query": "三亚自由行",
        "results": [
            {"title": "三亚5天4晚自由行攻略", "url": "https://travel.example.com/sanya-5days",
             "snippet": "Day1三亚湾日落，Day2蜈支洲岛，Day3南山寺+天涯海角，Day4亚龙湾，Day5免税店购物"},
            {"title": "三亚住宿选哪里？四大海湾对比", "url": "https://hotel.example.com/sanya",
             "snippet": "三亚湾性价比高，亚龙湾水质最好，海棠湾最豪华，大东海最便利"},
        ],
    },
    "省钱旅行技巧": {
        "query": "省钱旅行技巧",
        "results": [
            {"title": "2025年旅行省钱的20个技巧", "url": "https://budget.example.com/tips",
             "snippet": "提前订票、错峰出行、使用比价平台、选择民宿、当地市场买特产、办旅游年卡"},
            {"title": "穷游er的终极省钱指南", "url": "https://qyer.example.com/budget",
             "snippet": "机票比价用天巡，住宿用Airbnb，吃饭找当地人推荐的小店"},
        ],
    },
}

SEARCH_UNAVAILABLE_NOTICE = "当前没有可用搜索结果；请配置 Tavily API Key 或检查网络后重试。"

DATE_PATTERNS = [
    r"20\d{2}[年/-]\s*\d{1,2}[月/-]\s*\d{1,2}\s*[日号]?",
    r"20\d{2}\.\d{1,2}\.\d{1,2}",
    r"\d{1,2}\s*月\s*\d{1,2}\s*[日号]",
    r"\d{1,2}[/-]\d{1,2}",
    r"每年\s*\d{1,2}\s*月",
    r"\d{1,2}\s*月\s*(?:上旬|中旬|下旬|底)",
]


def _extract_date_candidates(text: str) -> list[str]:
    """Extract visible date-like strings from search snippets."""
    found = []
    for pattern in DATE_PATTERNS:
        for match in re.findall(pattern, text or ""):
            value = re.sub(r"\s+", "", match)
            if value and value not in found:
                found.append(value)
    return found[:8]


async def _tavily_search(query: str) -> dict:
    """使用 Tavily API 搜索"""
    import httpx

    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        # 没有 Tavily Key 时不抛异常，交给上层继续尝试 DuckDuckGo。
        return {"error": "Tavily API key not configured"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                },
                timeout=15,
            )
            data = resp.json()
            results = []
            for r in data.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:200],
                })
            return {"query": query, "results": results, "source": "tavily"}
        except Exception as e:
            return {"error": str(e)}


async def _duckduckgo_search(query: str) -> dict:
    """使用 DuckDuckGo 搜索（免费，无需 API key）"""
    import httpx

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1},
                headers={"User-Agent": "TravelPlanner/1.0"},
                timeout=15,
            )
            data = resp.json()

            results = []
            # Abstract
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", "")[:200],
                })
            # Related Topics
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")[:200],
                    })

            return {"query": query, "results": results, "source": "duckduckgo"}
        except Exception as e:
            return {"error": str(e)}


def _fallback_search(query: str) -> dict:
    """搜索服务不可用时的结构化降级结果。"""
    # 尝试精确匹配
    if query in FALLBACK_SEARCH_RESULTS:
        result = FALLBACK_SEARCH_RESULTS[query].copy()
        result["source"] = "fallback"
        result["note"] = SEARCH_UNAVAILABLE_NOTICE
        return result

    # 模糊匹配
    for key, value in FALLBACK_SEARCH_RESULTS.items():
        if key in query or query in key:
            result = value.copy()
            result["source"] = "fallback"
            result["note"] = SEARCH_UNAVAILABLE_NOTICE
            return result

    # 通用结果保持空列表，明确告诉 Agent “没有查到”，
    # 避免模型把示例文本误当真实搜索结果。
    return {
        "query": query,
        "results": [],
        "source": "unavailable",
        "note": SEARCH_UNAVAILABLE_NOTICE,
    }


# ============================================
# MCP 工具定义
# ============================================

@mcp.tool()
async def web_search(query: str) -> str:
    """通用网络搜索。可用于搜索旅游攻略、景点信息、旅行贴士等。

    Args:
        query: 搜索关键词
    """
    # 降级策略：Tavily → DuckDuckGo → 结构化不可用提示。
    # 只有前两个属于外部搜索；fallback 只是告诉上层搜索不可用。
    result = await _tavily_search(query)
    if "error" not in result and result.get("results"):
        return json.dumps(result, ensure_ascii=False, indent=2)

    result = await _duckduckgo_search(query)
    if "error" not in result and result.get("results"):
        return json.dumps(result, ensure_ascii=False, indent=2)

    return json.dumps(_fallback_search(query), ensure_ascii=False, indent=2)


@mcp.tool()
async def search_travel_guide(destination: str, days: int = 3, style: str = "经典") -> str:
    """搜索目的地旅游攻略。

    Args:
        destination: 目的地城市
        days: 计划游玩天数
        style: 旅行风格（经典/文艺/冒险/亲子/穷游）
    """
    query = f"{destination}{days}天{style}旅游攻略"
    return await web_search(query)


@mcp.tool()
async def search_trending_places(destination: str, count: int = 5) -> str:
    """搜索目的地最近热门、网红打卡、新晋出圈地点。

    Args:
        destination: 目的地城市或地区
        count: 返回数量
    """
    query = f"{destination} 最近很火 网红打卡 新晋热门 景点 旅行攻略"
    raw = await web_search(query)
    data = json.loads(raw)
    return json.dumps({
        "destination": destination,
        "query": query,
        "source": data.get("source", "search"),
        "places": [
            {
                "name": item.get("title", "")[:40],
                "reason": item.get("snippet", ""),
                "url": item.get("url", ""),
            }
            for item in data.get("results", [])[:count]
        ],
        "note": "结果来自实时搜索摘要，热门程度会随时间变化，建议出行前再次确认开放时间和预约规则。",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def search_event_schedule(destination: str, event_name: str, date_hint: str = "") -> str:
    """搜索目的地活动/节庆/赛事/展会的真实举办时间、地点和票务信息。

    Args:
        destination: 目的地城市、区县或景区
        event_name: 活动名称，例如音乐节、马拉松、庙会、展览、演唱会
        date_hint: 用户提到的日期线索，可为空
    """
    # 活动查询会多路搜索：普通时间查询、什么时候举办、官方公告。
    # 这样可以覆盖“活动名 + 地点”不完整时的情况。
    base_query = f"{destination} {event_name} 举办时间 地点 门票 官方"
    if date_hint:
        base_query = f"{base_query} {date_hint}"
    queries = [
        base_query,
        f"{destination} {event_name} 活动时间 什么时候 举办",
        f"{destination} {event_name} 官方 公告 日程",
    ]

    candidates = []
    sources = []
    for query in queries:
        raw = await web_search(query)
        data = json.loads(raw)
        sources.append(data.get("source", "search"))
        for item in data.get("results", []):
            # search API 通常只返回摘要，不保证结构化日期。
            # 这里先从 title/snippet 中提取可见日期候选，再交给模型判断。
            text = " ".join([item.get("title", ""), item.get("snippet", "")])
            candidates.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "date_candidates": _extract_date_candidates(text),
            })

    deduped = []
    seen = set()
    for item in candidates:
        key = (item.get("title"), item.get("url"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    has_date = any(item.get("date_candidates") for item in deduped)
    return json.dumps({
        "destination": destination,
        "event_name": event_name,
        "date_hint": date_hint,
        "queries": queries,
        "sources": sorted(set(sources)),
        "candidates": deduped[:8],
        "has_confirmed_date_candidate": has_date,
        "note": (
            "请优先使用官方/主办方/票务平台来源；如果候选结果没有日期，不要从当前时间顺推，必须提示用户活动时间未确认。"
        ),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def search_visa_info(destination: str, nationality: str = "中国") -> str:
    """查询签证和出入境信息。

    Args:
        destination: 目的地（国家或城市）
        nationality: 国籍
    """
    # 简化的签证信息（实际应调用搜索API）
    visa_info = {
        "国内": {"visa_required": False, "tip": "国内旅行无需签证，携带身份证即可"},
        "港澳": {"visa_required": True, "tip": "需要港澳通行证+签注，提前在出入境管理局办理"},
        "台湾": {"visa_required": True, "tip": "需要台湾通行证+入台证"},
    }

    # 判断是国内还是国外
    domestic_cities = ["北京", "上海", "成都", "三亚", "广州", "深圳", "杭州", "西安", "重庆", "南京"]
    if destination in domestic_cities:
        info = visa_info["国内"]
    elif "港" in destination or "澳" in destination:
        info = visa_info["港澳"]
    else:
        info = {"visa_required": "未知", "tip": f"请查询{destination}的最新签证政策"}

    info["destination"] = destination
    info["nationality"] = nationality
    return json.dumps(info, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
