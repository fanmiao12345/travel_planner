"""
预算计算工具

知识点：@tool 装饰器、复杂业务逻辑封装
"""

from langchain_core.tools import tool


@tool
def calculate_daily_budget(total_budget: float, days: int, people: int = 1) -> dict:
    """根据总预算计算每日人均预算，并给出分配建议。

    Args:
        total_budget: 总预算（元）
        days: 出游天数
        people: 出游人数
    """
    # 先算“团队每天总预算”，再算“每人每天预算”。
    daily_total = total_budget / days
    daily_per_person = daily_total / people

    # 经验分配比例：只是预算初稿，不替代真实报价。
    # 后续交通/住宿/餐饮 Agent 给出价格后，预算 Agent 会再汇总。
    allocation = {
        "交通": round(daily_total * 0.30, 2),
        "住宿": round(daily_total * 0.30, 2),
        "餐饮": round(daily_total * 0.25, 2),
        "门票_活动": round(daily_total * 0.10, 2),
        "其他": round(daily_total * 0.05, 2),
    }

    return {
        "total_budget": total_budget,
        "days": days,
        "people": people,
        "daily_total": round(daily_total, 2),
        "daily_budget": round(daily_per_person, 2),
        "daily_per_person": round(daily_per_person, 2),
        "suggested_allocation": allocation,
    }


@tool
def compare_options(options: list[dict], budget: float) -> dict:
    """对比多个方案，按性价比排序。

    Args:
        options: 方案列表，每个方案包含 name, price, rating 字段
        budget: 预算上限
    """
    # 过滤超预算方案
    within_budget = [o for o in options if o.get("price", 0) <= budget]

    if not within_budget:
        return {"recommendation": None, "message": "所有方案都超出预算", "all_options": options}

    # 按性价比排序（rating/price）。
    # max(price, 1) 防止异常数据 price=0 导致除零。
    for opt in within_budget:
        price = opt.get("price", 1)
        rating = opt.get("rating", 3)
        opt["value_score"] = round(rating / max(price, 1) * 100, 2)

    sorted_options = sorted(within_budget, key=lambda x: x["value_score"], reverse=True)

    return {
        "recommendation": sorted_options[0],
        "all_ranked": sorted_options,
        "within_budget_count": len(within_budget),
        "total_count": len(options),
    }


@tool
def estimate_saving_tips(destination: str, days: int, budget: float) -> list[str]:
    """根据目的地和预算，提供省钱建议。

    Args:
        destination: 目的地城市
        days: 出游天数
        budget: 总预算
    """
    tips = []

    # 通用省钱建议先给基础项，再按预算紧张程度追加更强的节省策略。
    tips.append("🎫 提前预订机票/火车票通常更便宜（提前14-21天最佳）")
    tips.append("🏨 选择民宿或青旅比酒店节省30-50%")
    tips.append("🍜 品尝当地小吃街比餐厅更实惠且地道")

    if budget / days < 300:
        tips.append("💡 预算较紧，建议选择公共交通而非打车")
        tips.append("💡 可以选择免费景点为主，付费景点提前网购优惠票")
        tips.append("💡 超市采购早餐和零食，减少外出就餐次数")

    if budget / days < 500:
        tips.append("💡 避开旅游旺季出行，价格通常低20-40%")
        tips.append("💡 关注各平台的酒店优惠券和满减活动")

    # 季节性建议
    tips.append("📅 工作日出行比周末便宜，特别是住宿价格")
    tips.append("📱 多平台比价：携程、去哪儿、美团、飞猪价格可能不同")

    return tips
