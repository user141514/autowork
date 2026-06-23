from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.demand_radar import DemandMessage
from app.schemas.message_document import MessageReviewDocumentRequest
from app.services.message_document_service import MessageReviewDocumentService


def _sample_messages():
    return [
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
            "text": "期望保存成功后提示已保存，今天发版前要修",
            "msgType": "text",
            "source": "test",
        },
    ]


def test_message_document_endpoint_builds_review_markdown():
    client = TestClient(create_app())

    response = client.post(
        "/message-documents/from-demand-messages",
        json={"extractor": "local", "messages": _sample_messages()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reviewDocumentId"].startswith("review_")
    assert payload["sourceMessageCount"] == 2
    assert payload["candidateCount"] >= 1
    assert "## 3. 候选需求" in payload["markdown"]
    assert "## 4. 人工确认填写区" in payload["markdown"]
    assert "not authorized for AgentRun or Git" in payload["markdown"]
    assert "/agent-runs" not in payload["markdown"]
    assert "/git/" not in payload["markdown"]


def test_message_document_service_writes_markdown_file(tmp_path):
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
            text="期望保存成功后提示已保存，今天发版前要修",
            msgType="text",
            source="test",
        ),
    ]
    request = MessageReviewDocumentRequest(messages=messages, extractor="local", writeDocument=True)

    result = MessageReviewDocumentService(output_root=tmp_path).build(request)

    assert result.document_path is not None
    path = tmp_path / f"{result.review_document_id}.md"
    assert path.exists()
    assert path.read_text(encoding="utf-8") == result.markdown


def test_message_document_empty_batch_is_stable():
    client = TestClient(create_app())

    response = client.post(
        "/message-documents/from-demand-messages",
        json={"extractor": "local", "messages": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidateCount"] == 0
    assert "message batch is empty" in payload["warnings"]
    assert "no candidate requirements extracted" in payload["warnings"]
    assert "未提取到候选需求" in payload["markdown"]


def test_message_document_from_candidates_reuses_existing_candidates_and_escapes_markdown():
    client = TestClient(create_app())
    first = client.post(
        "/message-documents/from-demand-messages",
        json={"extractor": "local", "messages": _sample_messages()},
    )
    assert first.status_code == 200
    candidate = first.json()["candidates"][0]
    candidate["title"] = "# 标题 `code` <tag>"
    candidate["hypothesis"] = "需要处理 `code` <tag>"
    candidate["evidence"][0]["text"] = "`raw` <xml>" + "x" * 800

    response = client.post(
        "/message-documents/from-candidates",
        json={"messages": _sample_messages(), "candidates": [candidate], "writeDocument": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["extractor"] == "provided"
    assert payload["candidateCount"] == 1
    assert "# 标题" not in payload["markdown"]
    assert "\\`code\\`" in payload["markdown"]
    assert "&lt;tag&gt;" in payload["markdown"]
    assert len(payload["markdown"]) < 8000
