from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.demand_radar import DemandMessage
from app.services.context_confidence import ContextConfidenceAnalyzer
from app.services.demand_radar import DemandRadar


BASE_TIME = datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc)


def _msg(idx: int, text: str, *, minute: int | None = None, sender: str = "Alice") -> DemandMessage:
    return DemandMessage(
        id=f"m-{idx}",
        chat_id="room-a",
        chat_name="项目A工作群",
        sender=sender,
        timestamp=BASE_TIME + timedelta(minutes=minute if minute is not None else idx),
        text=text,
        msg_type="text",
        source="test",
    )


def test_self_contained_question_can_be_answered_directly():
    result = ContextConfidenceAnalyzer().analyze(
        [_msg(1, "@WorkBot Python 里的 pathlib.Path 是干什么用的？")]
    )

    assert result.assessment.resolution == "self_contained"
    assert result.assessment.suggested_action == "direct_answer_ready"
    assert result.direct_answer_draft is not None
    assert "pathlib.Path" in result.direct_answer_draft.question


def test_local_context_enough_becomes_candidate_ready():
    result = ContextConfidenceAnalyzer().analyze(
        [
            _msg(1, "设置页保存接口 500，页面一直转圈", sender="Tester"),
            _msg(2, "期望保存成功后提示已保存", sender="PM"),
        ]
    )

    assert result.assessment.resolution == "local_context_enough"
    assert result.assessment.suggested_action == "candidate_ready"
    assert result.assessment.confidence in {"medium", "high"}
    assert "has_explicit_object" in result.assessment.reasons


def test_remote_reference_requires_more_history():
    result = ContextConfidenceAnalyzer().analyze(
        [_msg(1, "@WorkBot 还是按刚才那个方案改一下，这次别漏字段")]
    )

    assert result.assessment.resolution == "needs_more_history"
    assert result.assessment.suggested_action == "keep_scanning"
    assert "remote_context_reference" in result.assessment.reasons
    assert result.assessment.suggested_lookback_messages >= 50


def test_missing_target_requires_user_supplement():
    result = ContextConfidenceAnalyzer().analyze([_msg(1, "@WorkBot 这个不行了，帮我修一下")])

    assert result.assessment.resolution == "needs_user_input"
    assert result.assessment.suggested_action == "ask_user"
    assert "target_object" in result.assessment.missing_fields


def test_demand_radar_candidate_includes_context_assessment():
    candidates = DemandRadar().extract(
        [
            _msg(1, "设置页保存接口 500，页面一直转圈", sender="Tester"),
            _msg(2, "期望保存成功后提示已保存", sender="PM"),
        ]
    )

    assert len(candidates) == 1
    assert candidates[0].context_assessment is not None
    assert candidates[0].context_assessment.suggested_action == "candidate_ready"


def test_context_confidence_api_returns_assessment_and_direct_answer_draft():
    client = TestClient(create_app())

    response = client.post(
        "/context-confidence/analyze",
        json={
            "messages": [
                {
                    "id": "m-1",
                    "chatId": "room-a",
                    "chatName": "项目A工作群",
                    "sender": "PM",
                    "timestamp": BASE_TIME.isoformat(),
                    "text": "@WorkBot FastAPI 的 Depends 是做什么的？",
                    "msgType": "text",
                    "source": "test",
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assessment"]["resolution"] == "self_contained"
    assert body["assessment"]["suggestedAction"] == "direct_answer_ready"
    assert body["directAnswerDraft"]["status"] == "draft"
