"""
日期计算工具

知识点：@tool 装饰器、参数描述
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from langchain_core.tools import tool


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
# 全项目统一使用中国时区，避免服务器时区不同导致“今天/明天”错位。


def today_date() -> datetime:
    """Return today's date in the app's local timezone."""
    return datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def today_local_date():
    """Return today's calendar date in the app's local timezone."""
    return datetime.now(LOCAL_TZ).date()


def parse_local_date(value: str):
    """Parse YYYY-MM-DD or ISO datetime strings into a local calendar date."""
    text = str(value).strip()
    if not text:
        raise ValueError("日期不能为空")

    try:
        # 大多数工具只关心日历日期，先按 YYYY-MM-DD 快速解析。
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        pass

    # 支持 2026-06-15T00:00:00+08:00 这类带时区字符串。
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(LOCAL_TZ)
    return parsed.date()


@tool
def calculate_duration(start_date: str, end_date: str) -> int:
    """计算两个日期之间的天数差。

    Args:
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
    """
    start = parse_local_date(start_date)
    end = parse_local_date(end_date)
    return (end - start).days


@tool
def get_date_range(start_date: str, days: int) -> list[str]:
    """从指定日期开始，生成连续N天的日期列表。

    Args:
        start_date: 起始日期，格式 YYYY-MM-DD
        days: 天数
    """
    start = parse_local_date(start_date)
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


@tool
def get_today() -> str:
    """获取今天的日期，格式 YYYY-MM-DD。"""
    return today_date().strftime("%Y-%m-%d")


@tool
def get_current_datetime() -> str:
    """获取当前真实日期时间，格式 YYYY-MM-DD HH:MM:SS，时区 Asia/Shanghai。"""
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


@tool
def is_weekend(date: str) -> bool:
    """判断指定日期是否为周末。

    Args:
        date: 日期，格式 YYYY-MM-DD
    """
    d = parse_local_date(date)
    return d.weekday() >= 5


@tool
def days_until(target_date: str) -> int:
    """计算距离目标日期还有多少天。

    Args:
        target_date: 目标日期，格式 YYYY-MM-DD
    """
    target = parse_local_date(target_date)
    today = today_local_date()
    # 过去日期返回 0，避免 UI 显示负数“还有 -2 天”。
    return max(0, (target - today).days)
