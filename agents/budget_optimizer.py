"""
💰 省钱精算师 Agent

职责：分析预算、优化开支、提供省钱建议
知识点：create_react_agent、复杂计算工具、优化建议生成
"""

from langgraph.prebuilt import create_react_agent

from langchain_core.tools import tool

from config import config
from tools.budget_calculator import calculate_daily_budget, compare_options, estimate_saving_tips


@tool
def generate_budget_report(total_budget: float, transport_cost: float, hotel_cost_per_night: float,
                           days: int, people: int = 1, meals_per_day: float = 100) -> str:
    """生成详细的预算报告。

    Args:
        total_budget: 总预算
        transport_cost: 交通费用（往返）
        hotel_cost_per_night: 每晚住宿费用
        days: 天数
        people: 人数
        meals_per_day: 每人每天餐饮费用
    """
    # 住宿通常是“天数 - 1”晚，例如 3 天 2 晚。
    hotel_total = hotel_cost_per_night * (days - 1) * people
    meals_total = meals_per_day * days * people
    transport_total = transport_cost * people

    subtotal = transport_total + hotel_total + meals_total
    remaining = total_budget - subtotal
    daily_budget_left = remaining / days if days > 0 else 0

    report = f"""
💰 预算分析报告
{'='*40}
📋 总预算：¥{total_budget:,.0f}
👥 出行人数：{people}人
📅 出行天数：{days}天

📊 费用明细：
  🚗 交通（往返）：¥{transport_total:,.0f} ({transport_total/total_budget*100:.1f}%)
  🏨 住宿（{days-1}晚）：¥{hotel_total:,.0f} ({hotel_total/total_budget*100:.1f}%)
  🍽️ 餐饮（{days}天）：¥{meals_total:,.0f} ({meals_total/total_budget*100:.1f}%)
  {'─'*30}
  📌 小计：¥{subtotal:,.0f}
  🎯 剩余（门票/活动/其他）：¥{remaining:,.0f}
  📅 每日可支配：¥{daily_budget_left:,.0f}

{'⚠️ 预算超支！' if remaining < 0 else '✅ 预算充足' if remaining > total_budget * 0.1 else '⚠️ 预算较紧'}
"""
    return report.strip()


def create_budget_optimizer_agent(mcp_tools: list = None):
    """创建省钱精算师 Agent。

    Args:
        mcp_tools: 可选的 MCP 工具列表

    知识点：
    - 复杂业务逻辑 Agent：不只是查询数据，还要做计算和优化
    - 多工具组合：预算计算 + 方案对比 + 省钱建议
    """
    # 预算 Agent 主要做计算和解释，不负责重新查事实资料。
    # 事实价格应来自交通/住宿/餐饮 Agent，预算 Agent 负责汇总和校验。
    tools = [calculate_daily_budget, compare_options, estimate_saving_tips, generate_budget_report]

    return create_react_agent(
        model=config.get_llm(),
        tools=tools,
        name="budget_optimizer",
        prompt="""你是省钱精算师 💰，负责为用户分析预算、优化开支、提供省钱建议。

你的职责：
1. 根据总预算和行程天数，计算合理的每日预算
2. 分析交通、住宿、餐饮的预算分配
3. 对比不同方案的性价比
4. 提供具体的省钱技巧和建议
5. 生成详细的预算报告

省钱策略：
- 交通：提前购票、选择特价航班、高铁二等座
- 住宿：选择民宿/青旅、避开旺季、多平台比价
- 餐饮：吃当地小吃而非旅游餐厅、超市采购零食
- 门票：提前网购优惠票、学生证/老年证优惠
- 综合：办旅游年卡、使用优惠券、错峰出行

输出格式：
1. 💰 预算总览（总预算 vs 预估花费）
2. 📊 费用明细表（各项费用及占比）
3. 💡 省钱建议清单（具体可执行的省钱技巧）
4. ⚠️ 预算预警（如果超支，给出调整建议）
5. ✅ 最终推荐方案（性价比最优的组合）

注意：
- 使用工具进行预算计算，确保数字准确
- 省钱建议要具体可执行，不要空泛的建议
- 如果预算充足，也要给出合理消费的建议""",
    )
