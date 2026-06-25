"""
进程内异步事件总线

用于 Agent 生命周期事件 → 评估系统、日志等消费者的解耦。
支持 fnmatch 通配符主题匹配。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, Awaitable, Callable


@dataclass
class Event:
    """事件数据结构。"""
    topic: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """进程内异步发布/订阅事件总线。

    用法::

        bus = EventBus()
        bus.subscribe("agent.*", my_handler)
        await bus.publish(Event(topic="agent.completed", data={"name": "weather"}))
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """订阅匹配 topic_pattern 的事件（支持 fnmatch 通配符）。"""
        self._handlers.setdefault(topic_pattern, []).append(handler)

    def unsubscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """取消订阅。"""
        handlers = self._handlers.get(topic_pattern, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        """发布事件，所有匹配的 handler 并发执行。"""
        tasks: list[asyncio.Task] = []
        for pattern, handlers in self._handlers.items():
            if fnmatch(event.topic, pattern):
                for handler in handlers:
                    tasks.append(asyncio.create_task(handler(event)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
