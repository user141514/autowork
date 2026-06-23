from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import timedelta

from app.schemas.demand_radar import (
    CandidateFact,
    CandidateInference,
    CandidateRequirement,
    DemandMessage,
    EvidenceMessage,
    SignalSummary,
)
from app.services.context_confidence import ContextConfidenceAnalyzer


ACK_TEXTS = {
    "1",
    "ok",
    "嗯",
    "好",
    "好的",
    "收到",
    "辛苦",
    "我看看",
    "了解",
    "明白",
    "可以",
}

SIGNAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "problem": (
        "报错",
        "失败",
        "打不开",
        "没反应",
        "不行",
        "不对",
        "异常",
        "闪退",
        "错位",
        "一直转圈",
        "500",
        "403",
        "bug",
        "error",
        "failed",
    ),
    "intent": (
        "能不能",
        "需要",
        "帮我",
        "加一个",
        "做一个",
        "改成",
        "优化",
        "支持",
        "整理",
        "修一下",
        "处理一下",
        "麻烦看一下",
        "期望",
        "预期",
        "应该",
        "验收",
    ),
    "object": (
        "页面",
        "首页",
        "设置",
        "工作台",
        "看板",
        "报表",
        "权限",
        "按钮",
        "接口",
        "数据库",
        "脚本",
        "仓库",
        "文件",
        "日志",
        "路由",
        "api",
        "表",
        "字段",
        "组件",
        "筛选",
        ".py",
        ".ts",
        ".tsx",
        ".md",
        "/api/",
    ),
    "constraint": (
        "不要",
        "别影响",
        "只改",
        "只修",
        "先只",
        "先别",
        "保持兼容",
        "不重构",
        "本地",
    ),
    "priority": (
        "紧急",
        "今天",
        "马上",
        "发版前",
        "优先",
        "先处理",
        "要修",
    ),
    "artifact": (
        "截图",
        "日志",
        "报错",
        "文件",
        "链接",
        "录屏",
    ),
    "termination": (
        "不用改",
        "不需要改",
        "已解决",
        "先不做",
        "取消",
        "忽略",
        "不是问题",
    ),
}


@dataclass(frozen=True)
class _AnnotatedMessage:
    message: DemandMessage
    signals: set[str]
    is_noise: bool


class DemandRadar:
    """Extract reviewable requirement candidates from noisy chat batches."""

    def extract(self, messages: list[DemandMessage]) -> list[CandidateRequirement]:
        if not messages:
            return []

        annotated = [_annotate_message(message) for message in sorted(messages, key=lambda item: item.timestamp)]
        windows = self._build_windows(annotated)
        return [self._candidate_from_window(window) for window in windows]

    def _build_windows(self, annotated: list[_AnnotatedMessage]) -> list[list[_AnnotatedMessage]]:
        seeds = [
            index
            for index, item in enumerate(annotated)
            if not item.is_noise and _is_seed(item.signals)
        ]
        if not seeds:
            return []

        raw_ranges: list[tuple[int, int]] = []
        for seed in seeds:
            seed_time = annotated[seed].message.timestamp
            start = seed
            while start > 0 and seed_time - annotated[start - 1].message.timestamp <= timedelta(minutes=15):
                start -= 1
            end = seed
            while end + 1 < len(annotated) and annotated[end + 1].message.timestamp - seed_time <= timedelta(minutes=8):
                end += 1
            raw_ranges.append((start, end))

        merged: list[tuple[int, int]] = []
        for start, end in sorted(raw_ranges):
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
                continue
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))

        windows: list[list[_AnnotatedMessage]] = []
        for start, end in merged:
            signal_items = [item for item in annotated[start : end + 1] if not item.is_noise and item.signals]
            if signal_items:
                windows.append(signal_items)
        return windows

    def _candidate_from_window(self, window: list[_AnnotatedMessage]) -> CandidateRequirement:
        messages = [item.message for item in window]
        summary = _signal_summary(window)
        evidence = [
            EvidenceMessage(
                message_id=message.id,
                sender=message.sender,
                timestamp=message.timestamp,
                text=message.text,
                role=_evidence_role(item),
            )
            for item in window
            for message in [item.message]
        ]
        evidence_ids = [message.id for message in messages]
        score = _confidence_score(summary, len(window))
        status = _status(summary, score)
        confidence = _confidence_label(score)
        requirement_type = _requirement_type(summary, messages)
        hypothesis = _hypothesis(requirement_type, messages)
        missing_fields = _missing_fields(summary, messages)
        candidate_id = _candidate_id(messages)
        context_assessment = ContextConfidenceAnalyzer().analyze(messages).assessment

        return CandidateRequirement(
            id=candidate_id,
            chat_id=messages[0].chat_id,
            chat_name=messages[0].chat_name,
            title=_title(hypothesis),
            requirement_type=requirement_type,
            status=status,
            confidence=confidence,
            confidence_score=score,
            hypothesis=hypothesis,
            evidence_message_ids=evidence_ids,
            evidence=evidence,
            facts=[
                CandidateFact(
                    text=f"{message.sender or '未知'}: {_truncate(message.text, 100)}",
                    message_id=message.id,
                )
                for message in messages
            ],
            inferences=[
                CandidateInference(
                    text=hypothesis,
                    basis_message_ids=evidence_ids,
                )
            ],
            missing_fields=missing_fields,
            signal_summary=summary,
            noise_ratio=0.0,
            context_assessment=context_assessment,
        )


def _annotate_message(message: DemandMessage) -> _AnnotatedMessage:
    text = _norm(message.text)
    signals: set[str] = set()
    for name, patterns in SIGNAL_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            signals.add(name)
    if message.msg_type in {"image", "file", "link"}:
        signals.add("artifact")
    is_noise = message.msg_type == "system" or not text or text in ACK_TEXTS
    return _AnnotatedMessage(message=message, signals=signals, is_noise=is_noise)


def _is_seed(signals: set[str]) -> bool:
    if "termination" in signals and len(signals) == 1:
        return False
    core = signals & {"problem", "intent", "object", "artifact"}
    if len(core) >= 2:
        return True
    if core and signals & {"priority", "constraint"}:
        return True
    if signals == {"problem"}:
        return True
    return bool("priority" in signals and "object" in signals)


def _signal_summary(window: list[_AnnotatedMessage]) -> SignalSummary:
    counts = {key: 0 for key in SIGNAL_PATTERNS}
    for item in window:
        for signal in item.signals:
            counts[signal] += 1
    return SignalSummary(**counts)


def _confidence_score(summary: SignalSummary, evidence_count: int) -> float:
    score = 0.0
    score += min(summary.problem, 2) * 0.18
    score += min(summary.intent, 2) * 0.18
    score += min(summary.object, 2) * 0.16
    score += min(summary.constraint, 1) * 0.12
    score += min(summary.priority, 1) * 0.14
    score += min(summary.artifact, 1) * 0.10
    score += min(evidence_count, 3) * 0.04
    if summary.termination:
        score = min(score, 0.42)
    if summary.object == 0:
        score = min(score, 0.58)
    return round(min(score, 0.95), 2)


def _status(summary: SignalSummary, score: float) -> str:
    if summary.termination:
        return "expired"
    if score >= 0.6 or (summary.intent and summary.object) or (summary.priority and (summary.intent or summary.object)):
        return "pending_review"
    return "suspect"


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _requirement_type(summary: SignalSummary, messages: list[DemandMessage]) -> str:
    text = _norm(" ".join(message.text for message in messages))
    if summary.problem:
        return "bug"
    if "文档" in text or "readme" in text or ".md" in text:
        return "document"
    if "数据" in text or "数据库" in text or "字段" in text or re.search(r"数据表|表结构|表名", text):
        return "data"
    if "配置" in text:
        return "config"
    if summary.intent:
        return "feature"
    return "uncertain"


def _hypothesis(requirement_type: str, messages: list[DemandMessage]) -> str:
    source = _best_source_text(messages)
    prefix = {
        "bug": "可能的 bug",
        "feature": "可能的功能/改动需求",
        "document": "可能的文档需求",
        "data": "可能的数据需求",
        "config": "可能的配置需求",
    }.get(requirement_type, "可能的需求")
    return f"{prefix}：{_truncate(source, 120)}"


def _best_source_text(messages: list[DemandMessage]) -> str:
    for message in messages:
        signals = _annotate_message(message).signals
        if signals & {"problem", "intent"}:
            return message.text
    return messages[0].text


def _missing_fields(summary: SignalSummary, messages: list[DemandMessage]) -> list[str]:
    text = _norm(" ".join(message.text for message in messages))
    missing: list[str] = []
    if summary.object == 0:
        missing.append("target_object")
    if not re.search(r"repo|仓库|项目路径|代码路径|根目录|\.py|\.ts|\.tsx|\.md", text):
        missing.append("project_or_repo")
    if not re.search(r"验收|期望|预期|应该|成功后|显示|提示", text):
        missing.append("acceptance_criteria")
    if summary.problem and not re.search(r"期望|预期|应该|验收", text):
        missing.append("expected_behavior")
    return missing


def _evidence_role(item: _AnnotatedMessage) -> str:
    for role in ("termination", "artifact", "problem", "intent", "constraint", "priority", "object"):
        if role in item.signals:
            return role
    return "context"


def _title(hypothesis: str) -> str:
    title = hypothesis.split("：", 1)[-1]
    return _truncate(title, 36)


def _candidate_id(messages: list[DemandMessage]) -> str:
    raw = "|".join([messages[0].chat_id, *[message.id for message in messages]])
    return "cand_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _norm(text: str) -> str:
    return text.strip().lower()


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "..."
