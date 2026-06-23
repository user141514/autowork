import hashlib
from datetime import datetime, timezone

from app.schemas.demand_radar import CandidateRequirement
from app.schemas.requirement_promotion import (
    ConfirmedRequirementFields,
    PromotedRequirementType,
    WorkDocDraft,
    WorkDocEvidence,
    WorkDocFact,
)


TYPE_MAP: dict[str, PromotedRequirementType] = {
    "bug": "bugfix",
    "feature": "feature",
    "config": "config",
    "data": "data",
    "document": "doc",
    "uncertain": "process",
}


class WorkDocDraftBuilder:
    def build(self, candidate: CandidateRequirement, fields: ConfirmedRequirementFields) -> WorkDocDraft:
        now = datetime.now(timezone.utc)
        workdoc_id = _stable_id("wd", candidate.id, fields.project_or_repo, fields.scope)
        return WorkDocDraft(
            workdoc_id=workdoc_id,
            candidate_id=candidate.id,
            title=candidate.title,
            type=TYPE_MAP.get(candidate.requirement_type, "process"),
            project_or_repo=fields.project_or_repo.strip(),
            working_dir=_optional(fields.working_dir),
            branch=_optional(fields.branch),
            background=_background(candidate, fields),
            problem_statement=_problem_statement(candidate, fields),
            expected_outcome=_expected_outcome(fields),
            evidence=[
                WorkDocEvidence(
                    message_id=item.message_id,
                    sender=item.sender,
                    timestamp=item.timestamp,
                    text=item.text,
                )
                for item in candidate.evidence
            ],
            facts=[
                WorkDocFact(fact=fact.text, source_message_ids=[fact.message_id])
                for fact in candidate.facts
                if fact.message_id
            ],
            assumptions=[inference.text for inference in candidate.inferences],
            constraints=[item.strip() for item in fields.constraints if item.strip()],
            acceptance_criteria=[item.strip() for item in fields.acceptance_criteria if item.strip()],
            out_of_scope=[item.strip() for item in fields.out_of_scope if item.strip()],
            human_notes=_optional(fields.human_notes),
            status="draft",
            created_at=now,
            updated_at=now,
        )


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _background(candidate: CandidateRequirement, fields: ConfirmedRequirementFields) -> str:
    pieces = [
        f"From chat room {candidate.chat_name}.",
        f"Candidate confidence: {candidate.confidence} ({candidate.confidence_score}).",
    ]
    if fields.module:
        pieces.append(f"Module: {fields.module}.")
    if fields.page:
        pieces.append(f"Page: {fields.page}.")
    if fields.target_object:
        pieces.append(f"Target object: {fields.target_object}.")
    return " ".join(pieces)


def _problem_statement(candidate: CandidateRequirement, fields: ConfirmedRequirementFields) -> str:
    if fields.actual_behavior:
        return fields.actual_behavior.strip()
    if fields.desired_behavior:
        return fields.desired_behavior.strip()
    return candidate.hypothesis


def _expected_outcome(fields: ConfirmedRequirementFields) -> str:
    return (
        fields.expected_behavior
        or fields.desired_behavior
        or "; ".join(fields.acceptance_criteria)
    ).strip()


def _optional(value: str | None) -> str | None:
    clean = (value or "").strip()
    return clean or None
