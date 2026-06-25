"""
住宿餐饮 MCP 服务器 — 酒店/餐饮结构化工具

知识点：
  - FastMCP 多领域工具整合
  - 复杂参数过滤
  - 结构化数据返回
"""

import json
import random
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("accommodation-server")

# ============================================
# 内置酒店样例数据
# ============================================
SAMPLE_HOTELS = {
    "北京": [
        {"name": "北京王府井希尔顿酒店", "star": 5, "price": 880, "rating": 4.6, "location": "王府井",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["商务", "市中心"]},
        {"name": "北京国贸大酒店", "star": 5, "price": 1200, "rating": 4.7, "location": "国贸CBD",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["豪华", "商务"]},
        {"name": "如家商旅酒店(天安门店)", "star": 3, "price": 320, "rating": 4.2, "location": "前门",
         "breakfast": False, "wifi": True, "pool": False, "tags": ["经济", "近景点"]},
        {"name": "北京青旅·背包客之家", "star": 0, "price": 80, "rating": 4.0, "location": "南锣鼓巷",
         "breakfast": False, "wifi": True, "pool": False, "tags": ["青旅", "社交"]},
        {"name": "全季酒店(中关村店)", "star": 3, "price": 420, "rating": 4.3, "location": "中关村",
         "breakfast": True, "wifi": True, "pool": False, "tags": ["舒适", "连锁"]},
    ],
    "成都": [
        {"name": "成都博舍酒店", "star": 5, "price": 1100, "rating": 4.8, "location": "太古里",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["设计酒店", "市中心"]},
        {"name": "成都钓鱼台精品酒店", "star": 5, "price": 1500, "rating": 4.7, "location": "宽窄巷子",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["豪华", "近景点"]},
        {"name": "成都懒骨头青旅", "star": 0, "price": 65, "rating": 4.3, "location": "春熙路",
         "breakfast": False, "wifi": True, "pool": False, "tags": ["青旅", "热闹"]},
        {"name": "亚朵酒店(春熙路店)", "star": 3, "price": 380, "rating": 4.5, "location": "春熙路",
         "breakfast": True, "wifi": True, "pool": False, "tags": ["舒适", "连锁"]},
    ],
    "上海": [
        {"name": "上海和平饭店", "star": 5, "price": 2200, "rating": 4.8, "location": "外滩",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["历史", "地标"]},
        {"name": "上海外滩W酒店", "star": 5, "price": 1800, "rating": 4.6, "location": "外滩",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["时尚", "夜景"]},
        {"name": "汉庭酒店(南京路店)", "star": 2, "price": 280, "rating": 4.0, "location": "南京路",
         "breakfast": False, "wifi": True, "pool": False, "tags": ["经济", "市中心"]},
    ],
    "三亚": [
        {"name": "三亚亚特兰蒂斯酒店", "star": 5, "price": 2500, "rating": 4.7, "location": "海棠湾",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["亲子", "水上乐园"]},
        {"name": "三亚万豪度假酒店", "star": 5, "price": 1200, "rating": 4.5, "location": "亚龙湾",
         "breakfast": True, "wifi": True, "pool": True, "tags": ["海景", "度假"]},
        {"name": "三亚大东海花园客栈", "star": 0, "price": 180, "rating": 4.1, "location": "大东海",
         "breakfast": False, "wifi": True, "pool": False, "tags": ["民宿", "海景"]},
    ],
}

# ============================================
# 内置餐饮样例数据
# ============================================
SAMPLE_RESTAURANTS = {
    "北京": [
        {"name": "全聚德(前门店)", "cuisine": "北京菜", "avg_price": 180, "rating": 4.2,
         "specialty": "烤鸭", "location": "前门", "budget_level": "中"},
        {"name": "海底捞(王府井店)", "cuisine": "火锅", "avg_price": 130, "rating": 4.5,
         "specialty": "火锅", "location": "王府井", "budget_level": "中"},
        {"name": "护国寺小吃", "cuisine": "北京小吃", "avg_price": 30, "rating": 4.0,
         "specialty": "豆汁、焦圈、驴打滚", "location": "护国寺", "budget_level": "低"},
        {"name": "四季民福(故宫店)", "cuisine": "北京菜", "avg_price": 150, "rating": 4.6,
         "specialty": "烤鸭", "location": "故宫附近", "budget_level": "中"},
        {"name": "便宜坊(鲜鱼口店)", "cuisine": "北京菜", "avg_price": 120, "rating": 4.3,
         "specialty": "焖炉烤鸭", "location": "鲜鱼口", "budget_level": "中"},
    ],
    "成都": [
        {"name": "小龙坎火锅(春熙路店)", "cuisine": "火锅", "avg_price": 100, "rating": 4.4,
         "specialty": "麻辣火锅", "location": "春熙路", "budget_level": "中"},
        {"name": "陈麻婆豆腐(总店)", "cuisine": "川菜", "avg_price": 60, "rating": 4.3,
         "specialty": "麻婆豆腐", "location": "西玉龙街", "budget_level": "低"},
        {"name": "龙抄手(春熙路店)", "cuisine": "成都小吃", "avg_price": 35, "rating": 4.1,
         "specialty": "抄手、担担面", "location": "春熙路", "budget_level": "低"},
        {"name": "大龙燚火锅", "cuisine": "火锅", "avg_price": 110, "rating": 4.5,
         "specialty": "牛油火锅", "location": "玉林路", "budget_level": "中"},
        {"name": "玉林串串香", "cuisine": "串串", "avg_price": 50, "rating": 4.2,
         "specialty": "串串香", "location": "玉林路", "budget_level": "低"},
    ],
    "上海": [
        {"name": "南翔馒头店(豫园)", "cuisine": "上海小吃", "avg_price": 50, "rating": 4.3,
         "specialty": "小笼包", "location": "豫园", "budget_level": "低"},
        {"name": "鼎泰丰(上海IFC)", "cuisine": "台湾菜", "avg_price": 150, "rating": 4.6,
         "specialty": "小笼包", "location": "陆家嘴", "budget_level": "中"},
        {"name": "老正兴菜馆", "cuisine": "本帮菜", "avg_price": 100, "rating": 4.4,
         "specialty": "红烧肉、油爆虾", "location": "福州路", "budget_level": "中"},
    ],
    "三亚": [
        {"name": "林姐香味海鲜(第一市场)", "cuisine": "海鲜", "avg_price": 150, "rating": 4.5,
         "specialty": "椒盐皮皮虾、清蒸石斑", "location": "第一市场", "budget_level": "中"},
        {"name": "小胡子海鲜加工", "cuisine": "海鲜", "avg_price": 100, "rating": 4.3,
         "specialty": "海鲜加工", "location": "第一市场", "budget_level": "低"},
        {"name": "椰小鸡", "cuisine": "海南菜", "avg_price": 80, "rating": 4.2,
         "specialty": "椰子鸡火锅", "location": "三亚湾", "budget_level": "低"},
    ],
}


def _filter_by_budget(items: list[dict], max_price: float, price_key: str) -> list[dict]:
    """按预算过滤"""
    return [item for item in items if item.get(price_key, 0) <= max_price]


def _generate_hotels(city: str, budget: float) -> list[dict]:
    """为未知城市生成通用酒店数据"""
    # 这里是没有接入真实酒店 API 时的结构化示例。
    # 专业 Agent 会另外调用搜索工具查目的地住宿资料，避免只依赖这些样例。
    templates = [
        {"name": f"{city}国际大酒店", "star": 5, "price": 900, "rating": 4.5, "tags": ["豪华"]},
        {"name": f"{city}商务酒店", "star": 3, "price": 350, "rating": 4.2, "tags": ["舒适"]},
        {"name": f"{city}快捷酒店", "star": 2, "price": 180, "rating": 3.8, "tags": ["经济"]},
        {"name": f"{city}青年旅舍", "star": 0, "price": 60, "rating": 4.0, "tags": ["青旅"]},
    ]
    for t in templates:
        t["breakfast"] = t["star"] >= 3
        t["wifi"] = True
        t["pool"] = t["star"] >= 5
        t["location"] = "市中心"
    return templates


def _generate_restaurants(city: str) -> list[dict]:
    """为未知城市生成通用餐饮数据"""
    # 与酒店类似，这里只是给 UI 一个稳定的数据形状。
    # 真正的小众目的地美食应由 food_advisor 的搜索工具补充。
    return [
        {"name": f"{city}老字号餐厅", "cuisine": "地方菜", "avg_price": 80, "rating": 4.3,
         "specialty": "地方特色菜", "location": "市中心", "budget_level": "中"},
        {"name": f"{city}小吃街", "cuisine": "小吃", "avg_price": 30, "rating": 4.0,
         "specialty": "各类小吃", "location": "老城区", "budget_level": "低"},
        {"name": f"{city}网红餐厅", "cuisine": "创意菜", "avg_price": 120, "rating": 4.5,
         "specialty": "创意融合菜", "location": "商业区", "budget_level": "中"},
    ]


# ============================================
# MCP 工具定义
# ============================================

@mcp.tool()
def search_hotels(city: str, checkin: str = "", checkout: str = "", budget: float = 9999,
                  star: int = 0, need_breakfast: bool = False) -> str:
    """搜索指定城市的酒店信息。

    Args:
        city: 城市名称（中文）
        checkin: 入住日期（YYYY-MM-DD，可选）
        checkout: 退房日期（YYYY-MM-DD，可选）
        budget: 每晚预算上限（元）
        star: 最低星级（0=不限, 3=三星, 5=五星）
        need_breakfast: 是否需要含早餐
    """
    # 已知城市先用内置样例，未知城市生成同结构数据，保证下游 UI 可展示。
    hotels = SAMPLE_HOTELS.get(city, _generate_hotels(city, budget))

    # 过滤
    filtered = [h for h in hotels if h["price"] <= budget]
    if star > 0:
        filtered = [h for h in filtered if h["star"] >= star]
    if need_breakfast:
        filtered = [h for h in filtered if h.get("breakfast", False)]

    # 按评分排序
    filtered.sort(key=lambda x: x["rating"], reverse=True)

    # 计算总价（如果有入住天数）。
    # 这个计算只基于输入日期，不代表平台实时价格。
    if checkin and checkout:
        from datetime import datetime
        try:
            days = (datetime.strptime(checkout, "%Y-%m-%d") - datetime.strptime(checkin, "%Y-%m-%d")).days
            for h in filtered:
                h["total_price"] = h["price"] * days
                h["nights"] = days
        except ValueError:
            pass

    result = {
        "city": city,
        "checkin": checkin or "待定",
        "checkout": checkout or "待定",
        "budget": budget,
        "total_found": len(filtered),
        "hotels": filtered,
        "tip": "💡 预算紧张？选择青旅或民宿可节省50%以上" if budget < 300 else "💡 提前预订通常有早鸟优惠",
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def search_restaurants(city: str, cuisine: str = "", budget_per_meal: float = 9999,
                       count: int = 5) -> str:
    """搜索指定城市的餐饮推荐。

    Args:
        city: 城市名称（中文）
        cuisine: 菜系偏好（如"火锅"、"海鲜"、"小吃"，可选）
        budget_per_meal: 每餐人均预算上限（元）
        count: 返回数量
    """
    # 餐厅工具返回结构化候选；真实热门餐厅应结合搜索结果二次确认。
    restaurants = SAMPLE_RESTAURANTS.get(city, _generate_restaurants(city))

    # 过滤
    filtered = [r for r in restaurants if r["avg_price"] <= budget_per_meal]
    if cuisine:
        filtered = [r for r in restaurants if cuisine in r.get("cuisine", "") or cuisine in r.get("specialty", "")]

    # 按评分排序
    filtered.sort(key=lambda x: x["rating"], reverse=True)
    filtered = filtered[:count]

    result = {
        "city": city,
        "cuisine_filter": cuisine or "不限",
        "budget_per_meal": budget_per_meal,
        "total_found": len(filtered),
        "restaurants": filtered,
        "saving_tip": f"🍜 在{city}，当地小吃街和居民区餐馆通常是性价比最高的选择",
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_food_guide(city: str) -> str:
    """获取城市的美食攻略概览。

    Args:
        city: 城市名称（中文）
    """
    guides = {
        "北京": {
            "must_try": ["烤鸭", "豆汁焦圈", "炸酱面", "卤煮火烧", "铜锅涮肉"],
            "food_streets": ["簋街", "南锣鼓巷", "护国寺小吃街", "牛街"],
            "tips": ["烤鸭推荐四季民福或大董，全聚德游客较多", "豆汁需要适应，先少量尝试"],
            "budget_daily": "人均80-150元/天可吃好",
        },
        "成都": {
            "must_try": ["火锅", "串串香", "担担面", "麻婆豆腐", "龙抄手", "兔头"],
            "food_streets": ["建设路小吃街", "玉林路", "锦里", "宽窄巷子"],
            "tips": ["微辣已经是中辣水平，慎选辣度", "火锅推荐本地人去的店"],
            "budget_daily": "人均60-120元/天可吃好",
        },
        "上海": {
            "must_try": ["小笼包", "生煎", "本帮红烧肉", "蟹壳黄", "排骨年糕"],
            "food_streets": ["城隍庙", "吴江路", "云南南路"],
            "tips": ["南翔馒头店排队很长，建议工作日去", "本帮菜偏甜"],
            "budget_daily": "人均100-180元/天可吃好",
        },
        "三亚": {
            "must_try": ["海鲜", "椰子鸡", "清补凉", "抱罗粉", "芒果"],
            "food_streets": ["第一市场", "火车头万人海鲜广场"],
            "tips": ["海鲜去第一市场自己买再找加工店", "椰子鸡是海南特色，值得一试"],
            "budget_daily": "人均100-200元/天可吃好",
        },
    }

    guide = guides.get(city, {
        "must_try": ["当地特色菜", "小吃街美食"],
        "food_streets": ["市中心美食街"],
        "tips": ["多看大众点评评分选择"],
        "budget_daily": "人均80-150元/天可吃好",
    })
    guide["city"] = city
    return json.dumps(guide, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
