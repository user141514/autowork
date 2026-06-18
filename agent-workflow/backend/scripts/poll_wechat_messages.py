from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
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
from app.services.message_store import MessageStore


LOGGER = logging.getLogger("wechat-poller")


class ChatPoller(Protocol):
    def fetch_recent(self, room_id: str, limit: int | None = None) -> list[ChatMessageCreate]:
        ...


@dataclass
class PollStats:
    room_count: int = 0
    fetched_count: int = 0
    imported_count: int = 0
    command_count: int = 0
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
        "--dry-run",
        action="store_true",
        help="Fetch and log messages without writing to the database.",
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
) -> PollStats:
    selected_rooms = rooms if rooms is not None else list(settings.wechat_whitelist_rooms)
    stats = PollStats(room_count=len(selected_rooms))

    for room_id in selected_rooms:
        try:
            messages = adapter.fetch_recent(room_id, limit)
        except Exception as exc:
            message = f"{room_id}: {exc}"
            LOGGER.exception("Failed to fetch room %s", room_id)
            stats.errors.append(message)
            continue

        stats.fetched_count += len(messages)
        if len(messages) >= limit:
            LOGGER.warning("Room %s returned %s messages, at the configured read limit", room_id, len(messages))
        if dry_run:
            LOGGER.info("Dry run: fetched %s messages from %s", len(messages), room_id)
            continue

        before_count = _chat_message_count(db)
        MessageStore(db).import_messages(messages)
        after_count = _chat_message_count(db)
        stats.imported_count += max(0, after_count - before_count)

    if not dry_run:
        command_logs = BotCommandService(db).process_new_messages()
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
    should_stop = _StopFlag()
    signal.signal(signal.SIGINT, should_stop.handle)
    signal.signal(signal.SIGTERM, should_stop.handle)

    while not should_stop.value:
        with SessionLocal() as db:
            stats = poll_once(adapter, settings, db, limit=limit, dry_run=args.dry_run, rooms=rooms)
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


if __name__ == "__main__":
    raise SystemExit(main())
