import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.demand_radar as demand_radar_api
from app.main import create_app
from app.schemas.demand_radar import DemandMessage
from app.services.llm_client import LLMChatResult
from app.services.llm_demand_radar import LLMDemandRadar, clear_llm_demand_cache
from app.services.llm_settings import LLMSettings, get_llm_settings


class FakeLLMClient:
    def __init__(self):
        self.calls = 0
        self.settings = LLMSettings(
            provider="openai_compatible",
            base_url="https://example.test",
            api_key="test-key",
            model="demo-model",
            timeout_seconds=10,
            temperature=0.1,
            max_tokens=100,
            extract_max_messages=60,
            extract_max_chars_per_message=360,
            extract_max_candidates=6,
        )

    def chat_json(self, messages, *, temperature=None, max_tokens=None):
        self.calls += 1
        return LLMChatResult(
            content=json.dumps(
                {
                    "candidates": [
                        {
                            "title": "修复设置页保存接口 500",
                            "requirementType": "bug",
                            "status": "pending_review",
                            "confidence": "high",
                            "confidenceScore": 0.91,
                            "hypothesis": "设置页保存接口返回 500，需要修复并满足保存成功提示。",
                            "evidenceMessageIds": ["m-1", "m-2"],
                            "missingFields": ["project_or_repo"],
                            "facts": [{"text": "保存接口 500", "messageId": "m-1"}],
                            "inferences": [{"text": "需要后端修复", "basisMessageIds": ["m-1", "m-2"]}],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            raw={"choices": []},
        )


def test_llm_demand_radar_normalizes_candidates():
    messages = [
        DemandMessage(
            id="m-1",
            chatId="dev-room",
            chatName="开发群",
            sender="PM",
            timestamp=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
            text="设置页保存接口 500，页面一直转圈",
            msgType="text",
            source="test",
        ),
        DemandMessage(
            id="m-2",
            chatId="dev-room",
            chatName="开发群",
            sender="QA",
            timestamp=datetime(2026, 6, 20, 10, 1, tzinfo=timezone.utc),
            text="期望保存成功后提示已保存",
            msgType="text",
            source="test",
        ),
    ]

    candidates = LLMDemandRadar(client=FakeLLMClient()).extract(messages)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "修复设置页保存接口 500"
    assert candidate.requirement_type == "bug"
    assert candidate.confidence == "high"
    assert candidate.evidence_message_ids == ["m-1", "m-2"]
    assert candidate.evidence[0].text == "设置页保存接口 500，页面一直转圈"
    assert candidate.missing_fields == ["project_or_repo"]


def test_extract_llm_endpoint_uses_llm_extractor(monkeypatch):
    class StubRadar:
        def extract(self, messages):
            return LLMDemandRadar(client=FakeLLMClient()).extract(messages)

    monkeypatch.setattr(demand_radar_api, "LLMDemandRadar", StubRadar)
    client = TestClient(create_app())

    response = client.post(
        "/demand-radar/extract-llm",
        json={
            "messages": [
                {
                    "id": "m-1",
                    "chatId": "dev-room",
                    "chatName": "开发群",
                    "sender": "PM",
                    "timestamp": "2026-06-20T10:00:00+00:00",
                    "text": "设置页保存接口 500，页面一直转圈",
                    "msgType": "text",
                    "source": "test",
                },
                {
                    "id": "m-2",
                    "chatId": "dev-room",
                    "chatName": "开发群",
                    "sender": "QA",
                    "timestamp": "2026-06-20T10:01:00+00:00",
                    "text": "期望保存成功后提示已保存",
                    "msgType": "text",
                    "source": "test",
                },
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"][0]["title"] == "修复设置页保存接口 500"
    assert payload["candidates"][0]["evidenceMessageIds"] == ["m-1", "m-2"]


def test_llm_settings_redacts_key():
    settings = LLMSettings(
        provider="openai_compatible",
        base_url="https://example.test",
        api_key="secret-value",
        model="demo-model",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=100,
        extract_max_messages=60,
        extract_max_chars_per_message=360,
        extract_max_candidates=6,
    )

    redacted = settings.redacted()

    assert redacted["api_key_present"] is True
    assert "secret-value" not in str(redacted)


def test_llm_settings_clamps_invalid_environment_values(monkeypatch):
    monkeypatch.setenv("AGENT_WORKFLOW_LLM_TIMEOUT_SECONDS", "9999")
    monkeypatch.setenv("AGENT_WORKFLOW_LLM_MAX_TOKENS", "1")
    monkeypatch.setenv("AGENT_WORKFLOW_LLM_EXTRACT_MAX_MESSAGES", "0")
    monkeypatch.setenv("AGENT_WORKFLOW_LLM_EXTRACT_MAX_CHARS_PER_MESSAGE", "999999")
    monkeypatch.setenv("AGENT_WORKFLOW_LLM_EXTRACT_MAX_CANDIDATES", "999999")

    settings = get_llm_settings()

    assert settings.timeout_seconds == 180
    assert settings.max_tokens == 256
    assert settings.extract_max_messages == 1
    assert settings.extract_max_chars_per_message == 2000
    assert settings.extract_max_candidates == 20
