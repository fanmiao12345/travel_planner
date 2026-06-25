"""Travel planner execution harness.

这个模块是项目的统一运行层：UI、命令行、测试和后续 API 都应该
通过 TravelPlannerHarness 调用 LangGraph，而不是直接散落调用 graph.astream。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, AsyncIterator, Literal

from langgraph.types import Command


EventType = Literal["node_start", "node_complete", "token", "tool_call", "interrupt", "end"]


@dataclass
class HarnessEvent:
    """一次工作流执行中对外发布的事件。"""

    event_type: EventType
    node_name: str = ""
    update: dict[str, Any] = field(default_factory=dict)
    final_state: dict[str, Any] = field(default_factory=dict)
    completed_nodes: list[str] = field(default_factory=list)
    elapsed: float | None = None
    message: str = ""


@dataclass
class HarnessResult:
    """完整执行结果。"""

    final_state: dict[str, Any]
    completed_nodes: list[str]
    awaiting_review: bool = False
    interrupted: bool = False


def merge_travel_state(current: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any]:
    """Merge LangGraph update chunks into a renderable state snapshot."""
    merged = dict(current or {})
    for key, value in (update or {}).items():
        # messages 由 LangGraph 自己通过 add_messages reducer 维护；
        # UI 只需要各业务字段，所以这里跳过消息字段避免重复膨胀。
        if key == "messages":
            continue

        # reducer 字段在图内会合并；harness 在图外也要做同样的事情，
        # 否则前端实时展示时只能看到最后一个节点的局部更新。
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            if key == "evidence_sources":
                from tools.evidence import dedupe_evidence

                merged[key] = dedupe_evidence(merged[key] + value)
            else:
                merged[key] = merged[key] + value
        else:
            merged[key] = value
    return merged


class TravelPlannerHarness:
    """统一封装旅行规划工作流的执行、流式事件和恢复逻辑。"""

    def __init__(
        self,
        thread_id: str = "travel-session-1",
        graph: Any | None = None,
        initial_state: dict[str, Any] | None = None,
    ):
        self.thread_id = thread_id
        self.graph = graph
        self.final_state = dict(initial_state or {})

    def _get_graph(self):
        if self.graph is None:
            from graph.builder import get_graph

            self.graph = get_graph()
        return self.graph

    @property
    def graph_config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    async def stream_request(self, user_input: str) -> AsyncIterator[HarnessEvent]:
        """Start a new planning request and stream harness events."""
        from agents.state import create_initial_state

        self.final_state = dict(create_initial_state(user_input))
        async for event in self._stream(self.final_state):
            yield event

    async def stream_resume(self, user_response: str) -> AsyncIterator[HarnessEvent]:
        """Resume a paused human-review workflow."""
        async for event in self._stream(Command(resume=user_response)):
            yield event

    async def run_request(self, user_input: str) -> HarnessResult:
        """Run a request until completion or human-review interrupt."""
        result = HarnessResult(final_state={}, completed_nodes=[])
        async for event in self.stream_request(user_input):
            if event.final_state:
                result.final_state = event.final_state
            if event.completed_nodes:
                result.completed_nodes = event.completed_nodes
            if event.event_type == "interrupt":
                result.awaiting_review = True
                result.interrupted = True
        if not result.final_state:
            result.final_state = self.final_state
        return result

    async def run_resume(self, user_response: str) -> HarnessResult:
        """Resume and run until completion or another interrupt."""
        result = HarnessResult(final_state=self.final_state, completed_nodes=[])
        async for event in self.stream_resume(user_response):
            if event.final_state:
                result.final_state = event.final_state
            if event.completed_nodes:
                result.completed_nodes = event.completed_nodes
            if event.event_type == "interrupt":
                result.awaiting_review = True
                result.interrupted = True
        self.final_state = result.final_state
        return result

    async def _stream(self, graph_input: Any) -> AsyncIterator[HarnessEvent]:
        graph = self._get_graph()
        started: set[str] = set()
        completed: list[str] = []
        node_start_times: dict[str, float] = {}

        # 这里使用 stream_mode="updates" 作为主执行通道。它对
        # interrupt/Command(resume=...) 的语义最稳定，也不会在确认方案后
        # 因底层 token 事件流未正确收尾而卡住。详细 ReAct 信息仍由
        # graph/builder.py 从 ToolMessage 中抽取并放进节点 update。
        async for raw_event in graph.astream(
            graph_input,
            config=self.graph_config,
            stream_mode="updates",
        ):
            for node_name, update in raw_event.items():
                if node_name == "__end__":
                    continue

                if node_name == "__interrupt__":
                    yield HarnessEvent(
                        event_type="interrupt",
                        node_name="human_review",
                        final_state=self.final_state,
                        completed_nodes=list(completed),
                        message="流程已暂停，等待用户审核或修改意见",
                    )
                    continue

                if not isinstance(update, dict):
                    continue

                if node_name not in started:
                    started.add(node_name)
                    node_start_times[node_name] = perf_counter()
                    yield HarnessEvent(
                        event_type="node_start",
                        node_name=node_name,
                        final_state=self.final_state,
                        completed_nodes=list(completed),
                    )

                if node_name not in completed:
                    completed.append(node_name)

                self.final_state = merge_travel_state(self.final_state, update)
                elapsed = None
                if node_name in node_start_times:
                    elapsed = perf_counter() - node_start_times[node_name]

                yield HarnessEvent(
                    event_type="node_complete",
                    node_name=node_name,
                    update=update,
                    final_state=self.final_state,
                    completed_nodes=list(completed),
                    elapsed=elapsed,
                )

        yield HarnessEvent(
            event_type="end",
            final_state=self.final_state,
            completed_nodes=list(completed),
        )
