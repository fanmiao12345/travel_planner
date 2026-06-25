"""
评估管线

编排: MetricsCollector → TrajectoryRecorder → LLM Judge → DriftDetector → AutoOptimizer
"""

from __future__ import annotations

from typing import Any

from .checker import QualityChecker, QualityReport
from .collector import MetricsCollector, TaskMetrics
from .drift import DriftAlert, DriftDetector
from .judge import EvalResult, LLMEvaluator
from .optimizer import AutoOptimizer
from .store import EvalStore
from .trajectory import Trajectory, TrajectoryRecorder


class EvaluationPipeline:
    """评估管线。"""

    def __init__(
        self,
        store: EvalStore,
        drift_detector: DriftDetector | None = None,
        auto_judge: bool = True,
        auto_optimize: bool = False,
    ) -> None:
        self._store = store
        self._drift = drift_detector or DriftDetector()
        self._auto_judge = auto_judge
        self._optimizer = AutoOptimizer(store, self._drift) if auto_optimize else None
        self._judge = LLMEvaluator()
        self._checker = QualityChecker()

    async def evaluate_task(
        self,
        task_id: str,
        query: str,
        output: str,
        accuracy: float = 0.0,
        latency_ms: int = 0,
        total_tokens: int = 0,
        trajectory_summary: str = "",
    ) -> EvalResult | None:
        """执行完整评估流程。"""
        # 持久化指标
        self._store.save_task_metrics({
            "task_id": task_id, "accuracy": accuracy,
            "total_latency_ms": latency_ms, "total_tokens": total_tokens,
        })

        # 漂移检测
        self._drift.record("accuracy", accuracy)
        alerts = self._drift.check("accuracy", accuracy)
        for alert in alerts:
            self._store.save_drift_alert(
                alert.metric, alert.baseline, alert.current,
                alert.deviation, alert.message,
            )

        # LLM Judge
        eval_result = None
        if self._auto_judge:
            lang = "zh" if any("一" <= c <= "鿿" for c in query) else "en"
            eval_result = await self._judge.evaluate(query, output, trajectory_summary, lang)
            self._store.save_eval_result(task_id, {
                "scores": eval_result.scores,
                "reasoning": eval_result.reasoning,
                "suggestions": eval_result.suggestions,
                "overall_score": eval_result.overall_score,
            })

        # 自动调参
        if self._optimizer:
            await self._optimizer.check_and_adjust()

        return eval_result

    async def run_quality_check(
        self,
        output: str,
        evidence_ids: list[str] | None = None,
    ) -> QualityReport:
        """运行质量检查。"""
        return await self._checker.check(output, evidence_ids=evidence_ids)

    @staticmethod
    def build_trajectory_summary(steps: list[dict]) -> str:
        """构建轨迹摘要。最多 50 步，每步 200 字符。"""
        lines = []
        for step in steps[:50]:
            action = step.get("action", "")
            agent = step.get("agent_name", "")
            tool = step.get("tool_name", "")
            output = str(step.get("output", ""))[:200]
            line = f"[{agent}] {action}"
            if tool:
                line += f" → {tool}"
            line += f": {output}"
            lines.append(line)
        return "\n".join(lines)
