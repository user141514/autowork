from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Protocol

from sqlalchemy import func, select


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.chat.wxauto_adapter import PersonalWeChatAdapter
from app.config import Settings, get_settings
from app.database import SessionLocal, init_db
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate
from app.services.bot_command_service import BotCommandService
from app.services.message_store import MessageStore, source_message_fingerprint


LOGGER = logging.getLogger("wechat-poller")


class ChatPoller(Protocol):
    def fetch_recent(self, room_id: str, limit: int | None = None) -> list[ChatMessageCreate]:
        ...


@dataclass
class NewMessageSummary:
    id: int
    room_id: str
    sender: str
    timestamp: str
    text: str
    is_workbot_command: bool


@dataclass
class PollStats:
    room_count: int = 0
    fetched_count: int = 0
    imported_count: int = 0
    command_count: int = 0
    new_messages: list[NewMessageSummary] = field(default_factory=list)
    prompt_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll whitelisted WeChat groups through wxauto and save messages to SQLite.",
    )
    parser.add_argument(
        "--interval",
        type=_non_negative_int,
        default=30,
        help="Polling interval in seconds. Use 0 to run once and exit.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one polling cycle and exit.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Max messages to read per room per poll. Defaults to AGENT_WORKFLOW_WECHAT_READ_LIMIT.",
    )
    parser.add_argument(
        "--rooms",
        type=_csv_list,
        default=None,
        help="Comma-separated room names. Defaults to AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS.",
    )
    parser.add_argument(
        "--resolve-rooms",
        action="store_true",
        help="Resolve fuzzy room names against the wxauto session list and prompt when multiple matches exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and log messages without writing to the database.",
    )
    parser.add_argument(
        "--since",
        type=_since_datetime,
        default=None,
        help='Only process messages at or after this time, e.g. "2026-06-19 10:30". Naive values are treated as UTC.',
    )
    parser.add_argument(
        "--show-new",
        action="store_true",
        help="Print newly imported messages each poll.",
    )
    parser.add_argument(
        "--write-agent-prompts",
        dest="prompt_dir",
        type=Path,
        default=None,
        help="Write prompt draft markdown files for newly imported @WorkBot messages.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Log level.",
    )
    args = parser.parse_args(argv)
    if args.once:
        args.interval = 0
    return args


def poll_once(
    adapter: ChatPoller,
    settings: Settings,
    db,
    limit: int,
    dry_run: bool,
    rooms: list[str] | None = None,
    since: datetime | None = None,
    show_new: bool = False,
    prompt_dir: Path | None = None,
) -> PollStats:
    selected_rooms = rooms if rooms is not None else list(settings.wechat_whitelist_rooms)
    stats = PollStats(room_count=len(selected_rooms))
    new_message_ids: list[int] = []

    for room_id in selected_rooms:
        try:
            messages = adapter.fetch_recent(room_id, limit)
        except Exception as exc:
            message = f"{room_id}: {exc}"
            LOGGER.exception("Failed to fetch room %s", room_id)
            stats.errors.append(message)
            continue

        stats.fetched_count += len(messages)
        filtered_messages = _filter_since(messages, since)
        if len(messages) >= limit:
            LOGGER.warning("Room %s returned %s messages, at the configured read limit", room_id, len(messages))
        if dry_run:
            LOGGER.info("Dry run: fetched %s messages from %s, %s after filters", len(messages), room_id, len(filtered_messages))
            continue

        existing_fingerprints = _existing_fingerprints(db, filtered_messages)
        before_count = _chat_message_count(db)
        saved_messages = MessageStore(db).import_messages(filtered_messages)
        after_count = _chat_message_count(db)
        stats.imported_count += max(0, after_count - before_count)
        new_messages = [
            message
            for message in saved_messages
            if message.source_message_fingerprint not in existing_fingerprints
        ]
        stats.new_messages.extend(_summarize_message(message) for message in new_messages)
        new_message_ids.extend(message.id for message in new_messages)
        if show_new:
            for message in new_messages:
                LOGGER.info("New message: %s", format_new_message(message))
        if prompt_dir is not None:
            for message in new_messages:
                prompt_path = write_agent_prompt_draft(message, prompt_dir)
                if prompt_path is not None:
                    stats.prompt_paths.append(str(prompt_path))

    if not dry_run:
        command_logs = BotCommandService(db).process_new_messages(new_message_ids)
        stats.command_count = len(command_logs)

    return stats


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    limit = args.limit or settings.wechat_read_limit
    rooms = args.rooms if args.rooms is not None else list(settings.wechat_whitelist_rooms)
    if not rooms:
        LOGGER.error("No whitelisted rooms configured. Set AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS or pass --rooms.")
        return 2
    if not settings.personal_wechat_enabled and not args.dry_run:
        LOGGER.error("Personal WeChat is disabled. Set AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED=true.")
        return 2

    init_db()
    adapter = PersonalWeChatAdapter(whitelist_rooms=rooms)
    if args.resolve_rooms:
        try:
            rooms = resolve_room_inputs(adapter, rooms, input_func=input, output_func=print)
        except KeyboardInterrupt:
            LOGGER.error("Room selection cancelled.")
            return 130
        adapter = PersonalWeChatAdapter(whitelist_rooms=rooms)
    should_stop = _StopFlag()
    signal.signal(signal.SIGINT, should_stop.handle)
    signal.signal(signal.SIGTERM, should_stop.handle)

    while not should_stop.value:
        with SessionLocal() as db:
            stats = poll_once(
                adapter,
                settings,
                db,
                limit=limit,
                dry_run=args.dry_run,
                rooms=rooms,
                since=args.since,
                show_new=args.show_new,
                prompt_dir=args.prompt_dir,
            )
        LOGGER.info(
            "Poll complete: rooms=%s fetched=%s imported=%s commands=%s errors=%s",
            stats.room_count,
            stats.fetched_count,
            stats.imported_count,
            stats.command_count,
            len(stats.errors),
        )
        if args.interval <= 0:
            break
        should_stop.wait(args.interval)
    return 0


class _StopFlag:
    def __init__(self) -> None:
        self.value = False

    def handle(self, _signum: int, _frame: FrameType | None) -> None:
        self.value = True

    def wait(self, seconds: int) -> None:
        deadline = time.monotonic() + seconds
        while not self.value and time.monotonic() < deadline:
            time.sleep(min(0.5, deadline - time.monotonic()))


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def resolve_room_inputs(
    adapter: PersonalWeChatAdapter,
    rooms: list[str],
    input_func=input,
    output_func=print,
) -> list[str]:
    resolved_rooms: list[str] = []
    for room in rooms:
        candidates = adapter.room_candidates(room)
        if not candidates:
            output_func(f"No wxauto session candidates found for '{room}'. Keeping the original input.")
            resolved_rooms.append(room)
            continue
        if len(candidates) == 1:
            output_func(f"Resolved '{room}' -> '{candidates[0]}'")
            resolved_rooms.append(candidates[0])
            continue
        output_func("")
        output_func(f"Multiple wxauto sessions match '{room}':")
        for index, candidate in enumerate(candidates, start=1):
            output_func(f"  [{index}] {candidate}")
        selected = _prompt_room_choice(room, candidates, input_func=input_func, output_func=output_func)
        output_func(f"Resolved '{room}' -> '{selected}'")
        resolved_rooms.append(selected)
    return resolved_rooms


def _prompt_room_choice(room: str, candidates: list[str], input_func=input, output_func=print) -> str:
    while True:
        answer = input_func(f"Select room for '{room}' [1-{len(candidates)}]: ").strip()
        try:
            selected_index = int(answer)
        except ValueError:
            output_func("Please enter a number from the list.")
            continue
        if 1 <= selected_index <= len(candidates):
            return candidates[selected_index - 1]
        output_func("Selection out of range.")


def _since_datetime(value: str) -> datetime:
    normalized = value.strip().replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an ISO-like datetime, e.g. 2026-06-19 10:30") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be 0 or greater")
    return parsed


def _chat_message_count(db) -> int:
    return int(db.scalar(select(func.count()).select_from(ChatMessage)) or 0)


def _filter_since(messages: list[ChatMessageCreate], since: datetime | None) -> list[ChatMessageCreate]:
    if since is None:
        return messages
    since_utc = since.astimezone(timezone.utc)
    filtered_messages = [
        message
        for message in messages
        if message.timestamp is not None and _as_utc(message.timestamp) >= since_utc
    ]
    skipped_unknown = sum(1 for message in messages if message.timestamp is None)
    if skipped_unknown:
        LOGGER.warning("Skipped %s messages with unknown timestamps because --since is active", skipped_unknown)
    return filtered_messages


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _existing_fingerprints(db, messages: list[ChatMessageCreate]) -> set[str]:
    fingerprints = {
        message.source_message_fingerprint or source_message_fingerprint(message)
        for message in messages
    }
    if not fingerprints:
        return set()
    return set(
        db.scalars(
            select(ChatMessage.source_message_fingerprint).where(
                ChatMessage.source_message_fingerprint.in_(fingerprints)
            )
        )
    )


def format_new_message(message: ChatMessage) -> str:
    timestamp = message.timestamp.isoformat() if message.timestamp else "unknown-time"
    sender = message.sender_display_name or message.sender_hash
    text = " ".join((message.text or "").split())
    if len(text) > 120:
        text = text[:117] + "..."
    mention = " @WorkBot" if get_settings().workbot_mention in (message.text or "") else ""
    return f"[{timestamp}] {message.room_id} {sender}{mention}: {text}"


def _summarize_message(message: ChatMessage) -> NewMessageSummary:
    return NewMessageSummary(
        id=message.id,
        room_id=message.room_id,
        sender=message.sender_display_name or message.sender_hash,
        timestamp=message.timestamp.isoformat() if message.timestamp else "unknown-time",
        text=message.text or "",
        is_workbot_command=get_settings().workbot_mention in (message.text or ""),
    )


def write_agent_prompt_draft(message: ChatMessage, prompt_dir: Path) -> Path | None:
    if get_settings().workbot_mention not in (message.text or ""):
        return None
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"workbot-message-{message.id}.md"
    prompt_path.write_text(_agent_prompt_content(message), encoding="utf-8")
    return prompt_path


def _agent_prompt_content(message: ChatMessage) -> str:
    timestamp = message.timestamp.isoformat() if message.timestamp else "unknown"
    sender = message.sender_display_name or message.sender_hash
    return f"""# Agent Prompt Draft

这是从微信白名单群监控中生成的 Agent 输入草稿。

## 安全边界

- 不要直接运行 Agent。
- 不要直接修改代码。
- 不要直接执行 Git 操作。
- 先把需求转成 WorkDoc，并等待人工校验和审批。

## 来源

- 群聊：{message.room_id}
- 发送者：{sender}
- 时间：{timestamp}
- 消息 ID：{message.id}

## 原始消息

```text
{message.text}
```

## 下一步

请基于这条消息整理：

1. 问题摘要
2. 预期行为
3. 验收标准
4. 可能涉及的项目候选
5. 需要人工补充的问题
"""


if __name__ == "__main__":
    raise SystemExit(main())
