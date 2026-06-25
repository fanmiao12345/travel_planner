"""
评估报告生成器
"""

from __future__ import annotations

from typing import Any

from .collector import TaskMetrics


class Reporter:
    """评估报告生成器。"""

    def generate_summary(self, metrics_list: list[TaskMetrics]) -> dict[str, Any]:
        """生成评估摘要。"""
        if not metrics_list:
            return {"task_count": 0}

        total = len(metrics_list)
        avg_accuracy = sum(m.accuracy for m in metrics_list) / total
        avg_latency = sum(m.total_latency_ms for m in metrics_list) / total
        total_tokens = sum(m.total_tokens for m in metrics_list)

        tasks = {}
        for m in metrics_list:
            tasks[m.task_id] = {
                "accuracy": m.accuracy,
                "latency_ms": m.total_latency_ms,
                "tokens": m.total_tokens,
                "tool_success_rate": m.tool_success_rate,
                "agents": m.agent_count,
            }

        return {
            "task_count": total,
            "avg_accuracy": round(avg_accuracy, 3),
            "avg_latency_ms": int(avg_latency),
            "total_tokens": total_tokens,
            "tasks": tasks,
        }
