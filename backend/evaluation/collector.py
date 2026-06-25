"""
指标收集器

记录延迟、Token、工具调用成功率、Agent 数量等。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TaskMetrics:
    task_id: str
    accuracy: float = 0.0
    total_latency_ms: int = 0
    step_latencies: list[int] = field(default_factory=list)
    total_tokens: int = 0
    tool_call_count: int = 0
    tool_success_count: int = 0
    tool_success_rate: float = 0.0
    agent_count: int = 0
    iteration_count: int = 0


class MetricsCollector:
    """指标收集器。"""

    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}

    def start_task(self, task_id: str) -> None:
        self._tasks[task_id] = {
            "start_time": time.monotonic(),
            "step_start": time.monotonic(),
            "tool_calls": 0,
            "tool_successes": 0,
            "tokens": 0,
            "agents": 0,
            "iterations": 0,
            "step_latencies": [],
        }

    def record_tool_call(self, task_id: str | None = None, success: bool = True, latency_ms: int = 0) -> None:
        tid = task_id or self._active_task_id()
        if not tid or tid not in self._tasks:
            return
        t = self._tasks[tid]
        t["tool_calls"] += 1
        if success:
            t["tool_successes"] += 1

    def record_tokens(self, task_id: str | None = None, input_tokens: int = 0, output_tokens: int = 0) -> None:
        tid = task_id or self._active_task_id()
        if not tid or tid not in self._tasks:
            return
        self._tasks[tid]["tokens"] += input_tokens + output_tokens

    def record_iteration(self, task_id: str | None = None) -> None:
        tid = task_id or self._active_task_id()
        if not tid or tid not in self._tasks:
            return
        self._tasks[tid]["iterations"] += 1

    def record_agent_spawn(self, task_id: str | None = None) -> None:
        tid = task_id or self._active_task_id()
        if not tid or tid not in self._tasks:
            return
        self._tasks[tid]["agents"] += 1

    def record_step(self, task_id: str | None = None) -> None:
        tid = task_id or self._active_task_id()
        if not tid or tid not in self._tasks:
            return
        t = self._tasks[tid]
        now = time.monotonic()
        latency = int((now - t["step_start"]) * 1000)
        t["step_latencies"].append(latency)
        t["step_start"] = now

    def finish_task(self, task_id: str, accuracy: float = 0.0) -> TaskMetrics:
        t = self._tasks.pop(task_id, None)
        if not t:
            return TaskMetrics(task_id=task_id)
        return self._build_metrics(task_id, t, accuracy)

    def snapshot_task(self, task_id: str, accuracy: float = 0.0) -> TaskMetrics:
        """获取当前任务指标快照，不结束任务。"""
        t = self._tasks.get(task_id)
        if not t:
            return TaskMetrics(task_id=task_id)
        return self._build_metrics(task_id, t, accuracy)

    def _build_metrics(self, task_id: str, t: dict, accuracy: float = 0.0) -> TaskMetrics:
        total_ms = int((time.monotonic() - t["start_time"]) * 1000)
        tc = t["tool_calls"]
        return TaskMetrics(
            task_id=task_id, accuracy=accuracy, total_latency_ms=total_ms,
            step_latencies=t["step_latencies"], total_tokens=t["tokens"],
            tool_call_count=tc, tool_success_count=t["tool_successes"],
            tool_success_rate=t["tool_successes"] / tc if tc > 0 else 0.0,
            agent_count=t["agents"], iteration_count=t["iterations"],
        )

    def _active_task_id(self) -> str | None:
        if len(self._tasks) == 1:
            return next(iter(self._tasks))
        return None
