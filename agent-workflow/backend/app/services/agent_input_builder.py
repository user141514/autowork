from datetime import timezone

from app.models.chat_message import ChatMessage


def build_agent_input(messages: list[ChatMessage]) -> str:
    if not messages:
        return "# 新消息批次\n\n来源聊天：\n时间范围： - \n\n## 消息列表\n\n## 任务抽取要求\n\n请从以上消息中识别：\n1. 新派发任务\n2. 任务负责人\n3. 截止时间\n4. 所需输入材料\n5. 可直接交给代码智能体执行的提示词\n"

    room_id = messages[0].room_id
    start = _iso_timestamp(messages[0])
    end = _iso_timestamp(messages[-1])
    lines = [
        "# 新消息批次",
        "",
        f"来源聊天：{room_id}",
        f"时间范围：{start} - {end}",
        "",
        "## 消息列表",
        "",
    ]
    for message in messages:
        sender = message.sender_display_name or message.sender_hash or "未知"
        lines.append(f"- [{_iso_timestamp(message)}] {sender}：{message.text}")
    lines.extend(
        [
            "",
            "## 任务抽取要求",
            "",
            "请从以上消息中识别：",
            "1. 新派发任务",
            "2. 任务负责人",
            "3. 截止时间",
            "4. 所需输入材料",
            "5. 可直接交给代码智能体执行的提示词",
            "",
        ]
    )
    return "\n".join(lines)


def _iso_timestamp(message: ChatMessage) -> str:
    timestamp = message.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.isoformat()
