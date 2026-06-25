"""
Backend Harness 适配层

包装原有 TravelPlannerHarness，集成:
- MetricsCollector 指标收集
- TrajectoryRecorder 轨迹记录
- EventBus 事件发布
- MemoryManager 记忆注入
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import AsyncGenerator, Any

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 导入原有 harness
from harness.travel_harness import (
    HarnessEvent as _HarnessEvent,
    HarnessResult as _HarnessResult,
    TravelPlannerHarness as _BaseHarness,
)


class HarnessEvent:
    """增强的 Harness 事件。"""
    def __init__(self, event: _HarnessEvent) -> None:
        self._event = event

    @property
    def event_type(self) -> str:
        return self._event.event_type

    @property
    def node_name(self) -> str:
        return self._event.node_name

    @property
    def message(self) -> str:
        return self._event.message

    @property
    def elapsed(self) -> float:
        return self._event.elapsed

    @property
    def completed_nodes(self) -> list[str]:
        return self._event.completed_nodes

    @property
    def update(self) -> dict:
        return self._event.update

    @property
    def final_state(self) -> dict:
        return self._event.final_state


class TravelPlannerHarness:
    """增强的旅行规划 Harness。

    在原有 Harness 基础上集成指标收集和轨迹记录。
    """

    def __init__(
        self,
        thread_id: str | None = None,
        graph: Any = None,
        initial_state: dict[str, Any] | None = None,
        metrics_collector: Any = None,
        trajectory_recorder: Any = None,
        memory_manager: Any = None,
    ) -> None:
        self.thread_id = thread_id or str(uuid.uuid4())
        self._base = _BaseHarness(thread_id=self.thread_id, graph=graph, initial_state=initial_state)
        self._metrics = metrics_collector
        self._trajectory = trajectory_recorder
        self._memory = memory_manager

    @property
    def final_state(self) -> dict:
        """当前底层 harness 的最终状态快照。"""
        return self._base.final_state

    async def stream_request(self, user_input: str) -> AsyncGenerator[HarnessEvent, None]:
        """流式提交旅行请求。集成指标收集。"""
        task_id = f"task-{self.thread_id[:8]}"

        # 注意：start_task 和 finish_task 由调用方（routes.py）负责
        # 这里只记录中间指标
        if self._trajectory:
            self._trajectory.start(task_id)

        # 注入记忆上下文
        if self._memory:
            context = await self._memory.prefetch_context(user_input)
            if context:
                user_input = f"{user_input}\n\n[用户历史偏好]\n{context}"
            self._memory.add_turn("user", user_input)

        try:
            async for event in self._base.stream_request(user_input):
                # 记录轨迹
                if self._trajectory and event.event_type == "node_complete":
                    self._trajectory.record(
                        task_id,
                        agent_name=event.node_name,
                        action="node_complete",
                        output=event.message[:200],
                    )

                # 记录指标
                if self._metrics and event.event_type == "node_complete":
                    self._metrics.record_agent_spawn(task_id)
                    self._metrics.record_step(task_id)

                yield HarnessEvent(event)
        finally:
            if self._trajectory:
                self._trajectory.finish(task_id)

    async def stream_resume(self, user_response: str) -> AsyncGenerator[HarnessEvent, None]:
        """流式恢复（人工审核后）。"""
        if self._memory:
            self._memory.add_turn("user", user_response)

        async for event in self._base.stream_resume(user_response):
            yield HarnessEvent(event)

    async def run_request(self, user_input: str) -> _HarnessResult:
        """非流式提交。"""
        return await self._base.run_request(user_input)

    async def run_resume(self, user_response: str) -> _HarnessResult:
        """非流式恢复。"""
        return await self._base.run_resume(user_response)
