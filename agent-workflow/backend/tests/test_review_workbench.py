import json
import sqlite3

from fastapi.testclient import TestClient

import app.api.review_workbench as review_workbench_api
from app.main import create_app


def test_review_workbench_served():
    client = TestClient(create_app())

    response = client.get('/review-workbench')

    assert response.status_code == 200
    assert '需求审查工作台' in response.text
    assert '提取候选需求' in response.text
    assert '提升为草稿' in response.text
    assert '生成审查文档' in response.text
    assert 'reviewDocumentOutput' in response.text
    assert '/message-documents/from-demand-messages' in response.text
    assert '/message-documents/from-candidates' in response.text
    assert 'messages 必须是数组' in response.text
    assert '获取并提取最近 50 条消息' in response.text
    assert '群聊筛选' in response.text
    assert '最近 50 条获取摘要' in response.text
    assert 'latestFetchSummary' in response.text
    assert 'loadingIndicator' in response.text
    assert 'class="spinner"' in response.text
    assert 'withLoading(' in response.text
    assert '正在搜索会话...' in response.text
    assert '正在获取并提取最近 50 条...' in response.text
    assert '/review-workbench/recent-50-stream' in response.text
    assert '/messages?limit=50&order=desc' in response.text
    assert '/demand-radar/extract' in response.text
    assert '/requirement-promotion/promote' in response.text
    assert 'escapeHtml(candidate.title)' in response.text
    assert "split('\\n')" in response.text
    assert "split('\n')" not in response.text
    assert "current+'\\n'" in response.text
    assert "current+'\n'" not in response.text
    assert '/agent-runs/from-workdoc' not in response.text
    assert '/git/' not in response.text


def test_recent_50_messages_can_feed_demand_radar():
    client = TestClient(create_app())
    messages = []
    for index in range(60):
        text = "收到"
        if index == 55:
            text = "设置页保存接口 500，页面一直转圈"
        if index == 56:
            text = "期望保存成功后提示已保存，今天发版前要修"
        messages.append(
            {
                "platform": "mock",
                "room_id": "项目开发群",
                "sender_hash": f"user-{index % 5}",
                "sender_display_name": f"成员{index % 5}",
                "timestamp": f"2026-06-20T10:{index // 60:02d}:{index % 60:02d}+08:00",
                "message_type": "text",
                "text": text,
            }
        )
    import_response = client.post("/messages/import", json={"messages": messages})
    assert import_response.status_code == 200

    latest_response = client.get("/messages", params={"limit": 50, "order": "desc"})
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert len(latest) == 50

    demand_messages = [
        {
            "id": f"chat-{message['id']}",
            "chatId": message["room_id"],
            "chatName": message["room_id"],
            "sender": message["sender_display_name"] or message["sender_hash"],
            "timestamp": message["timestamp"],
            "text": message["text"],
            "msgType": message["message_type"],
            "source": message["platform"],
        }
        for message in latest
    ]
    extract_response = client.post("/demand-radar/extract", json={"messages": demand_messages})

    assert extract_response.status_code == 200
    candidates = extract_response.json()["candidates"]
    assert candidates
    assert candidates[0]["contextAssessment"]["suggestedAction"] == "candidate_ready"


def test_recent_50_stream_returns_progress_events():
    client = TestClient(create_app())
    import_response = client.post(
        "/messages/import",
        json={
            "messages": [
                {
                    "platform": "mock",
                    "room_id": "项目开发群",
                    "sender_hash": "user-1",
                    "sender_display_name": "测试",
                    "timestamp": "2026-06-20T10:00:00+08:00",
                    "message_type": "text",
                    "text": "设置页保存接口 500，页面一直转圈",
                },
                {
                    "platform": "mock",
                    "room_id": "项目开发群",
                    "sender_hash": "user-2",
                    "sender_display_name": "产品",
                    "timestamp": "2026-06-20T10:01:00+08:00",
                    "message_type": "text",
                    "text": "期望保存成功后提示已保存，今天发版前要修",
                },
            ]
        },
    )
    assert import_response.status_code == 200

    response = client.get("/review-workbench/recent-50-stream", params={"room_id": "项目开发群", "extractor": "local"})

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [event["type"] for event in events]
    assert event_types[:2] == ["start", "fetched"]
    assert "message" in event_types
    assert "candidates" in event_types
    assert event_types[-1] == "done"
    assert next(event for event in events if event["type"] == "fetched")["count"] == 2
    assert next(event for event in events if event["type"] == "candidates")["count"] >= 1


def test_recent_50_stream_explains_empty_database():
    client = TestClient(create_app())

    response = client.get("/review-workbench/recent-50-stream")

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert any(event["type"] == "warning" for event in events)
    assert "没有消息" in next(event["message"] for event in events if event["type"] == "warning")


def test_recent_50_stream_imports_from_decrypted_wechat_db(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    micro_msg = decrypted_dir / "de_MicroMsg.db"
    msg_db = decrypted_dir / "de_MSG0.db"
    with sqlite3.connect(micro_msg) as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute(
            "INSERT INTO Contact (UserName, Remark, NickName) VALUES (?, ?, ?)",
            ("12345@chatroom", "项目开发群", ""),
        )
    with sqlite3.connect(msg_db) as conn:
        conn.execute("CREATE TABLE MSG (CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.execute(
            "INSERT INTO MSG (CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?)",
            (1781882400, "12345@chatroom", 0, "设置页保存接口 500，页面一直转圈"),
        )
        conn.execute(
            "INSERT INTO MSG (CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?)",
            (1781882460, "12345@chatroom", 0, "期望保存成功后提示已保存，今天发版前要修"),
        )
    monkeypatch.setattr(review_workbench_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    response = client.get("/review-workbench/recent-50-stream", params={"room_id": "项目开发群", "extractor": "local"})

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [event["type"] for event in events]
    assert "wechat_room_resolved" in event_types
    assert "wechat_db_imported" in event_types
    assert "message" in event_types
    assert next(event for event in events if event["type"] == "wechat_db_imported")["count"] == 2
    assert next(event for event in events if event["type"] == "candidates")["count"] >= 1

    second_response = client.get("/review-workbench/recent-50-stream", params={"room_id": "项目开发群", "extractor": "local"})
    second_events = [json.loads(line) for line in second_response.text.splitlines() if line.strip()]
    assert any(event["type"] == "fetched" and event["count"] == 2 for event in second_events)
    assert next(event for event in second_events if event["type"] == "wechat_db_imported")["count"] == 0


def test_recent_50_stream_requires_selected_conversation_before_database_scan(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    micro_msg = decrypted_dir / "de_MicroMsg.db"
    msg_db = decrypted_dir / "de_MSG0.db"
    with sqlite3.connect(micro_msg) as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
    with sqlite3.connect(msg_db) as conn:
        conn.execute("CREATE TABLE MSG (CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.execute(
            "INSERT INTO MSG (CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?)",
            (1781882460, "12345@chatroom", 0, "自动化工作台需要读取最近 50 条消息"),
        )
    monkeypatch.setattr(review_workbench_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    response = client.get("/review-workbench/recent-50-stream")

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [event["type"] for event in events]
    assert event_types == ["warning", "done"]
    assert "选择" in events[0]["message"]
    assert "wechat_db_read" not in event_types


def test_recent_50_stream_limits_selected_decrypted_wechat_import_to_50(tmp_path, monkeypatch):
    decrypted_dir = tmp_path / "decrypted_wechat"
    decrypted_dir.mkdir()
    micro_msg = decrypted_dir / "de_MicroMsg.db"
    msg_db = decrypted_dir / "de_MSG0.db"
    with sqlite3.connect(micro_msg) as conn:
        conn.execute("CREATE TABLE Contact (UserName TEXT, Remark TEXT, NickName TEXT)")
        conn.execute("CREATE TABLE Session (strUsrName TEXT, strNickName TEXT)")
        conn.execute(
            "INSERT INTO Contact (UserName, Remark, NickName) VALUES (?, ?, ?)",
            ("room-main@chatroom", "主项目群", ""),
        )
    with sqlite3.connect(msg_db) as conn:
        conn.execute("CREATE TABLE MSG (CreateTime INTEGER, StrTalker TEXT, IsSender INTEGER, StrContent TEXT)")
        conn.executemany(
            "INSERT INTO MSG (CreateTime, StrTalker, IsSender, StrContent) VALUES (?, ?, ?, ?)",
            [
                (1781882400 + index, "room-main@chatroom", 0, f"第 {index} 条测试消息")
                for index in range(80)
            ],
        )
    monkeypatch.setattr(review_workbench_api, "DEFAULT_DECRYPTED_WECHAT_DIR", decrypted_dir)
    client = TestClient(create_app())

    response = client.get("/review-workbench/recent-50-stream", params={"room_id": "room-main@chatroom", "extractor": "local"})

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert next(event for event in events if event["type"] == "wechat_db_read")["count"] == 50
    assert next(event for event in events if event["type"] == "wechat_db_imported")["count"] == 50
