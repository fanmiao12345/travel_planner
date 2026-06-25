"""
地理距离计算工具

知识点：数学计算工具、Haversine公式
"""

import math
from langchain_core.tools import tool

# 常用城市经纬度数据库（中国主要城市）
CITY_COORDS = {
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
    "长沙": (28.2282, 112.9388),
    "青岛": (36.0671, 120.3826),
    "大理": (25.6065, 100.2676),
    "丽江": (26.8721, 100.2299),
    "三亚": (18.2528, 109.5120),
    "厦门": (24.4798, 118.0894),
    "昆明": (25.0389, 102.7183),
    "桂林": (25.2736, 110.2900),
    "拉萨": (29.6500, 91.1000),
    "乌鲁木齐": (43.8256, 87.6168),
}


@tool
def get_city_coordinates(city: str) -> dict:
    """获取城市的经纬度坐标。

    Args:
        city: 城市名称（中文）
    """
    # 这是本地静态坐标表，适合快速估算和测试；
    # 真实自驾路线不要用它替代地图路线工具。
    if city in CITY_COORDS:
        lat, lon = CITY_COORDS[city]
        return {"city": city, "latitude": lat, "longitude": lon}
    return {"city": city, "latitude": None, "longitude": None, "error": "未找到该城市坐标"}


@tool
def calculate_distance(city1: str, city2: str) -> dict:
    """计算两个城市之间的直线距离（公里）。

    使用 Haversine 公式计算地球表面两点间的最短距离。

    Args:
        city1: 城市1名称
        city2: 城市2名称
    """
    # 缺坐标时直接返回错误，让 Agent 明确说明无法估算。
    if city1 not in CITY_COORDS or city2 not in CITY_COORDS:
        return {"error": f"未找到城市坐标: {city1 if city1 not in CITY_COORDS else city2}"}

    lat1, lon1 = CITY_COORDS[city1]
    lat2, lon2 = CITY_COORDS[city2]

    # Haversine 公式计算球面直线距离，不考虑道路绕行、限速和拥堵。
    R = 6371  # 地球半径（公里）
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c

    return {
        "from": city1,
        "to": city2,
        "distance_km": round(distance, 1),
        "estimated_drive_hours": round(distance / 80, 1),  # 假设平均80km/h
        "estimated_flight_hours": round(distance / 800, 1),  # 假设平均800km/h
    }
