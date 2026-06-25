"""
交通 MCP 服务器 — 机票(Amadeus) + 火车票(12306模拟)

知识点：
  - FastMCP 多工具组织
  - 外部 API 集成 (Amadeus SDK)
  - 内置样例数据和通用估算
  - 错误处理与降级策略
"""

import json
import os
import random
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("transport-server")

# ============================================
# 内置样例数据
# ============================================
SAMPLE_FLIGHTS = {
    ("北京", "成都"): [
        {"airline": "中国国航", "flight": "CA4101", "departure": "08:00", "arrival": "10:30",
         "duration": "2h30m", "price": 1280, "class": "经济舱", "seats_left": 5},
        {"airline": "四川航空", "flight": "3U8001", "departure": "10:30", "arrival": "13:00",
         "duration": "2h30m", "price": 980, "class": "经济舱", "seats_left": 12},
        {"airline": "东方航空", "flight": "MU5405", "departure": "14:00", "arrival": "16:20",
         "duration": "2h20m", "price": 1150, "class": "经济舱", "seats_left": 3},
        {"airline": "南方航空", "flight": "CZ6101", "departure": "18:30", "arrival": "21:00",
         "duration": "2h30m", "price": 850, "class": "经济舱", "seats_left": 20},
    ],
    ("北京", "上海"): [
        {"airline": "中国国航", "flight": "CA1501", "departure": "07:00", "arrival": "09:15",
         "duration": "2h15m", "price": 960, "class": "经济舱", "seats_left": 8},
        {"airline": "东方航空", "flight": "MU5101", "departure": "09:30", "arrival": "11:45",
         "duration": "2h15m", "price": 880, "class": "经济舱", "seats_left": 15},
        {"airline": "春秋航空", "flight": "9C8801", "departure": "13:00", "arrival": "15:20",
         "duration": "2h20m", "price": 520, "class": "经济舱", "seats_left": 30},
    ],
    ("上海", "三亚"): [
        {"airline": "南方航空", "flight": "CZ6782", "departure": "08:30", "arrival": "12:00",
         "duration": "3h30m", "price": 1580, "class": "经济舱", "seats_left": 6},
        {"airline": "春秋航空", "flight": "9C8779", "departure": "15:00", "arrival": "18:30",
         "duration": "3h30m", "price": 980, "class": "经济舱", "seats_left": 25},
    ],
    ("北京", "三亚"): [
        {"airline": "中国国航", "flight": "CA1369", "departure": "07:30", "arrival": "11:30",
         "duration": "4h00m", "price": 2100, "class": "经济舱", "seats_left": 4},
        {"airline": "海南航空", "flight": "HU7279", "departure": "12:00", "arrival": "16:00",
         "duration": "4h00m", "price": 1850, "class": "经济舱", "seats_left": 10},
    ],
}

SAMPLE_TRAINS = {
    ("北京", "成都"): [
        {"train": "G89", "type": "高铁", "departure": "06:36", "arrival": "14:59",
         "duration": "8h23m", "price_二等座": 778, "price_一等座": 1245, "seats_left": 150},
        {"train": "G307", "type": "高铁", "departure": "10:05", "arrival": "20:43",
         "duration": "10h38m", "price_二等座": 778, "price_一等座": 1245, "seats_left": 200},
        {"train": "K817", "type": "快速", "departure": "18:00", "arrival": "次日12:30",
         "duration": "18h30m", "price_硬座": 240, "price_硬卧": 436, "seats_left": 50},
    ],
    ("北京", "上海"): [
        {"train": "G1", "type": "高铁", "departure": "09:00", "arrival": "13:28",
         "duration": "4h28m", "price_二等座": 553, "price_一等座": 933, "seats_left": 300},
        {"train": "G7", "type": "高铁", "departure": "10:00", "arrival": "14:28",
         "duration": "4h28m", "price_二等座": 553, "price_一等座": 933, "seats_left": 280},
        {"train": "D321", "type": "动车", "departure": "19:52", "arrival": "次日07:08",
         "duration": "11h16m", "price_二等座": 410, "price_软卧": 680, "seats_left": 100},
    ],
    ("上海", "杭州"): [
        {"train": "G7301", "type": "高铁", "departure": "07:00", "arrival": "07:45",
         "duration": "45m", "price_二等座": 73, "price_一等座": 117, "seats_left": 500},
        {"train": "G7543", "type": "高铁", "departure": "08:30", "arrival": "09:20",
         "duration": "50m", "price_二等座": 73, "price_一等座": 117, "seats_left": 450},
    ],
    ("成都", "重庆"): [
        {"train": "G8601", "type": "高铁", "departure": "07:00", "arrival": "08:15",
         "duration": "1h15m", "price_二等座": 154, "price_一等座": 246, "seats_left": 600},
        {"train": "C6003", "type": "城际", "departure": "09:00", "arrival": "10:10",
         "duration": "1h10m", "price_二等座": 154, "price_一等座": 246, "seats_left": 550},
    ],
}


def _reverse_key(key: tuple) -> tuple:
    """反转路线方向"""
    return (key[1], key[0])


def _reverse_flights(flights: list[dict], key: tuple) -> list[dict]:
    """反转航班方向（简单模拟）"""
    result = []
    for f in flights:
        rf = f.copy()
        rf["price"] = int(f["price"] * random.uniform(0.9, 1.1))  # 价格微调
        result.append(rf)
    return result


def _reverse_trains(trains: list[dict], key: tuple) -> list[dict]:
    """反转火车方向"""
    return [t.copy() for t in trains]


def _parse_waypoints(waypoints: str) -> list[str]:
    """把用户输入的途经点字符串整理成列表。"""
    if not waypoints:
        return []
    for sep in ["→", "->", "，", ",", ";", "；", "|"]:
        waypoints = waypoints.replace(sep, "\n")
    return [item.strip() for item in waypoints.splitlines() if item.strip()]


def _geocode_amap(place: str) -> dict | None:
    """Use AMap geocoding if AMAP_API_KEY is configured."""
    import httpx

    api_key = os.getenv("AMAP_API_KEY", "")
    if not api_key:
        # 高德对国内地址识别更好，所以优先使用；
        # 没配置 Key 时返回 None，让上层尝试 OSM。
        return None
    resp = httpx.get(
        "https://restapi.amap.com/v3/geocode/geo",
        params={"key": api_key, "address": place},
        timeout=12,
    )
    data = resp.json()
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return None
    first = geocodes[0]
    lon, lat = first["location"].split(",", 1)
    return {
        "name": first.get("formatted_address") or place,
        "lon": float(lon),
        "lat": float(lat),
        "location": first["location"],
        "source": "amap",
    }


def _amap_driving_route(origin: str, destination: str, waypoints: list[str]) -> dict | None:
    """Plan a real driving route through AMap when configured."""
    import httpx

    api_key = os.getenv("AMAP_API_KEY", "")
    if not api_key:
        return None

    # 高德 direction API 需要经纬度字符串，所以先 geocode。
    origin_geo = _geocode_amap(origin)
    destination_geo = _geocode_amap(destination)
    waypoint_geos = [_geocode_amap(item) for item in waypoints]
    waypoint_geos = [item for item in waypoint_geos if item]
    if not origin_geo or not destination_geo:
        return None

    params = {
        "key": api_key,
        "origin": origin_geo["location"],
        "destination": destination_geo["location"],
        "strategy": 10,
        "extensions": "base",
    }
    if waypoint_geos:
        params["waypoints"] = ";".join(item["location"] for item in waypoint_geos)

    resp = httpx.get("https://restapi.amap.com/v3/direction/driving", params=params, timeout=15)
    data = resp.json()
    paths = data.get("route", {}).get("paths", [])
    if not paths:
        return None
    path = paths[0]
    distance_km = round(float(path.get("distance", 0)) / 1000, 1)
    duration_min = round(float(path.get("duration", 0)) / 60)
    return {
        "source": "amap",
        "origin": origin_geo,
        "destination": destination_geo,
        "waypoints": waypoint_geos,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "tolls_yuan": float(path.get("tolls", 0) or 0),
        "traffic_lights": int(path.get("traffic_lights", 0) or 0),
        "strategy": "高德地图驾车路线，优先速度和路况综合",
    }


def _geocode_osm(place: str) -> dict | None:
    """Use OpenStreetMap Nominatim as a no-key geocoder fallback."""
    import httpx

    resp = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1, "accept-language": "zh-CN"},
        headers={"User-Agent": "TravelPlanner/1.0"},
        timeout=12,
    )
    data = resp.json()
    if not data:
        return None
    first = data[0]
    return {
        "name": first.get("display_name") or place,
        "lon": float(first["lon"]),
        "lat": float(first["lat"]),
        "source": "openstreetmap",
    }


def _osrm_driving_route(origin: str, destination: str, waypoints: list[str]) -> dict | None:
    """Plan a real route through OSRM public service when possible."""
    import httpx

    # OSM/OSRM 是无 Key 兜底方案，但国内道路和中文地址覆盖可能不如高德。
    points = [origin] + waypoints + [destination]
    geos = [_geocode_osm(item) for item in points]
    if any(item is None for item in geos):
        return None
    coords = ";".join(f"{item['lon']},{item['lat']}" for item in geos)
    resp = httpx.get(
        f"https://router.project-osrm.org/route/v1/driving/{coords}",
        params={"overview": "false", "alternatives": "false", "steps": "false"},
        timeout=15,
    )
    data = resp.json()
    routes = data.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    return {
        "source": "osrm",
        "origin": geos[0],
        "destination": geos[-1],
        "waypoints": geos[1:-1],
        "distance_km": round(route.get("distance", 0) / 1000, 1),
        "duration_min": round(route.get("duration", 0) / 60),
        "strategy": "OSRM 公开驾车路线；国内道路覆盖和实时路况可能不完整",
    }


# ============================================
# MCP 工具定义
# ============================================

@mcp.tool()
def search_flights(origin: str, destination: str, date: str = "") -> str:
    """搜索两个城市之间的航班信息。

    Args:
        origin: 出发城市（中文）
        destination: 到达城市（中文）
        date: 出发日期（YYYY-MM-DD格式，可选）
    """
    key = (origin, destination)
    reverse_key = _reverse_key(key)

    # 当前没有接入正式航班 API，已知热门路线使用内置样例；
    # 未知路线生成通用数据，仅用于展示工具结构，Agent prompt 会要求不要编造班次。
    if key in SAMPLE_FLIGHTS:
        flights = SAMPLE_FLIGHTS[key]
    elif reverse_key in SAMPLE_FLIGHTS:
        flights = _reverse_flights(SAMPLE_FLIGHTS[reverse_key], reverse_key)
    else:
        # 生成通用航班数据
        airlines = ["中国国航", "东方航空", "南方航空", "海南航空", "春秋航空", "四川航空"]
        flights = []
        base_price = random.randint(500, 2000)
        for i in range(random.randint(3, 6)):
            dep_hour = random.randint(6, 21)
            dur_hours = random.randint(1, 5)
            flights.append({
                "airline": random.choice(airlines),
                "flight": f"{'CA' if i % 2 == 0 else 'MU'}{random.randint(1000, 9999)}",
                "departure": f"{dep_hour:02d}:{random.choice(['00', '15', '30', '45'])}",
                "arrival": f"{(dep_hour + dur_hours) % 24:02d}:{random.choice(['00', '15', '30', '45'])}",
                "duration": f"{dur_hours}h{random.choice(['00', '15', '30', '45'])}m",
                "price": base_price + random.randint(-200, 500),
                "class": "经济舱",
                "seats_left": random.randint(2, 50),
            })

    result = {
        "route": f"{origin} → {destination}",
        "date": date or "待定",
        "flights": flights,
        "cheapest": min(flights, key=lambda x: x["price"]) if flights else None,
        "recommendation": "建议提前14-21天预订以获得最佳价格",
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def search_trains(origin: str, destination: str, date: str = "") -> str:
    """搜索两个城市之间的火车/高铁信息。

    Args:
        origin: 出发城市（中文）
        destination: 到达城市（中文）
        date: 出发日期（YYYY-MM-DD格式，可选）
    """
    key = (origin, destination)
    reverse_key = _reverse_key(key)

    if key in SAMPLE_TRAINS:
        trains = SAMPLE_TRAINS[key]
    elif reverse_key in SAMPLE_TRAINS:
        trains = _reverse_trains(SAMPLE_TRAINS[reverse_key], reverse_key)
    else:
        # 生成通用火车数据
        train_types = [("G", "高铁"), ("D", "动车"), ("K", "快速")]
        trains = []
        for prefix, ttype in random.sample(train_types, min(3, len(train_types))):
            dep_hour = random.randint(6, 20)
            dur_minutes = random.randint(30, 600)
            h, m = divmod(dur_minutes, 60)
            price_base = dur_minutes * (3 if prefix == "G" else 2 if prefix == "D" else 1)
            trains.append({
                "train": f"{prefix}{random.randint(1, 999)}",
                "type": ttype,
                "departure": f"{dep_hour:02d}:{random.choice(['00', '30'])}",
                "arrival": f"{(dep_hour + h) % 24:02d}:{m:02d}",
                "duration": f"{h}h{m}m" if h > 0 else f"{m}m",
                "price_二等座": price_base,
                "price_一等座": int(price_base * 1.6),
                "seats_left": random.randint(50, 500),
            })

    result = {
        "route": f"{origin} → {destination}",
        "date": date or "待定",
        "trains": trains,
        "cheapest": min(trains, key=lambda x: x.get("price_二等座", x.get("price_硬座", 999))) if trains else None,
        "tip": "高铁比飞机更准时，3小时以内高铁优于飞机（算上机场时间）",
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def compare_transport(origin: str, destination: str, date: str = "") -> str:
    """对比同一航线的飞机和火车方案，给出综合推荐。

    Args:
        origin: 出发城市
        destination: 到达城市
        date: 出发日期
    """
    # 内部调用已有工具，统一形成“飞机 vs 火车”的对比结构。
    flights_raw = json.loads(search_flights(origin, destination, date))
    trains_raw = json.loads(search_trains(origin, destination, date))

    cheapest_flight = flights_raw.get("cheapest", {})
    cheapest_train = trains_raw.get("cheapest", {})

    flight_price = cheapest_flight.get("price", float("inf")) if cheapest_flight else float("inf")
    train_price = cheapest_train.get("price_二等座", cheapest_train.get("price_硬座", float("inf"))) if cheapest_train else float("inf")

    if train_price < flight_price * 0.6:
        recommendation = "🚄 推荐火车：价格优势明显，性价比更高"
    elif flight_price < train_price:
        recommendation = "✈️ 推荐飞机：价格更低或接近，节省时间"
    else:
        recommendation = "⏱️ 短途推荐火车，长途推荐飞机（综合考虑时间和价格）"

    return json.dumps({
        "route": f"{origin} → {destination}",
        "flights_summary": f"最低 ¥{flight_price}" if flight_price != float("inf") else "无航班",
        "trains_summary": f"最低 ¥{train_price}" if train_price != float("inf") else "无火车",
        "recommendation": recommendation,
        "details": {"flights": flights_raw, "trains": trains_raw},
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def plan_driving_route(origin: str, destination: str, waypoints: str = "", departure_time: str = "") -> str:
    """查询真实地图驾车路线，不使用直线距离估算。

    Args:
        origin: 起点，可以是城市、区县、景点或详细地址
        destination: 终点，可以是城市、区县、景点或详细地址
        waypoints: 途经点，多个地点可用逗号、分号或箭头分隔
        departure_time: 出发时间线索，可为空
    """
    waypoint_list = _parse_waypoints(waypoints)
    try:
        # 优先高德，失败再尝试 OSRM。两者都失败时，不用直线距离替代。
        route = _amap_driving_route(origin, destination, waypoint_list)
        if not route:
            route = _osrm_driving_route(origin, destination, waypoint_list)
    except Exception as exc:
        route = {"error": str(exc)}

    if not route:
        route = {
            "error": "无法通过外部地图服务获取路线，请配置 AMAP_API_KEY 或检查网络。",
            "source": "unavailable",
        }

    route.update({
        "query": {
            "origin": origin,
            "destination": destination,
            "waypoints": waypoint_list,
            "departure_time": departure_time,
        },
        "note": "路线结果来自外部地图/路线服务；自驾出发前仍应以实时导航路况为准。",
    })
    return json.dumps(route, ensure_ascii=False, indent=2)


@mcp.tool()
def get_transport_cities() -> str:
    """获取交通查询支持的热门路线。"""
    routes = set()
    for (o, d) in list(SAMPLE_FLIGHTS.keys()) + list(SAMPLE_TRAINS.keys()):
        routes.add(f"{o}→{d}")
    return json.dumps({"hot_routes": sorted(routes)}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
