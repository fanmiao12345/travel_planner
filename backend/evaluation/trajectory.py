"""
执行轨迹记录器

逐步记录 Agent 执行轨迹: 工具调用、输入输出、延迟。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TrajectoryStep:
    step_index: int
    agent_name: str
    action: str       # "tool_call" | "reasoning" | "summarize"
    input: str = ""
    output: str = ""
    tool_name: str | None = None
    tool_params: dict | None = None
    latency_ms: int = 0


@dataclass
class Trajectory:
    task_id: str
    steps: list[TrajectoryStep] = field(default_factory=list)


class TrajectoryRecorder:
    """轨迹记录器。"""

    def __init__(self) -> None:
        self._trajectories: dict[str, Trajectory] = {}
        self._step_counters: dict[str, int] = {}
        self._step_start: dict[str, float] = {}

    def start(self, task_id: str) -> None:
        self._trajectories[task_id] = Trajectory(task_id=task_id)
        self._step_counters[task_id] = 0
        self._step_start[task_id] = time.monotonic()

    def record(self, task_id: str, step: TrajectoryStep | None = None, **kwargs) -> None:
        """记录一步。可传 TrajectoryStep 或关键字参数。"""
        if task_id not in self._trajectories:
            return
        if step is None:
            now = time.monotonic()
            start = self._step_start.get(task_id, now)
            latency = int((now - start) * 1000)
            self._step_counters[task_id] += 1
            step = TrajectoryStep(
                step_index=self._step_counters[task_id],
                latency_ms=latency,
                **kwargs,
            )
            self._step_start[task_id] = now
        self._trajectories[task_id].steps.append(step)

    def finish(self, task_id: str) -> Trajectory:
        return self._trajectories.pop(task_id, Trajectory(task_id=task_id))

    def get(self, task_id: str) -> Trajectory | None:
        return self._trajectories.get(task_id)

    def clear(self, task_id: str) -> None:
        self._trajectories.pop(task_id, None)
        self._step_counters.pop(task_id, None)
        self._step_start.pop(task_id, None)
