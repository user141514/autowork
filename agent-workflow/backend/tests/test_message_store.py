from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import create_app
from app.schemas.chat_message import ChatMessageCreate
from app.services.message_store import MessageStore


def test_message_import_keeps_same_minute_distinct_messages_when_seconds_differ():
    client = TestClient(create_app())

    response = client.post(
        "/messages/import",
        json={
            "messages": [
                {
                    "platform": "mock",
                    "room_id": "dedupe-room",
                    "sender_hash": "user-1",
                    "timestamp": "2026-06-20T10:00:01+00:00",
                    "message_type": "text",
                    "text": "重复文本",
                },
                {
                    "platform": "mock",
                    "room_id": "dedupe-room",
                    "sender_hash": "user-1",
                    "timestamp": "2026-06-20T10:00:02+00:00",
                    "message_type": "text",
                    "text": "重复文本",
                },
            ]
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["id"] != response.json()[1]["id"]


def test_message_import_reuses_identical_fingerprint_inside_batch():
    client = TestClient(create_app())
    message = {
        "platform": "mock",
        "room_id": "dedupe-room",
        "sender_hash": "user-1",
        "timestamp": "2026-06-20T10:00:01+00:00",
        "message_type": "text",
        "text": "同一条消息",
    }

    response = client.post("/messages/import", json={"messages": [message, message]})

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["id"] == response.json()[1]["id"]


def test_message_import_without_timestamp_has_stable_fingerprint():
    client = TestClient(create_app())
    message = {
        "platform": "mock",
        "room_id": "dedupe-room",
        "sender_hash": "user-1",
        "message_type": "text",
        "text": "无时间消息",
    }

    first = client.post("/messages/import", json={"messages": [message]})
    second = client.post("/messages/import", json={"messages": [message]})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()[0]["id"] == second.json()[0]["id"]


def test_message_import_result_reports_inserted_and_reused_counts():
    message = ChatMessageCreate(
        platform="mock",
        room_id="result-room",
        sender_hash="user-1",
        message_type="text",
        text="统计导入结果",
    )
    with SessionLocal() as db:
        store = MessageStore(db)
        first = store.import_messages_with_result([message, message])
        second = store.import_messages_with_result([message])

    assert first.inserted_count == 1
    assert first.reused_count == 1
    assert second.inserted_count == 0
    assert second.reused_count == 1
