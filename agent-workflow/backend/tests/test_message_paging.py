from fastapi.testclient import TestClient

from app.main import create_app


def test_messages_page_uses_cursor_and_caps_limit():
    client = TestClient(create_app())
    messages = [
        {
            "platform": "mock",
            "room_id": "分页测试群",
            "sender_hash": "user-1",
            "sender_display_name": "测试",
            "timestamp": f"2026-06-20T10:00:{index % 60:02d}+08:00",
            "message_type": "text",
            "text": f"第 {index} 条",
        }
        for index in range(250)
    ]
    response = client.post("/messages/import", json={"messages": messages})
    assert response.status_code == 200

    page = client.get("/messages/page", params={"room_id": "分页测试群", "limit": 10000})

    assert page.status_code == 200
    payload = page.json()
    assert len(payload) == 200
    first_id = payload[0]["id"]
    last_id = payload[-1]["id"]
    assert first_id > last_id

    next_page = client.get("/messages/page", params={"room_id": "分页测试群", "before_id": last_id, "limit": 50})

    assert next_page.status_code == 200
    assert len(next_page.json()) == 50
    assert all(item["id"] < last_id for item in next_page.json())
