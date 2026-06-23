from app.schemas.demand_radar import CandidateRequirement
from app.schemas.requirement_promotion import HumanReviewDecision, RequirementPromotionResult
from app.services.requirement_promotion.agent_brief_markdown_builder import AgentBriefMarkdownBuilder
from app.services.requirement_promotion.agent_input_builder import AgentInputBuilder
from app.services.requirement_promotion.review_validator import RequirementPromotionError, ReviewValidator
from app.services.requirement_promotion.workdoc_draft_builder import WorkDocDraftBuilder


class RequirementPromoter:
    def __init__(
        self,
        validator: ReviewValidator | None = None,
        workdoc_builder: WorkDocDraftBuilder | None = None,
        agent_input_builder: AgentInputBuilder | None = None,
        brief_builder: AgentBriefMarkdownBuilder | None = None,
    ):
        self.validator = validator or ReviewValidator()
        self.workdoc_builder = workdoc_builder or WorkDocDraftBuilder()
        self.agent_input_builder = agent_input_builder or AgentInputBuilder()
        self.brief_builder = brief_builder or AgentBriefMarkdownBuilder()

    def promote(
        self,
        candidate: CandidateRequirement,
        decision: HumanReviewDecision,
    ) -> RequirementPromotionResult:
        fields = self.validator.validate(candidate, decision)
        workdoc = self.workdoc_builder.build(candidate, fields)
        pack = self.agent_input_builder.build(workdoc)
        brief = self.brief_builder.build(workdoc, pack)
        return RequirementPromotionResult(
            workdoc_draft=workdoc,
            agent_input_pack=pack,
            agent_brief_markdown=brief,
        )


__all__ = ["RequirementPromoter", "RequirementPromotionError"]
