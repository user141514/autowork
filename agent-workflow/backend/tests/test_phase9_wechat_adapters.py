from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.chat.wxauto_adapter import WxautoAdapter
from app.config import get_settings
from app.main import create_app


def test_manual_export_import_and_workbot_candidate_flow(tmp_path: Path) -> None:
    export_file = tmp_path / "chat.txt"
    export_file.write_text(
        "首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。\n@WorkBot 记录为任务\n",
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        imported = client.post(
            "/wechat/manual-export/import",
            json={"file_path": str(export_file), "room_id": "dev-group"},
        )
        assert imported.status_code == 200
        payload = imported.json()
        assert len(payload) == 2
        normal_id, command_id = payload[0]["id"], payload[1]["id"]

        ordinary_command = client.post("/bot/command", json={"message_id": normal_id})
        assert ordinary_command.status_code == 409

        command_log = client.post("/bot/command", json={"message_id": command_id})
        assert command_log.status_code == 200
        assert command_log.json()["command_type"] == "record_task"

        normal_segment = client.post("/segments/from-messages", json={"message_ids": [normal_id]})
        assert normal_segment.status_code == 200
        rejected = client.post("/task-candidates/from-segment", json={"segment_id": normal_segment.json()["id"]})
        assert rejected.status_code == 409
        assert "@WorkBot" in rejected.json()["detail"]

        segment = client.post("/segments/from-command/" + str(command_id), json={"context_window_size": 2})
        assert segment.status_code == 200
        assert normal_id in segment.json()["message_ids"]
        candidate = client.post(f"/task-candidates/from-segment/{segment.json()['id']}")
        assert candidate.status_code == 200
        assert candidate.json()["command_text"].startswith("首页设置按钮")
        assert candidate.json()["status"] == "NEED_CLARIFICATION"
        assert "repo_path" in candidate.json()["missing_fields"]
        assert "acceptance_criteria" in candidate.json()["missing_fields"]

        blocked = client.post(f"/task-candidates/{candidate.json()['id']}/convert-to-workdoc")
        assert blocked.status_code == 409

        updated = client.post(
            f"/task-candidates/{candidate.json()['id']}/update",
            json={"repo_path": "F:\\tmp\\phase9-demo-repo", "acceptance_criteria": ["点击设置按钮后跳转到 /settings"]},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "READY_FOR_WORKDOC"

        workdoc = client.post(f"/task-candidates/{candidate.json()['id']}/convert-to-workdoc")
        assert workdoc.status_code == 200
        assert workdoc.json()["status"] == "WORKDOC_DRAFTED"
        assert workdoc.json()["acceptance_criteria"]
        converted = client.get(f"/task-candidates/{candidate.json()['id']}")
        assert converted.json()["status"] == "CONVERTED_TO_WORKDOC"
        assert converted.json()["workdoc_id"] == workdoc.json()["id"]


def test_personal_wechat_messages_cannot_create_workdoc_directly() -> None:
    with TestClient(create_app()) as client:
        imported = client.post(
            "/messages/import",
            json={
                "messages": [
                    {
                        "platform": "personal_wechat",
                        "room_id": "dev-group",
                        "text": "@WorkBot 设置按钮应该跳转到 /settings。",
                    }
                ]
            },
        )
        message_id = imported.json()[0]["id"]

        direct = client.post("/workdocs/from-messages", json={"message_ids": [message_id]})
        assert direct.status_code == 409
        assert "Segment and TaskCandidate" in direct.json()["detail"]


def test_wxauto_adapter_uses_whitelist_and_maps_messages(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED", "true")
    monkeypatch.setenv("AGENT_WORKFLOW_WECHAT_SEND_ENABLED", "true")
    get_settings.cache_clear()

    class FakeWechat:
        def __init__(self) -> None:
            self.chat_with = None
            self.sent = []

        def ChatWith(self, room_id: str) -> None:
            self.chat_with = room_id

        def GetAllMessage(self):
            return [
                {"sender": "Alice", "content": "普通消息"},
                {"sender": "Bob", "content": "@WorkBot 设置按钮应该跳转到 /settings。"},
            ]

        def SendMsg(self, text: str, who: str | None = None) -> None:
            self.sent.append((who, text))

    fake = FakeWechat()
    adapter = WxautoAdapter(whitelist_rooms=("dev-group",))
    adapter._wechat = fake

    messages = adapter.read_recent_messages("dev-group", limit=1)
    assert len(messages) == 1
    assert messages[0].platform == "personal_wechat"
    assert messages[0].room_id == "dev-group"
    assert "@WorkBot" in messages[0].text

    adapter.send_message("dev-group", "done")
    assert fake.sent == [("dev-group", "done")]

    try:
        adapter.read_recent_messages("private-chat", limit=1)
    except Exception as exc:
        assert "WECHAT_ROOM_NOT_ALLOWED" in str(exc)
    else:
        raise AssertionError("non-whitelisted room should be blocked")
    finally:
        get_settings.cache_clear()


def test_deduplication_and_feedback_mock(tmp_path: Path) -> None:
    export_file = tmp_path / "chat.csv"
    export_file.write_text("sender,text\nAlice,@WorkBot 设置按钮应该跳转到 /settings。\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        first = client.post(
            "/wechat/manual-export/import",
            json={"file_path": str(export_file), "room_id": "dev-group"},
        )
        second = client.post(
            "/wechat/manual-export/import",
            json={"file_path": str(export_file), "room_id": "dev-group"},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()[0]["id"] == second.json()[0]["id"]
        assert first.json()[0]["source_message_fingerprint"]

        segment = client.post("/segments/from-messages", json={"message_ids": [first.json()[0]["id"]]})
        candidate = client.post("/task-candidates/from-segment", json={"segment_id": segment.json()["id"]}).json()
        feedback = client.post(
            f"/chat-feedback/task-candidate/{candidate['id']}",
            json={"room_id": "dev-group", "adapter_type": "mock"},
        )
        assert feedback.status_code == 200
        assert feedback.json()["status"] == "sent_mock"


def test_wechat_disabled_health_and_poll_blocked() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/wechat/health")
        assert health.status_code == 200
        assert health.json()["enabled"] is False
        assert health.json()["error_code"] == "PERSONAL_WECHAT_DISABLED"

        poll = client.post("/wechat/poll-room", json={"room_id": "dev-group"})
        assert poll.status_code == 403
        assert "PERSONAL_WECHAT_DISABLED" in poll.json()["detail"]

        db_import = client.post("/wechat/local-db/import", json={"path": "F:\\WeChat Files"})
        assert db_import.status_code == 403
        assert "not implemented" in db_import.json()["detail"]
