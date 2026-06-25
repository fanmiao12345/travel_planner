"""
天气 MCP 服务器 — Open-Meteo API（免费，无需API Key）

知识点：
  - FastMCP 框架构建 MCP Server
  - @mcp.tool() 装饰器定义工具
  - @mcp.resource() 暴露数据资源
  - 异步 HTTP 请求 (httpx)
  - Open-Meteo 真实天气查询
"""

import json
from mcp.server.fastmcp import FastMCP

# 创建 MCP 服务器实例
mcp = FastMCP("weather-server")

# ============================================
# 城市坐标映射（用于真实 API）
# ============================================
CITY_GEO = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "成都": (30.5728, 104.0668),
    "杭州": (30.2741, 120.1551),
    "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398),
    "重庆": (29.4316, 106.9123),
    "南京": (32.0603, 118.7969),
    "三亚": (18.2528, 109.5120),
    "大理": (25.6065, 100.2676),
    "丽江": (26.8721, 100.2299),
    "厦门": (24.4798, 118.0894),
    "昆明": (25.0389, 102.7183),
    "桂林": (25.2736, 110.2900),
    "拉萨": (29.6500, 91.1000),
    "青岛": (36.0671, 120.3826),
    "长沙": (28.2282, 112.9388),
}


def _fetch_real_weather(city: str, days: int) -> dict:
    """调用 Open-Meteo 真实 API 获取天气数据"""
    import httpx

    # 先把中文城市/区县名解析成经纬度，再调用天气预报接口。
    geo = _resolve_city_geo(city)
    if not geo:
        return {"error": f"无法定位城市: {city}，请尝试输入更完整的城市名，例如“云南大理”或“福建泉州”"}

    lat, lon, resolved_name = geo

    with httpx.Client(timeout=15) as client:
        # 获取天气预报
        resp = client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,apparent_temperature,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "timezone": "Asia/Shanghai",
                "forecast_days": min(days, 16),
            },
        )
        data = resp.json()

    # Open-Meteo 返回 WMO weather_code，这里映射为中文描述。
    WMO_CODES = {
        0: "晴", 1: "大部晴", 2: "多云", 3: "阴天",
        45: "雾", 48: "雾凇", 51: "小毛毛雨", 53: "中毛毛雨",
        61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 73: "中雪",
        80: "阵雨", 81: "中阵雨", 95: "雷暴", 96: "雷暴+冰雹",
    }

    current = data.get("current", {})
    daily = data.get("daily", {})

    forecast = []
    dates = daily.get("time", [])
    for i in range(min(len(dates), days)):
        wmo = daily.get("weather_code", [0])[i] if i < len(daily.get("weather_code", [])) else 0
        forecast.append({
            "date": dates[i],
            "temp_max": daily.get("temperature_2m_max", [0])[i],
            "temp_min": daily.get("temperature_2m_min", [0])[i],
            "condition": WMO_CODES.get(wmo, "未知"),
            "precipitation": daily.get("precipitation_probability_max", [0])[i],
        })

    wmo_now = current.get("weather_code", 0)
    return {
        "city": resolved_name,
        "requested_city": city,
        "current": {
            "temp": current.get("temperature_2m"),
            "feels_like": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "condition": WMO_CODES.get(wmo_now, "未知"),
        },
        "forecast": forecast,
    }


def _fetch_real_air_quality(city: str) -> dict:
    """调用 Open-Meteo 空气质量 API"""
    import httpx

    # 空气质量 API 与天气 API 分开，所以也需要先解析经纬度。
    geo = _resolve_city_geo(city)
    if not geo:
        return {"error": f"无法定位城市: {city}"}

    lat, lon, resolved_name = geo

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "pm10,pm2_5,us_aqi",
                "timezone": "Asia/Shanghai",
            },
        )
        data = resp.json()

    current = data.get("current", {})
    aqi = current.get("us_aqi", 0)

    if aqi <= 50:
        level = "优"
    elif aqi <= 100:
        level = "良"
    elif aqi <= 150:
        level = "轻度污染"
    else:
        level = "中重度污染"

    return {
        "city": resolved_name,
        "requested_city": city,
        "aqi": aqi,
        "level": level,
        "pm25": current.get("pm2_5"),
        "pm10": current.get("pm10"),
    }


def _resolve_city_geo(city: str) -> tuple[float, float, str] | None:
    """Resolve any Chinese destination through static data first, then Open-Meteo geocoding."""
    import httpx

    # 常用城市先查本地坐标表，速度更快，也避免外部 geocoding 波动。
    normalized = city.strip().replace("市", "")
    if normalized in CITY_GEO:
        lat, lon = CITY_GEO[normalized]
        return lat, lon, normalized
    if city in CITY_GEO:
        lat, lon = CITY_GEO[city]
        return lat, lon, city

    try:
        # 不在本地表里的区县/小城市，再请求 Open-Meteo 地理编码服务。
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": city,
                    "count": 1,
                    "language": "zh",
                    "format": "json",
                },
            )
            data = resp.json()
    except Exception:
        return None

    results = data.get("results") or []
    if not results:
        return None
    first = results[0]
    name = first.get("name") or city
    admin = first.get("admin1")
    resolved_name = f"{admin}{name}" if admin and admin not in name else name
    return first["latitude"], first["longitude"], resolved_name


# ============================================
# MCP 工具定义
# ============================================

@mcp.tool()
def get_weather_forecast(city: str, days: int = 3) -> str:
    """获取指定城市的天气预报。

    Args:
        city: 城市名称（中文，如"北京"、"成都"）
        days: 预报天数（1-16天）
    """
    try:
        # 工具层捕获异常并返回 error 字段，避免整个 graph 因网络错误中断。
        result = _fetch_real_weather(city, days)
    except Exception as exc:
        result = {"city": city, "error": f"天气服务查询失败: {exc}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_air_quality(city: str) -> str:
    """获取指定城市的空气质量信息。

    Args:
        city: 城市名称（中文）
    """
    try:
        # 与天气预报一致：失败时返回结构化错误，由 Agent 展示给用户。
        result = _fetch_real_air_quality(city)
    except Exception as exc:
        result = {"city": city, "error": f"空气质量服务查询失败: {exc}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_supported_cities() -> str:
    """获取天气查询支持的城市列表。"""
    cities = list(CITY_GEO.keys())
    return json.dumps({
        "supported_cities": cities,
        "total": len(cities),
        "note": "支持通过 Open-Meteo 地理编码查询更多全国城市；列表仅为内置热门城市。",
    }, ensure_ascii=False)


# ============================================
# MCP 资源定义
# ============================================

@mcp.resource("weather://cities")
def list_weather_cities() -> str:
    """获取支持天气查询的城市列表（资源形式）。"""
    return json.dumps(list(CITY_GEO.keys()), ensure_ascii=False)


# ============================================
# 启动入口
# ============================================
if __name__ == "__main__":
    mcp.run()
