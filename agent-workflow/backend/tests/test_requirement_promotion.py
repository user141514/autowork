from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.demand_radar import (
    CandidateFact,
    CandidateInference,
    CandidateRequirement,
    EvidenceMessage,
    SignalSummary,
)
from app.schemas.requirement_promotion import ConfirmedRequirementFields, HumanReviewDecision
from app.services.requirement_promotion.agent_inbox_writer import AgentInboxWriter
from app.services.requirement_promotion.requirement_promoter import RequirementPromoter, RequirementPromotionError


NOW = datetime(2026, 6, 19, 9, 0, tzinfo=timezone.utc)


def _candidate(requirement_type: str = "bug", status: str = "pending_review") -> CandidateRequirement:
    return CandidateRequirement(
        id="cand_001",
        chat_id="room-a",
        chat_name="项目A工作群",
        title="设置页保存接口 500",
        requirement_type=requirement_type,
        status=status,
        confidence="high",
        confidence_score=0.86,
        hypothesis="可能的 bug：设置页保存接口 500，页面一直转圈",
        evidence_message_ids=["m-1", "m-2"],
        evidence=[
            EvidenceMessage(
                message_id="m-1",
                sender="Tester",
                timestamp=NOW,
                text="设置页保存接口 500，页面一直转圈",
                role="problem",
            ),
            EvidenceMessage(
                message_id="m-2",
                sender="PM",
                timestamp=NOW,
                text="期望保存成功后提示已保存",
                role="intent",
            ),
        ],
        facts=[
            CandidateFact(text="Tester: 设置页保存接口 500，页面一直转圈", message_id="m-1"),
            CandidateFact(text="PM: 期望保存成功后提示已保存", message_id="m-2"),
        ],
        inferences=[
            CandidateInference(text="系统推断这是设置页保存失败问题", basis_message_ids=["m-1", "m-2"])
        ],
        missing_fields=["project_or_repo"],
        signal_summary=SignalSummary(problem=1, intent=1, object=1),
        noise_ratio=0.0,
    )


def _fields(**overrides) -> ConfirmedRequirementFields:
    data = {
        "project_or_repo": "agent-workflow",
        "working_dir": "F:/autowork/agent-workflow/backend",
        "branch": "main",
        "module": "settings",
        "page": "设置页",
        "target_object": "保存按钮",
        "actual_behavior": "点击保存后接口 500，页面一直转圈",
        "expected_behavior": "保存成功后提示已保存",
        "desired_behavior": None,
        "scope": "只修设置页保存流程",
        "constraints": ["不要做大范围重构"],
        "acceptance_criteria": ["保存成功后显示已保存提示"],
        "out_of_scope": ["不调整其他设置项"],
        "human_notes": "先做最小修复",
        "allow_agent": True,
    }
    data.update(overrides)
    return ConfirmedRequirementFields(**data)


def _decision(decision: str = "confirm", **field_overrides) -> HumanReviewDecision:
    return HumanReviewDecision(
        candidate_id="cand_001",
        decision=decision,
        reviewer="human",
        reviewed_at=NOW,
        reason="reviewed",
        human_fields=_fields(**field_overrides) if decision == "confirm" else None,
    )


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"project_or_repo": ""}, "projectOrRepo is required"),
        ({"acceptance_criteria": []}, "acceptanceCriteria is required"),
    ],
)
def test_required_common_fields_are_validated(overrides, expected):
    with pytest.raises(RequirementPromotionError, match=expected):
        RequirementPromoter().promote(_candidate(), _decision(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_behavior": ""},
        {"expected_behavior": ""},
    ],
)
def test_bug_requires_actual_and_expected_behavior(overrides):
    with pytest.raises(RequirementPromotionError, match="bugfix requires"):
        RequirementPromoter().promote(_candidate("bug"), _decision(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"desired_behavior": "", "expected_behavior": ""},
        {"scope": ""},
    ],
)
def test_feature_requires_desired_or_expected_behavior_and_scope(overrides):
    with pytest.raises(RequirementPromotionError, match="feature requires"):
        RequirementPromoter().promote(_candidate("feature"), _decision(**overrides))


def test_allow_agent_false_blocks_agent_input_pack():
    with pytest.raises(RequirementPromotionError, match="allowAgent must be true"):
        RequirementPromoter().promote(_candidate(), _decision(allow_agent=False))


def test_inferences_become_assumptions_not_facts():
    result = RequirementPromoter().promote(_candidate(), _decision())

    assert result.workdoc_draft.assumptions == ["系统推断这是设置页保存失败问题"]
    fact_text = " ".join(fact.fact for fact in result.workdoc_draft.facts)
    assert "系统推断" not in fact_text


def test_agent_inbox_writes_four_files(tmp_path: Path):
    result = RequirementPromoter().promote(_candidate(), _decision())

    inbox_dir = AgentInboxWriter(root_dir=tmp_path).write(result)

    assert (inbox_dir / "agent_input.json").exists()
    assert (inbox_dir / "agent_brief.md").exists()
    assert (inbox_dir / "workdoc_draft.json").exists()
    assert (inbox_dir / "evidence.json").exists()


def test_default_execution_policy_blocks_push_deploy_and_broad_refactor():
    result = RequirementPromoter().promote(_candidate(), _decision())
    policy = result.agent_input_pack.execution_policy

    assert policy.allow_push is False
    assert policy.allow_git_commit is False
    assert "Do not deploy" in policy.forbidden_actions
    assert "Do not push to remote" in policy.forbidden_actions
    assert "Do not perform broad refactors unless explicitly requested" in policy.forbidden_actions


def test_evidence_messages_enter_agent_input_pack():
    result = RequirementPromoter().promote(_candidate(), _decision())

    assert [item.message_id for item in result.agent_input_pack.evidence] == ["m-1", "m-2"]
    assert result.agent_input_pack.evidence[0].source == "chat"


@pytest.mark.parametrize("decision", ["reject", "expire", "merge"])
def test_non_confirm_decisions_do_not_generate_agent_input_pack(decision):
    with pytest.raises(RequirementPromotionError, match="only confirm"):
        RequirementPromoter().promote(_candidate(), _decision(decision=decision))


def test_promotion_api_returns_pack_without_running_agent():
    client = TestClient(create_app())

    response = client.post(
        "/requirement-promotion/promote",
        json={
            "candidate": _candidate().model_dump(mode="json", by_alias=True),
            "decision": _decision().model_dump(mode="json", by_alias=True),
            "writeInbox": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workdocDraft"]["candidateId"] == "cand_001"
    assert body["agentInputPack"]["executionPolicy"]["allowPush"] is False
    assert body["inboxPath"] is None
    assert "agent_run_id" not in body


def test_promotion_api_returns_400_for_review_validation_errors():
    client = TestClient(create_app())
    decision = _decision(expected_behavior="")

    response = client.post(
        "/requirement-promotion/promote",
        json={
            "candidate": _candidate().model_dump(mode="json", by_alias=True),
            "decision": decision.model_dump(mode="json", by_alias=True),
            "writeInbox": False,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bugfix requires actualBehavior and expectedBehavior"
