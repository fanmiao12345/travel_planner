"""
MCP 服务器测试

知识点：单元测试、外部服务测试桩、工具数据验证
"""

import pytest
import json
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWeatherServer:
    """天气 MCP 服务器测试"""

    def test_get_weather_forecast(self, monkeypatch):
        from mcp_servers import weather_server
        from mcp_servers.weather_server import get_weather_forecast

        # 单元测试不依赖真实 Open-Meteo 网络，用测试桩固定返回。
        monkeypatch.setattr(weather_server, "_fetch_real_weather", lambda city, days: {
            "city": city,
            "current": {"condition": "晴", "temp": 22},
            "forecast": [{"date": "2026-06-13", "condition": "晴"}],
        })

        result = get_weather_forecast("北京", 3)
        data = json.loads(result)
        assert data["city"] == "北京"
        assert "current" in data
        assert "forecast" in data
        assert len(data["forecast"]) <= 3

    def test_get_weather_unknown_city(self, monkeypatch):
        from mcp_servers import weather_server
        from mcp_servers.weather_server import get_weather_forecast

        monkeypatch.setattr(weather_server, "_fetch_real_weather", lambda city, days: {
            "city": city,
            "error": f"无法定位城市: {city}",
        })

        result = get_weather_forecast("未知城市", 3)
        data = json.loads(result)
        assert "city" in data
        assert "error" in data

    def test_get_air_quality(self, monkeypatch):
        from mcp_servers import weather_server
        from mcp_servers.weather_server import get_air_quality

        monkeypatch.setattr(weather_server, "_fetch_real_air_quality", lambda city: {
            "city": city,
            "aqi": 45,
            "level": "优",
        })

        result = get_air_quality("北京")
        data = json.loads(result)
        assert "aqi" in data
        assert "level" in data

    def test_get_supported_cities(self):
        from mcp_servers.weather_server import get_supported_cities
        result = get_supported_cities()
        data = json.loads(result)
        assert "supported_cities" in data
        assert "北京" in data["supported_cities"]


class TestTransportServer:
    """交通 MCP 服务器测试"""

    def test_search_flights(self):
        from mcp_servers.transport_server import search_flights
        result = search_flights("北京", "成都", "2025-07-01")
        data = json.loads(result)
        assert data["route"] == "北京 → 成都"
        assert "flights" in data
        assert len(data["flights"]) > 0

    def test_search_trains(self):
        from mcp_servers.transport_server import search_trains
        result = search_trains("北京", "上海", "2025-07-01")
        data = json.loads(result)
        assert data["route"] == "北京 → 上海"
        assert "trains" in data

    def test_compare_transport(self):
        from mcp_servers.transport_server import compare_transport
        result = compare_transport("北京", "成都", "2025-07-01")
        data = json.loads(result)
        assert "recommendation" in data
        assert "flights_summary" in data
        assert "trains_summary" in data

    def test_unknown_route(self):
        from mcp_servers.transport_server import search_flights
        result = search_flights("小城A", "小城B", "2025-07-01")
        data = json.loads(result)
        # 未接入真实数据时不能生成假航班。
        assert "flights" in data
        assert data["source"] == "unavailable"
        assert data["flights"] == []

    def test_plan_driving_route_uses_external_route_result(self, monkeypatch):
        from mcp_servers import transport_server
        from mcp_servers.transport_server import plan_driving_route

        # 地图 API 在测试里也用测试桩替代，验证 plan_driving_route 会采用外部路线结果。
        monkeypatch.setattr(transport_server, "_amap_driving_route", lambda origin, destination, waypoints: {
            "source": "amap",
            "distance_km": 286.5,
            "duration_min": 241,
            "origin": {"name": origin},
            "destination": {"name": destination},
            "waypoints": [],
        })

        result = plan_driving_route("北京", "蔚县", "暖泉古镇", "明天上午")
        data = json.loads(result)
        assert data["source"] == "amap"
        assert data["distance_km"] == 286.5
        assert data["query"]["waypoints"] == ["暖泉古镇"]


class TestAccommodationServer:
    """住宿餐饮 MCP 服务器测试"""

    def test_search_hotels(self):
        from mcp_servers.accommodation_server import search_hotels
        result = search_hotels("成都", budget=500)
        data = json.loads(result)
        assert data["city"] == "成都"
        assert all(h["price"] <= 500 for h in data["hotels"])

    def test_search_hotels_with_breakfast(self):
        from mcp_servers.accommodation_server import search_hotels
        result = search_hotels("北京", need_breakfast=True)
        data = json.loads(result)
        assert all(h.get("breakfast", False) for h in data["hotels"])

    def test_search_restaurants(self):
        from mcp_servers.accommodation_server import search_restaurants
        result = search_restaurants("成都", cuisine="火锅")
        data = json.loads(result)
        assert data["city"] == "成都"
        assert all("火锅" in r.get("cuisine", "") or "火锅" in r.get("specialty", "")
                    for r in data["restaurants"])

    def test_get_food_guide(self):
        from mcp_servers.accommodation_server import get_food_guide
        result = get_food_guide("北京")
        data = json.loads(result)
        assert "must_try" in data
        assert "烤鸭" in str(data["must_try"])


class TestSearchServer:
    """搜索 MCP 服务器测试"""

    def test_web_search(self, monkeypatch):
        async def run():
            from mcp_servers import search_server
            from mcp_servers.search_server import web_search

            # 搜索测试固定 Tavily 返回，避免网络和第三方 API Key 影响 CI。
            async def fake_tavily(query: str):
                return {
                    "query": query,
                    "source": "tavily",
                    "results": [{"title": "成都攻略", "url": "https://example.com", "snippet": "成都三日游"}],
                }

            monkeypatch.setattr(search_server, "_tavily_search", fake_tavily)

            result = await web_search("成都旅游攻略")
            data = json.loads(result)
            assert "results" in data
            assert len(data["results"]) > 0

        asyncio.run(run())

    def test_search_travel_guide(self, monkeypatch):
        async def run():
            from mcp_servers import search_server
            from mcp_servers.search_server import search_travel_guide

            async def fake_web_search(query: str):
                return json.dumps({"query": query, "source": "tavily", "results": []}, ensure_ascii=False)

            monkeypatch.setattr(search_server, "web_search", fake_web_search)

            result = await search_travel_guide("成都", 3, "经典")
            data = json.loads(result)
            assert "query" in data
            assert "成都" in data["query"]

        asyncio.run(run())

    def test_search_trending_places(self, monkeypatch):
        async def run():
            from mcp_servers import search_server
            from mcp_servers.search_server import search_trending_places

            async def fake_web_search(query: str):
                return json.dumps({
                    "query": query,
                    "source": "tavily",
                    "results": [{"title": "泉州热门街区", "url": "https://example.com", "snippet": "近期热门打卡点"}],
                }, ensure_ascii=False)

            monkeypatch.setattr(search_server, "web_search", fake_web_search)

            result = await search_trending_places("泉州", 3)
            data = json.loads(result)
            assert data["destination"] == "泉州"
            assert "places" in data
            assert data["source"] in {"tavily", "duckduckgo", "fallback", "unavailable", "search"}
            assert "note" in data

        asyncio.run(run())

    def test_search_event_schedule_extracts_dates(self, monkeypatch):
        async def run():
            from mcp_servers import search_server
            from mcp_servers.search_server import search_event_schedule

            # 活动档期工具的关键能力是从摘要中提取日期候选。
            async def fake_web_search(query: str):
                return json.dumps({
                    "query": query,
                    "source": "tavily",
                    "results": [{
                        "title": "蔚县打树花活动公告",
                        "url": "https://example.com/event",
                        "snippet": "活动将于2026年7月18日-7月20日在暖泉古镇举行。",
                    }],
                }, ensure_ascii=False)

            monkeypatch.setattr(search_server, "web_search", fake_web_search)

            result = await search_event_schedule("蔚县", "打树花", "暑假")
            data = json.loads(result)
            assert data["event_name"] == "打树花"
            assert data["has_confirmed_date_candidate"] is True
            assert data["candidates"][0]["date_candidates"]

        asyncio.run(run())

    def test_search_visa_info(self):
        async def run():
            from mcp_servers.search_server import search_visa_info
            result = await search_visa_info("成都")
            data = json.loads(result)
            assert data["visa_required"] is False

        asyncio.run(run())


class TestTools:
    """辅助工具测试"""

    def test_calculate_duration(self):
        from tools.date_utils import calculate_duration
        result = calculate_duration.invoke({"start_date": "2025-07-01", "end_date": "2025-07-04"})
        assert result == 3

    def test_calculate_distance(self):
        from tools.geo_utils import calculate_distance
        result = calculate_distance.invoke({"city1": "北京", "city2": "上海"})
        assert "distance_km" in result
        assert result["distance_km"] > 0

    def test_calculate_daily_budget(self):
        from tools.budget_calculator import calculate_daily_budget
        result = calculate_daily_budget.invoke({"total_budget": 5000, "days": 5, "people": 2})
        assert result["daily_total"] == 1000.0
        assert result["daily_budget"] == 500.0
        assert result["daily_per_person"] == 500.0

    def test_days_until_uses_same_date_type(self):
        from tools.date_utils import days_until, get_today
        today = get_today.invoke({})
        assert days_until.invoke({"target_date": today}) == 0

    def test_days_until_accepts_offset_datetime(self):
        from tools.date_utils import days_until, get_today
        today = get_today.invoke({})
        assert days_until.invoke({"target_date": f"{today}T00:00:00+08:00"}) == 0

    def test_evidence_extraction_from_search_result(self):
        from tools.evidence import attach_evidence_ids, extract_evidence_from_value

        raw = json.dumps({
            "source": "tavily",
            "results": [{
                "title": "蔚县暖泉古镇攻略",
                "url": "https://example.com/yuxian",
                "snippet": "暖泉古镇适合夜间看打树花。",
            }],
        }, ensure_ascii=False)

        sources = attach_evidence_ids(extract_evidence_from_value(raw, "route_plan", "web_search"))
        assert sources[0]["id"] == "S1"
        assert sources[0]["url"] == "https://example.com/yuxian"
        assert sources[0]["source_type"] == "web_search"

    def test_quality_report_warns_when_self_drive_route_not_verified(self):
        from tools.evidence import build_quality_report

        report = build_quality_report({
            "user_request": "明天从北京到蔚县，11个人，自驾去，玩三天",
            "route_plan": {"content": "行程"},
            "transport_options": ["交通建议"],
            "food_recommendations": ["美食建议"],
            "accommodation_options": ["住宿建议"],
            "evidence_sources": [{
                "agent": "route_plan",
                "tool": "web_search",
                "source_type": "web_search",
                "title": "蔚县攻略",
                "url": "https://example.com",
            }],
        })

        assert report["checks"]["has_web_sources"] is True
        assert report["checks"]["has_route_api"] is False
        assert any("自驾" in warning for warning in report["warnings"])


class TestRequestParsing:
    """用户需求解析测试"""

    def test_parse_county_self_drive_request(self, monkeypatch):
        async def run():
            from config import config
            from agents.supervisor import parse_request_node
            from agents.state import create_initial_state

            class FailingLLM:
                async def ainvoke(self, messages):
                    raise RuntimeError("no model in unit test")

            # 让 LLM 故意失败，验证本地解析兜底能处理中文自驾需求。
            monkeypatch.setattr(config, "get_llm", lambda: FailingLLM())

            state = create_initial_state("明天从北京到张家口的蔚县，11个人，自驾去，玩三天")
            result = await parse_request_node(state)

            assert result["origin"] == "北京"
            assert result["destination"] == "蔚县"
            assert result["people_count"] == 11
            assert result["dates"]["days"] == 3

        asyncio.run(run())


class TestHarness:
    """统一 harness 测试"""

    def test_harness_runs_workflow_to_review(self):
        async def run():
            from harness import TravelPlannerHarness

            class FakeGraph:
                # harness 测试不跑真实 LangGraph，只模拟 astream 的 update 协议。
                async def astream(self, graph_input, config=None, stream_mode=None):
                    yield {"parse_request": {
                        "destination": "西安",
                        "dates": {"days": 3},
                    }}
                    yield {"route_planner": {
                        "route_plan": {"content": "西安3日游"},
                    }}
                    yield {"summarize": {
                        "final_plan": {"content": "最终方案"},
                        "current_phase": "reviewing",
                    }}
                    yield {"__interrupt__": {"type": "plan_review"}}

            harness = TravelPlannerHarness(thread_id="pytest-harness-session", graph=FakeGraph())
            result = await harness.run_request("西安3日游，一个人，预算3000元，喜欢历史")

            assert result.final_state["destination"] == "西安"
            assert result.final_state["dates"]["days"] == 3
            assert result.final_state["final_plan"]
            assert "route_planner" in result.completed_nodes
            assert result.awaiting_review is True

        asyncio.run(run())

    def test_harness_resume_confirm_finishes(self):
        async def run():
            from harness import TravelPlannerHarness

            class FakeGraph:
                async def astream(self, graph_input, config=None, stream_mode=None):
                    yield {"human_review": {
                        "is_approved": True,
                        "current_phase": "done",
                    }}

            harness = TravelPlannerHarness(
                thread_id="pytest-harness-resume-session",
                graph=FakeGraph(),
                initial_state={"final_plan": {"content": "最终方案"}, "current_phase": "reviewing"},
            )
            result = await harness.run_resume("确认")

            assert result.interrupted is False
            assert result.awaiting_review is False
            assert result.final_state["is_approved"] is True
            assert result.final_state["current_phase"] == "done"

        asyncio.run(run())


class TestConfig:
    """配置测试"""

    def test_local_model_without_api_key(self, monkeypatch):
        from config import AppConfig

        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
        monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        app_config = AppConfig()
        assert app_config.llm.provider == "ollama"
        assert app_config.llm.model == "qwen2.5:7b"


class TestMetricsCollector:
    """评估指标收集测试"""

    def test_snapshot_does_not_clear_task_metrics(self):
        from backend.evaluation.collector import MetricsCollector

        collector = MetricsCollector()
        collector.start_task("task-test")
        collector.record_agent_spawn("task-test")
        collector.record_step("task-test")

        snapshot = collector.snapshot_task("task-test", accuracy=0.5)
        final = collector.finish_task("task-test", accuracy=0.8)

        assert snapshot.agent_count == 1
        assert final.agent_count == 1
        assert final.accuracy == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
