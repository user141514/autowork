from pathlib import Path
import importlib.util
import sys
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.adapters.chat.wxauto_adapter import WxautoAdapter
from app.config import get_settings
from app.database import SessionLocal
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


def test_wxauto_adapter_resolves_room_by_whitelisted_substring(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED", "true")
    get_settings.cache_clear()

    class FakeWechat:
        def __init__(self) -> None:
            self.chat_with = None

        def GetSessionList(self):
            return ["Alice, Bob, Carol", "Ops Team"]

        def ChatWith(self, room_id: str) -> None:
            self.chat_with = room_id

        def GetAllMessage(self):
            return [{"sender": "Alice", "content": "@WorkBot fix login"}]

    fake = FakeWechat()
    adapter = WxautoAdapter(whitelist_rooms=("Bob",))
    adapter._wechat = fake

    try:
        messages = adapter.read_recent_messages("Bob", limit=20)

        assert fake.chat_with == "Alice, Bob, Carol"
        assert messages[0].room_id == "Alice, Bob, Carol"
    finally:
        get_settings.cache_clear()


def test_wxauto_adapter_rejects_ambiguous_room_substring(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED", "true")
    get_settings.cache_clear()

    class FakeWechat:
        def GetSessionList(self):
            return ["Alice, Bob, Carol", "Bob, Dave"]

    adapter = WxautoAdapter(whitelist_rooms=("Bob",))
    adapter._wechat = FakeWechat()

    try:
        adapter.read_recent_messages("Bob", limit=20)
    except Exception as exc:
        assert "WECHAT_ROOM_MATCH_AMBIGUOUS" in str(exc)
    else:
        raise AssertionError("ambiguous substring match should be rejected")
    finally:
        get_settings.cache_clear()


def test_wxauto_adapter_fingerprints_identical_batch_messages(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED", "true")
    get_settings.cache_clear()

    class FakeWechat:
        def ChatWith(self, room_id: str) -> None:
            self.room_id = room_id

        def GetAllMessage(self):
            return [
                {"sender": "Alice", "content": "@WorkBot status WD-1"},
                {"sender": "Alice", "content": "@WorkBot status WD-1"},
            ]

    adapter = WxautoAdapter(whitelist_rooms=("dev-group",))
    adapter._wechat = FakeWechat()

    try:
        messages = adapter.read_recent_messages("dev-group", limit=20)
        repeated = adapter.read_recent_messages("dev-group", limit=20)

        assert len(messages) == 2
        assert messages[0].source_message_fingerprint
        assert messages[1].source_message_fingerprint
        assert messages[0].source_message_fingerprint != messages[1].source_message_fingerprint
        assert [item.source_message_fingerprint for item in messages] == [
            item.source_message_fingerprint for item in repeated
        ]
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


def test_wechat_poller_imports_messages_and_processes_workbot_commands() -> None:
    module = _load_poller_module()

    class FakeAdapter:
        def fetch_recent(self, room_id: str, limit: int):
            assert room_id == "dev-group"
            assert limit == 20
            return [
                module.ChatMessageCreate(platform="personal_wechat", room_id=room_id, text="ordinary chat"),
                module.ChatMessageCreate(
                    platform="personal_wechat",
                    room_id=room_id,
                    text="@WorkBot record task",
                ),
            ]

    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": ("dev-group",)})
    with SessionLocal() as db:
        stats = module.poll_once(FakeAdapter(), settings, db, limit=20, dry_run=False)

    assert stats.room_count == 1
    assert stats.fetched_count == 2
    assert stats.imported_count == 2
    assert stats.command_count == 1
    assert stats.errors == []


def test_wechat_poller_dry_run_does_not_write_database() -> None:
    module = _load_poller_module()

    class FakeAdapter:
        def fetch_recent(self, room_id: str, limit: int):
            return [module.ChatMessageCreate(platform="personal_wechat", room_id=room_id, text="@WorkBot record task")]

    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": ("dev-group",)})
    with SessionLocal() as db:
        stats = module.poll_once(FakeAdapter(), settings, db, limit=20, dry_run=True)

    with TestClient(create_app()) as client:
        messages = client.get("/messages")
        commands = client.get("/bot/commands")

    assert stats.room_count == 1
    assert stats.fetched_count == 1
    assert stats.imported_count == 0
    assert stats.command_count == 0
    assert messages.json() == []
    assert commands.json() == []


def test_wechat_poller_imported_count_excludes_duplicates() -> None:
    module = _load_poller_module()

    class FakeAdapter:
        def fetch_recent(self, room_id: str, limit: int):
            return [module.ChatMessageCreate(platform="personal_wechat", room_id=room_id, text="@WorkBot record task")]

    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": ("dev-group",)})
    with SessionLocal() as db:
        first = module.poll_once(FakeAdapter(), settings, db, limit=20, dry_run=False)
        second = module.poll_once(FakeAdapter(), settings, db, limit=20, dry_run=False)

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.command_count == 0


def test_wechat_poller_parse_args_once_sets_interval_zero() -> None:
    module = _load_poller_module()

    args = module.parse_args(["--once", "--dry-run", "--rooms", "dev-group,ops-group"])

    assert args.interval == 0
    assert args.dry_run is True
    assert args.rooms == ["dev-group", "ops-group"]


def test_wechat_poller_rejects_negative_limit() -> None:
    module = _load_poller_module()

    try:
        module.parse_args(["--limit", "-5"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("negative --limit should be rejected")


def test_wechat_poller_since_filters_old_messages() -> None:
    module = _load_poller_module()

    class FakeAdapter:
        def fetch_recent(self, room_id: str, limit: int):
            return [
                module.ChatMessageCreate(
                    platform="personal_wechat",
                    room_id=room_id,
                    text="@WorkBot old task",
                    timestamp=datetime(2026, 6, 19, 9, 59, tzinfo=timezone.utc),
                ),
                module.ChatMessageCreate(
                    platform="personal_wechat",
                    room_id=room_id,
                    text="@WorkBot new task",
                    timestamp=datetime(2026, 6, 19, 10, 1, tzinfo=timezone.utc),
                ),
            ]

    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": ("dev-group",)})
    with SessionLocal() as db:
        stats = module.poll_once(
            FakeAdapter(),
            settings,
            db,
            limit=20,
            dry_run=False,
            since=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
            show_new=True,
        )

    assert stats.fetched_count == 2
    assert stats.imported_count == 1
    assert len(stats.new_messages) == 1
    assert stats.new_messages[0].text == "@WorkBot new task"
    assert stats.command_count == 1


def test_wechat_poller_since_skips_messages_without_timestamps() -> None:
    module = _load_poller_module()

    class FakeAdapter:
        def fetch_recent(self, room_id: str, limit: int):
            return [
                module.ChatMessageCreate(
                    platform="personal_wechat",
                    room_id=room_id,
                    text="@WorkBot unknown time",
                    timestamp=None,
                )
            ]

    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": ("dev-group",)})
    with SessionLocal() as db:
        stats = module.poll_once(
            FakeAdapter(),
            settings,
            db,
            limit=20,
            dry_run=False,
            since=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
        )

    assert stats.fetched_count == 1
    assert stats.imported_count == 0
    assert stats.new_messages == []
    assert stats.command_count == 0


def test_wechat_poller_only_processes_commands_imported_this_cycle() -> None:
    module = _load_poller_module()

    class FakeAdapter:
        def fetch_recent(self, room_id: str, limit: int):
            return [module.ChatMessageCreate(platform="personal_wechat", room_id=room_id, text="ordinary chat")]

    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": ("dev-group",)})
    with SessionLocal() as db:
        module.MessageStore(db).import_messages(
            [module.ChatMessageCreate(platform="personal_wechat", room_id="dev-group", text="@WorkBot old backlog")]
        )
        stats = module.poll_once(FakeAdapter(), settings, db, limit=20, dry_run=False)

    assert stats.imported_count == 1
    assert len(stats.new_messages) == 1
    assert stats.command_count == 0


def test_wechat_poller_writes_agent_prompt_drafts_for_new_workbot_messages(tmp_path: Path) -> None:
    module = _load_poller_module()

    class FakeAdapter:
        def fetch_recent(self, room_id: str, limit: int):
            return [
                module.ChatMessageCreate(platform="personal_wechat", room_id=room_id, text="ordinary chat"),
                module.ChatMessageCreate(platform="personal_wechat", room_id=room_id, text="@WorkBot fix settings"),
            ]

    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": ("dev-group",)})
    with SessionLocal() as db:
        stats = module.poll_once(
            FakeAdapter(),
            settings,
            db,
            limit=20,
            dry_run=False,
            show_new=True,
            prompt_dir=tmp_path,
        )

    assert len(stats.new_messages) == 2
    assert len(stats.prompt_paths) == 1
    prompt_path = Path(stats.prompt_paths[0])
    assert prompt_path.exists()
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "@WorkBot fix settings" in prompt
    assert "dev-group" in prompt
    assert "不要直接运行 Agent" in prompt


def test_wechat_poller_parse_args_accepts_since_show_new_and_prompt_dir() -> None:
    module = _load_poller_module()

    args = module.parse_args(
        [
            "--since",
            "2026-06-19 10:30",
            "--show-new",
            "--write-agent-prompts",
            ".agent-work/prompts",
        ]
    )

    assert args.since == datetime(2026, 6, 19, 10, 30, tzinfo=timezone.utc)
    assert args.show_new is True
    assert args.prompt_dir == Path(".agent-work/prompts")


def _load_poller_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "poll_wechat_messages.py"
    spec = importlib.util.spec_from_file_location("poll_wechat_messages", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
