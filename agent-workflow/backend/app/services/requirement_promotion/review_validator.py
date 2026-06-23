from app.schemas.demand_radar import CandidateRequirement
from app.schemas.requirement_promotion import ConfirmedRequirementFields, HumanReviewDecision


class RequirementPromotionError(ValueError):
    pass


class ReviewValidator:
    def validate(self, candidate: CandidateRequirement, decision: HumanReviewDecision) -> ConfirmedRequirementFields:
        if candidate.id != decision.candidate_id:
            raise RequirementPromotionError("decision candidateId does not match candidate.id")
        if candidate.status not in {"pending_review", "confirmed"}:
            raise RequirementPromotionError("candidate.status must be pending_review or confirmed")
        if decision.decision != "confirm":
            raise RequirementPromotionError("only confirm decisions can generate AgentInputPack")
        if decision.human_fields is None:
            raise RequirementPromotionError("humanFields are required for confirm decisions")

        fields = decision.human_fields
        if not fields.allow_agent:
            raise RequirementPromotionError("allowAgent must be true")
        if not _clean(fields.project_or_repo):
            raise RequirementPromotionError("projectOrRepo is required")
        if not _clean_list(fields.acceptance_criteria):
            raise RequirementPromotionError("acceptanceCriteria is required")
        if not _clean_list(fields.constraints):
            raise RequirementPromotionError("constraints are required; use '无特殊限制' when none")
        if not candidate.evidence:
            raise RequirementPromotionError("evidenceMessages are required")
        if any(not fact.message_id for fact in candidate.facts):
            raise RequirementPromotionError("facts must include sourceMessageIds")

        if candidate.requirement_type == "bug":
            if not _clean(fields.actual_behavior) or not _clean(fields.expected_behavior):
                raise RequirementPromotionError("bugfix requires actualBehavior and expectedBehavior")
        if candidate.requirement_type == "feature":
            if not (_clean(fields.desired_behavior) or _clean(fields.expected_behavior)) or not _clean(fields.scope):
                raise RequirementPromotionError("feature requires desiredBehavior or expectedBehavior, and scope")

        return fields


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _clean_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]
