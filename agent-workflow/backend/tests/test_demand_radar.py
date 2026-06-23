from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.demand_radar import DemandMessage
from app.services.demand_radar import DemandRadar


BASE_TIME = datetime(2026, 6, 19, 9, 0, tzinfo=timezone.utc)


def _msg(
    idx: int,
    text: str,
    *,
    minute: int | None = None,
    sender: str = "Alice",
    chat_id: str = "room-a",
    chat_name: str = "项目A需求群",
    msg_type: str = "text",
) -> DemandMessage:
    minute = idx if minute is None else minute
    return DemandMessage(
        id=f"m-{idx}",
        chat_id=chat_id,
        chat_name=chat_name,
        sender=sender,
        timestamp=BASE_TIME + timedelta(minutes=minute),
        text=text,
        msg_type=msg_type,
        source="test",
    )


def test_pure_chatter_does_not_create_candidates():
    messages = [_msg(i, text, sender=f"u{i}") for i, text in enumerate(["收到", "好的", "辛苦", "我看看", "1"], 1)]

    candidates = DemandRadar().extract(messages)

    assert candidates == []


def test_single_vague_complaint_is_only_low_confidence_suspect():
    candidates = DemandRadar().extract([_msg(1, "这个东西又不行了", sender="PM")])

    assert len(candidates) == 1
    assert candidates[0].status == "suspect"
    assert candidates[0].confidence in {"low", "medium"}
    assert "target_object" in candidates[0].missing_fields


def test_bug_context_creates_reviewable_candidate_with_evidence_facts_inferences_and_missing_fields():
    messages = [
        _msg(1, "早"),
        _msg(2, "设置页点保存以后接口 500，页面一直转圈", sender="Tester"),
        _msg(3, "日志里是 /api/settings/save 报错，发版前要修一下", sender="Dev"),
        _msg(4, "期望是保存成功后提示已保存，并回到设置页", sender="PM"),
        _msg(5, "收到"),
    ]

    candidates = DemandRadar().extract(messages)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.status == "pending_review"
    assert candidate.requirement_type == "bug"
    assert candidate.confidence == "high"
    assert candidate.evidence_message_ids == ["m-2", "m-3", "m-4"]
    assert candidate.facts
    assert candidate.inferences
    assert candidate.missing_fields
    assert "m-2" in candidate.evidence[0].message_id


def test_feature_request_with_constraints_creates_candidate():
    messages = [
        _msg(1, "工作台这里能不能加一个导入按钮，直接导入聊天 txt", sender="PM"),
        _msg(2, "先只做本地文件，不要接真实微信", sender="PM"),
        _msg(3, "验收：上传后能看到解析出的消息列表", sender="PM"),
    ]

    candidates = DemandRadar().extract(messages)

    assert len(candidates) == 1
    assert candidates[0].requirement_type == "feature"
    assert candidates[0].status == "pending_review"
    assert any("本地文件" in fact.text for fact in candidates[0].facts)


def test_priority_preserves_low_signal_candidate_for_human_review():
    candidates = DemandRadar().extract([_msg(1, "今天发版前把首页入口处理一下，优先", sender="PM")])

    assert len(candidates) == 1
    assert candidates[0].status == "pending_review"
    assert candidates[0].confidence in {"medium", "high"}


def test_artifact_context_creates_candidate():
    messages = [
        _msg(1, "[截图] 首页按钮错位", sender="Tester", msg_type="image"),
        _msg(2, "应该和右侧筛选按钮对齐", sender="PM"),
    ]

    candidates = DemandRadar().extract(messages)

    assert len(candidates) == 1
    assert candidates[0].status == "pending_review"
    assert any(e.role == "artifact" for e in candidates[0].evidence)


def test_termination_marks_candidate_expired():
    messages = [
        _msg(1, "报表导出报错，麻烦看一下", sender="User"),
        _msg(2, "不用改了，是我本地数据没刷新", sender="User"),
    ]

    candidates = DemandRadar().extract(messages)

    assert len(candidates) == 1
    assert candidates[0].status == "expired"


def test_repeated_discussion_is_merged_into_one_candidate():
    messages = [
        _msg(1, "权限页新增用户失败，提示 403", sender="Tester"),
        _msg(2, "我也遇到了，新增用户按钮点了没反应", sender="Dev"),
        _msg(3, "这个今天要修", sender="PM"),
    ]

    candidates = DemandRadar().extract(messages)

    assert len(candidates) == 1
    assert candidates[0].evidence_message_ids == ["m-1", "m-2", "m-3"]


def test_api_extract_returns_candidates_without_creating_workdoc_or_agent_run():
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/demand-radar/extract",
        json={
            "messages": [
                {
                    "id": "m-1",
                    "chatId": "room-a",
                    "chatName": "项目A需求群",
                    "sender": "PM",
                    "timestamp": BASE_TIME.isoformat(),
                    "text": "看板页需要加一个按负责人筛选，验收是选人后列表只显示对应任务",
                    "msgType": "text",
                    "source": "test",
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["status"] == "pending_review"
    assert "workdoc_id" not in body["candidates"][0]
    assert "agent_run_id" not in body["candidates"][0]


def test_100_mixed_messages_produce_small_reviewable_candidate_set():
    messages: list[DemandMessage] = []
    demand_text_by_minute = {
        10: "设置页保存接口 500，页面一直转圈，发版前要修",
        11: "期望保存成功后提示已保存",
        35: "工作台需要加一个导入聊天记录按钮",
        36: "先只支持本地 txt，验收是能看到解析结果",
        60: "权限页新增用户失败，提示 403，今天发版前要修",
        61: "这个今天要修，影响演示",
        85: "报表导出文件名不对，应该带日期",
        86: "不用改了，是测试数据问题",
    }
    filler = ["收到", "好的", "我看看", "午饭订了吗", "这个后面再聊"]
    for minute in range(100):
        text = demand_text_by_minute.get(minute, filler[minute % len(filler)])
        messages.append(_msg(minute + 1, text, minute=minute, sender=f"u{minute % 6}"))

    candidates = DemandRadar().extract(messages)

    assert 3 <= len(candidates) <= 8
    assert [candidate.status for candidate in candidates].count("pending_review") >= 3
    assert any(candidate.status == "expired" for candidate in candidates)
    for candidate in candidates:
        assert candidate.evidence_message_ids
        assert candidate.facts
        assert candidate.inferences
        assert candidate.confidence in {"low", "medium", "high"}


def test_demo_page_is_available_in_chinese():
    app = create_app()
    client = TestClient(app)

    response = client.get("/demand-radar/demo")

    assert response.status_code == 200
    assert "需求雷达" in response.text
    assert "运行提取" in response.text
    assert "WorkDoc 草稿预览" in response.text
    assert "Agent 输入包预览" in response.text
    assert "Agent Brief Markdown" in response.text
    assert "判断上下文" in response.text
    assert "上下文置信度预览" in response.text
