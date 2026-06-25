"""
4 层质量检查器

1. 来源合规: 引用是否充分
2. 大纲完整: 6 个维度是否覆盖
3. 内容冗余: Jaccard 相似度去重
4. 证据匹配: 事实陈述是否有引用
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class QualityReport:
    source_compliance: float = 0.0    # 0-1
    completeness: float = 0.0         # 0-1
    redundancy: float = 0.0           # 0-1 (1 = 无冗余)
    evidence_match: float = 0.0       # 0-1
    overall: float = 0.0              # 加权总分
    issues: list[str] = field(default_factory=list)


# 旅行方案必须覆盖的维度
_REQUIRED_DIMENSIONS = ["路线", "天气", "交通", "住宿", "餐饮", "预算"]
_DIMENSION_KEYWORDS = {
    "路线": ["路线", "行程", "景点", "打卡", "游览", "日程"],
    "天气": ["天气", "气温", "温度", "穿衣", "雨", "晴"],
    "交通": ["交通", "航班", "火车", "高铁", "自驾", "驾车", "机票"],
    "住宿": ["住宿", "酒店", "民宿", "宾馆", "入住"],
    "餐饮": ["餐饮", "美食", "餐厅", "小吃", "吃饭", "推荐"],
    "预算": ["预算", "费用", "花费", "省钱", "价格", "人均"],
}


class QualityChecker:
    """4 层质量检查器。"""

    async def check(
        self,
        output: str,
        outline: str | None = None,
        evidence_ids: list[str] | None = None,
    ) -> QualityReport:
        issues: list[str] = []

        # 层 1: 来源合规
        source_score = self._check_sources(output, evidence_ids, issues)

        # 层 2: 大纲完整
        completeness_score = self._check_completeness(output, issues)

        # 层 3: 内容冗余
        redundancy_score = self._check_redundancy(output, issues)

        # 层 4: 证据匹配
        evidence_score = self._check_evidence_match(output, evidence_ids, issues)

        overall = (
            0.30 * source_score +
            0.30 * completeness_score +
            0.15 * redundancy_score +
            0.25 * evidence_score
        )

        return QualityReport(
            source_compliance=source_score,
            completeness=completeness_score,
            redundancy=redundancy_score,
            evidence_match=evidence_score,
            overall=overall,
            issues=issues,
        )

    def _check_sources(self, output: str, evidence_ids: list[str] | None, issues: list[str]) -> float:
        """检查来源引用充分性。"""
        url_count = len(re.findall(r"https?://\S+", output))
        citation_count = len(re.findall(r"\[E\d{4}\]", output))

        if url_count == 0 and citation_count == 0:
            issues.append("方案中没有任何来源引用")
            return 0.2
        if url_count + citation_count < 3:
            issues.append("来源引用不足 (少于 3 个)")
            return 0.5
        return min(1.0, (url_count + citation_count) / 5)

    def _check_completeness(self, output: str, issues: list[str]) -> float:
        """检查维度覆盖完整性。"""
        covered = 0
        for dim, keywords in _DIMENSION_KEYWORDS.items():
            if any(kw in output for kw in keywords):
                covered += 1
            else:
                issues.append(f"缺少 {dim} 相关信息")
        return covered / len(_REQUIRED_DIMENSIONS)

    def _check_redundancy(self, output: str, issues: list[str]) -> float:
        """检查内容冗余度 (Jaccard 相似度)。"""
        # 按段落分割
        paragraphs = [p.strip() for p in output.split("\n\n") if len(p.strip()) > 50]
        if len(paragraphs) < 2:
            return 1.0

        max_overlap = 0.0
        for i in range(len(paragraphs)):
            for j in range(i + 1, len(paragraphs)):
                set_a = set(paragraphs[i])
                set_b = set(paragraphs[j])
                intersection = len(set_a & set_b)
                union = len(set_a | set_b)
                if union > 0:
                    overlap = intersection / union
                    max_overlap = max(max_overlap, overlap)

        if max_overlap > 0.7:
            issues.append(f"内容存在高度冗余 (相似度 {max_overlap:.0%})")
        return max(0.0, 1.0 - max_overlap)

    def _check_evidence_match(self, output: str, evidence_ids: list[str] | None, issues: list[str]) -> float:
        """检查事实陈述是否有引用支撑。"""
        # 简单检查: 包含数字/日期的句子是否有引用
        sentences = re.split(r"[。！？\n]", output)
        factual = [s for s in sentences if re.search(r"\d+[元天日点度]|¥|\$", s)]
        cited = [s for s in factual if re.search(r"\[E\d{4}\]|https?://", s)]

        if not factual:
            return 0.8  # 没有事实陈述，不需要引用

        ratio = len(cited) / len(factual) if factual else 1.0
        if ratio < 0.3:
            issues.append(f"事实陈述引用不足 ({len(cited)}/{len(factual)})")
        return min(1.0, ratio + 0.3)
