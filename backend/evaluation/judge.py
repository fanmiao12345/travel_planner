"""
LLM-as-Judge — 4 维度评估

维度: 完整性, 准确性, 结构化, 效率
双语支持 (zh/en)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalRubric:
    dimensions: dict[str, str] = field(default_factory=lambda: {
        "completeness": "旅行方案是否覆盖了路线、天气、交通、住宿、餐饮、预算所有维度",
        "accuracy": "提供的信息是否真实、准确、可执行",
        "structure": "行程是否清晰、有条理、用户可以直接使用",
        "efficiency": "Token 和时间使用是否合理，没有冗余操作",
    })


@dataclass
class EvalResult:
    scores: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    suggestions: list[str] = field(default_factory=list)
    overall_score: float = 0.0


_DEFAULT_RUBRIC = EvalRubric()


class LLMEvaluator:
    """LLM-as-Judge 评估器。"""

    def __init__(self, rubric: EvalRubric | None = None) -> None:
        self._rubric = rubric or _DEFAULT_RUBRIC

    async def evaluate(
        self,
        task: str,
        output: str,
        trajectory_summary: str = "",
        lang: str = "zh",
    ) -> EvalResult:
        """使用 LLM 评估旅行方案质量。"""
        from backend.core.config import get_settings

        settings = get_settings()
        llm = settings.get_llm()

        dimensions_desc = "\n".join(
            f"- {k}: {v}" for k, v in self._rubric.dimensions.items()
        )

        if lang == "zh":
            prompt = f"""你是一个旅行方案质量评估专家。请对以下旅行方案进行评估。

## 用户需求
{task}

## AI 生成的方案
{output[:3000]}

## 执行轨迹摘要
{trajectory_summary[:1000]}

## 评估维度
{dimensions_desc}

## 评分标准
- 0.0-0.2: 完全不相关或无用
- 0.3-0.4: 有重大缺失
- 0.5-0.6: 基本可用
- 0.7-0.8: 质量良好
- 0.9-1.0: 优秀

请以 JSON 格式输出:
{{"scores": {{"completeness": 0.0, "accuracy": 0.0, "structure": 0.0, "efficiency": 0.0}}, "reasoning": "评估理由", "suggestions": ["改进建议1", "改进建议2"]}}"""
        else:
            prompt = f"""You are a travel plan quality evaluator. Rate the following plan.

## User Request
{task}

## AI Generated Plan
{output[:3000]}

## Execution Summary
{trajectory_summary[:1000]}

## Dimensions
{dimensions_desc}

## Scoring
- 0.0-0.2: Irrelevant, 0.3-0.4: Major gaps, 0.5-0.6: Adequate, 0.7-0.8: Good, 0.9-1.0: Excellent

Output JSON: {{"scores": {{"completeness": 0.0, "accuracy": 0.0, "structure": 0.0, "efficiency": 0.0}}, "reasoning": "...", "suggestions": ["..."]}}"""

        try:
            from langchain_core.messages import HumanMessage
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return self._parse_result(response.content)
        except Exception:
            return EvalResult(
                scores={k: 0.5 for k in self._rubric.dimensions},
                reasoning="评估失败，使用默认分数",
                overall_score=0.5,
            )

    def _parse_result(self, content: str) -> EvalResult:
        """解析 LLM 输出为 EvalResult。"""
        # 尝试提取 JSON
        json_match = re.search(r"\{[^{}]*\"scores\"[^{}]*\}", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                scores = data.get("scores", {})
                overall = sum(scores.values()) / len(scores) if scores else 0.5
                return EvalResult(
                    scores=scores,
                    reasoning=data.get("reasoning", ""),
                    suggestions=data.get("suggestions", []),
                    overall_score=overall,
                )
            except json.JSONDecodeError:
                pass
        # 回退
        return EvalResult(
            scores={k: 0.5 for k in self._rubric.dimensions},
            reasoning="无法解析评估结果",
            overall_score=0.5,
        )
