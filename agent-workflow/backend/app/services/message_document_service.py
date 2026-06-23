from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.demand_radar import CandidateRequirement, DemandMessage
from app.schemas.message_document import ExtractorMode, MessageReviewDocumentRequest, MessageReviewDocumentResponse
from app.services.demand_radar import DemandRadar
from app.services.llm_demand_radar import LLMDemandRadar


MAX_DOCUMENT_CANDIDATES = 20
MAX_EVIDENCE_PER_CANDIDATE = 12
MAX_FACTS_PER_CANDIDATE = 12
MAX_INFERENCES_PER_CANDIDATE = 12
MAX_INLINE_TEXT_CHARS = 500
MAX_HEADING_TEXT_CHARS = 120


class MessageDocumentWriteError(RuntimeError):
    pass


class MessageReviewDocumentService:
    def __init__(self, output_root: Path | str = "review_documents"):
        self.output_root = Path(output_root)

    def build(self, request: MessageReviewDocumentRequest) -> MessageReviewDocumentResponse:
        candidates = _extract_candidates(request.extractor, request.messages)
        warnings = _warnings(messages=request.messages, candidates=candidates)
        candidates = _cap_candidates(candidates, warnings)
        created_at = datetime.now(timezone.utc)
        title = _safe_heading(request.title or _default_title(request.messages))
        document_id = _document_id(request.extractor, request.messages)
        markdown = _build_markdown(
            document_id=document_id,
            title=title,
            extractor=request.extractor,
            created_at=created_at,
            messages=request.messages,
            candidates=candidates,
            warnings=warnings,
        )
        document_path = None
        if request.write_document:
            document_path = str(self._write_document(document_id, markdown))
        return MessageReviewDocumentResponse(
            reviewDocumentId=document_id,
            title=title,
            extractor=request.extractor,
            createdAt=created_at,
            sourceMessageCount=len(request.messages),
            candidateCount=len(candidates),
            candidates=candidates,
            markdown=markdown,
            documentPath=document_path,
            warnings=warnings,
        )

    def build_from_candidates(self, messages: list[DemandMessage], candidates: list[CandidateRequirement], title: str | None = None, write_document: bool = False) -> MessageReviewDocumentResponse:
        warnings = _warnings(messages=messages, candidates=candidates)
        candidates = _cap_candidates(candidates, warnings)
        created_at = datetime.now(timezone.utc)
        clean_title = _safe_heading(title or _default_title(messages))
        document_id = _document_id("provided", messages)
        markdown = _build_markdown(document_id, clean_title, "provided", created_at, messages, candidates, warnings)
        document_path = str(self._write_document(document_id, markdown)) if write_document else None
        return MessageReviewDocumentResponse(
            reviewDocumentId=document_id,
            title=clean_title,
            extractor="provided",
            createdAt=created_at,
            sourceMessageCount=len(messages),
            candidateCount=len(candidates),
            candidates=candidates,
            markdown=markdown,
            documentPath=document_path,
            warnings=warnings,
        )

    def _write_document(self, document_id: str, markdown: str) -> Path:
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
            path = self.output_root / f"{document_id}.md"
            path.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            raise MessageDocumentWriteError(f"document write failed: {exc}") from exc
        return path


def _warnings(messages: list[DemandMessage], candidates: list[CandidateRequirement]) -> list[str]:
    warnings: list[str] = []
    if not messages:
        warnings.append("message batch is empty")
    if not candidates:
        warnings.append("no candidate requirements extracted")
    return warnings


def _cap_candidates(candidates: list[CandidateRequirement], warnings: list[str]) -> list[CandidateRequirement]:
    if len(candidates) > MAX_DOCUMENT_CANDIDATES:
        warnings.append(f"candidate count capped at {MAX_DOCUMENT_CANDIDATES}")
    return [_cap_candidate(candidate, warnings) for candidate in candidates[:MAX_DOCUMENT_CANDIDATES]]


def _cap_candidate(candidate: CandidateRequirement, warnings: list[str]) -> CandidateRequirement:
    updates = {}
    if len(candidate.evidence_message_ids) > MAX_EVIDENCE_PER_CANDIDATE:
        warnings.append(f"candidate {candidate.id} evidenceMessageIds capped at {MAX_EVIDENCE_PER_CANDIDATE}")
        updates["evidence_message_ids"] = candidate.evidence_message_ids[:MAX_EVIDENCE_PER_CANDIDATE]
    if len(candidate.evidence) > MAX_EVIDENCE_PER_CANDIDATE:
        warnings.append(f"candidate {candidate.id} evidence capped at {MAX_EVIDENCE_PER_CANDIDATE}")
        updates["evidence"] = candidate.evidence[:MAX_EVIDENCE_PER_CANDIDATE]
    if len(candidate.facts) > MAX_FACTS_PER_CANDIDATE:
        warnings.append(f"candidate {candidate.id} facts capped at {MAX_FACTS_PER_CANDIDATE}")
        updates["facts"] = candidate.facts[:MAX_FACTS_PER_CANDIDATE]
    if len(candidate.inferences) > MAX_INFERENCES_PER_CANDIDATE:
        warnings.append(f"candidate {candidate.id} inferences capped at {MAX_INFERENCES_PER_CANDIDATE}")
        updates["inferences"] = candidate.inferences[:MAX_INFERENCES_PER_CANDIDATE]
    return candidate.model_copy(update=updates, deep=True) if updates else candidate.model_copy(deep=True)


def _extract_candidates(extractor: ExtractorMode, messages: list[DemandMessage]) -> list[CandidateRequirement]:
    if not messages:
        return []
    if extractor == "llm":
        return LLMDemandRadar().extract(messages)
    return DemandRadar().extract(messages)


def _default_title(messages: list[DemandMessage]) -> str:
    if not messages:
        return "需求审查文档"
    chat_name = messages[0].chat_name or messages[0].chat_id
    return f"{chat_name} 需求审查文档"


def _document_id(extractor: ExtractorMode, messages: list[DemandMessage]) -> str:
    raw = "|".join(
        [
            extractor,
            *[f"{message.id}:{message.timestamp.isoformat()}:{message.text}" for message in messages],
        ]
    )
    return "review_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _build_markdown(
    document_id: str,
    title: str,
    extractor: ExtractorMode,
    created_at: datetime,
    messages: list[DemandMessage],
    candidates: list[CandidateRequirement],
    warnings: list[str],
) -> str:
    lines: list[str] = [
        f"# {_safe_heading(title)}",
        "",
        "## 1. 文档元信息",
        "",
        f"- Review Document ID: `{document_id}`",
        f"- Extractor: `{extractor}`",
        f"- Created At: `{created_at.isoformat()}`",
        f"- Source Message Count: `{len(messages)}`",
        f"- Candidate Count: `{len(candidates)}`",
        "- Execution Boundary: `review-only; not authorized for AgentRun or Git`",
        "",
    ]
    if warnings:
        lines.extend(["## 2. 警告", ""])
        for warning in warnings:
            lines.append(f"- {_md_inline(warning)}")
        lines.append("")
    else:
        lines.extend(["## 2. 警告", "", "- none", ""])

    lines.extend(["## 3. 候选需求", ""])
    if not candidates:
        lines.extend(["未提取到候选需求。", ""])
    for index, candidate in enumerate(candidates, start=1):
        lines.extend(_candidate_markdown(index, candidate))

    lines.extend(
        [
            "## 4. 人工确认填写区",
            "",
            "```yaml",
            "decision: confirm | reject | merge | expire",
            "reviewer: ",
            "project_or_repo: ",
            "working_dir: ",
            "scope: ",
            "constraints:",
            "  - ",
            "acceptance_criteria:",
            "  - ",
            "out_of_scope:",
            "  - 原始群聊消息不能直接触发 AgentRun",
            "allow_agent: false",
            "human_notes: ",
            "```",
            "",
            "## 5. 安全边界",
            "",
            "- 本文档只是审查材料，不是执行授权。",
            "- 只有人工确认后，才能提升为 WorkDocDraft / AgentInputPack。",
            "- 只有 WorkDoc validate / approve 后，才允许进入 AgentRun。",
            "- 本阶段不会触发 Git 或代码修改。",
            "",
        ]
    )
    return "\n".join(lines)


def _md_inline(value: str | None, limit: int = MAX_INLINE_TEXT_CHARS) -> str:
    text = " ".join(str(value or "").replace("\r", "\n").split())
    if len(text) > limit:
        text = text[: max(0, limit - 3)] + "..."
    return text.replace("`", "\\`").replace("<", "&lt;").replace(">", "&gt;")


def _safe_heading(value: str | None) -> str:
    text = _md_inline(value or "未命名文档", limit=MAX_HEADING_TEXT_CHARS).lstrip("#").strip()
    return text or "未命名文档"


def _candidate_markdown(index: int, candidate: CandidateRequirement) -> list[str]:
    confidence_score = max(0.0, min(float(candidate.confidence_score or 0.0), 1.0))
    lines = [
        f"### 3.{index} {_safe_heading(candidate.title)}",
        "",
        f"- Candidate ID: `{_md_inline(candidate.id)}`",
        f"- Type: `{candidate.requirement_type}`",
        f"- Status: `{candidate.status}`",
        f"- Confidence: `{candidate.confidence}` / `{confidence_score}`",
        f"- Hypothesis: {_md_inline(candidate.hypothesis)}",
        f"- Missing Fields: {_md_inline(', '.join(candidate.missing_fields) if candidate.missing_fields else 'none')}",
        "",
        "#### Evidence",
        "",
    ]
    if not candidate.evidence:
        lines.append("- none")
    for evidence in candidate.evidence:
        timestamp = evidence.timestamp.isoformat() if evidence.timestamp else "unknown-time"
        lines.append(f"- `{_md_inline(evidence.message_id)}` {_md_inline(evidence.sender or '未知')} @ {timestamp}: {_md_inline(evidence.text)}")
    lines.extend(["", "#### Facts", ""])
    if not candidate.facts:
        lines.append("- none")
    for fact in candidate.facts:
        lines.append(f"- {_md_inline(fact.text)} (`{_md_inline(fact.message_id)}`)")
    lines.extend(["", "#### Inferences", ""])
    if not candidate.inferences:
        lines.append("- none")
    for inference in candidate.inferences:
        basis = ", ".join(inference.basis_message_ids[:MAX_EVIDENCE_PER_CANDIDATE])
        lines.append(f"- {_md_inline(inference.text)} (basis: `{_md_inline(basis)}`)")
    lines.append("")
    return lines
