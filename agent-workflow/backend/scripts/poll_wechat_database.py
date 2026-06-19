from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.adapters.chat.wechat_database_adapter import WeChatDatabaseAdapter
from app.config import get_settings
from app.database import SessionLocal, init_db
from poll_wechat_messages import poll_once


LOGGER = logging.getLogger("wechat-db-poller")


class DatabasePoller:
    def __init__(self, adapter: WeChatDatabaseAdapter, cursors: dict[str, int]):
        self.adapter = adapter
        self.cursors = cursors

    def fetch_recent(self, room_id: str, limit: int | None = None):
        messages = self.adapter.fetch_since(room_id, self.cursors.get(room_id, 0), limit=limit)
        if messages:
            self.cursors[room_id] = max(int(message.timestamp.timestamp()) for message in messages)
        return messages


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll a readable or already-decrypted WeChat MSG.db SQLite database.",
    )
    parser.add_argument("--db-path", type=Path, required=True, help="Path to a readable SQLite MSG.db copy.")
    parser.add_argument("--talkers", type=_csv_list, required=True, help="Comma-separated StrTalker values or fuzzy fragments.")
    parser.add_argument("--interval", type=_non_negative_int, default=3, help="Polling interval in seconds. Use 0 to run once.")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle and exit.")
    parser.add_argument("--limit", type=_positive_int, default=50, help="Max messages to read per talker per poll.")
    parser.add_argument(
        "--since",
        type=_since_datetime,
        default=None,
        help='Only process messages at or after this time, e.g. "2026-06-19 10:30". Naive values are treated as UTC.',
    )
    parser.add_argument("--resolve-talkers", action="store_true", help="Prompt when fuzzy StrTalker fragments match multiple DB talkers.")
    parser.add_argument("--show-new", action="store_true", help="Print newly imported messages each poll.")
    parser.add_argument("--write-agent-prompts", dest="prompt_dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Read and log without writing to the workflow database.")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args(argv)
    if args.once:
        args.interval = 0
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    init_db()
    start_ts = int(args.since.timestamp()) if args.since is not None else int(time.time())
    adapter = WeChatDatabaseAdapter(db_path=str(args.db_path), allowed_talkers=args.talkers)
    talkers = args.talkers
    if args.resolve_talkers:
        try:
            talkers = resolve_talker_inputs(adapter, talkers, input_func=input, output_func=print)
        except KeyboardInterrupt:
            LOGGER.error("Talker selection cancelled.")
            return 130
        adapter = WeChatDatabaseAdapter(db_path=str(args.db_path), allowed_talkers=talkers)
    cursors = {talker: start_ts for talker in talkers}
    poller = DatabasePoller(adapter, cursors)
    settings = get_settings().model_copy(update={"wechat_whitelist_rooms": tuple(talkers)})
    should_stop = _StopFlag()
    signal.signal(signal.SIGINT, should_stop.handle)
    signal.signal(signal.SIGTERM, should_stop.handle)

    while not should_stop.value:
        with SessionLocal() as db:
            stats = poll_once(
                poller,
                settings,
                db,
                limit=args.limit,
                dry_run=args.dry_run,
                rooms=talkers,
                since=args.since,
                show_new=args.show_new,
                prompt_dir=args.prompt_dir,
            )
        LOGGER.info(
            "Database poll complete: talkers=%s fetched=%s imported=%s commands=%s errors=%s",
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


def resolve_talker_inputs(adapter: WeChatDatabaseAdapter, talkers: list[str], input_func=input, output_func=print) -> list[str]:
    resolved_talkers: list[str] = []
    for talker in talkers:
        candidates = adapter.talker_candidates(talker)
        if not candidates:
            output_func(f"No database talker candidates found for '{talker}'. Keeping the original input.")
            resolved_talkers.append(talker)
            continue
        if len(candidates) == 1:
            output_func(f"Resolved '{talker}' -> '{candidates[0]}'")
            resolved_talkers.append(candidates[0])
            continue
        output_func("")
        output_func(f"Multiple database talkers match '{talker}':")
        for index, candidate in enumerate(candidates, start=1):
            output_func(f"  [{index}] {candidate}")
        selected = _prompt_talker_choice(talker, candidates, input_func=input_func, output_func=output_func)
        output_func(f"Resolved '{talker}' -> '{selected}'")
        resolved_talkers.append(selected)
    return resolved_talkers


def _prompt_talker_choice(talker: str, candidates: list[str], input_func=input, output_func=print) -> str:
    while True:
        answer = input_func(f"Select talker for '{talker}' [1-{len(candidates)}]: ").strip()
        try:
            selected_index = int(answer)
        except ValueError:
            output_func("Please enter a number from the list.")
            continue
        if 1 <= selected_index <= len(candidates):
            return candidates[selected_index - 1]
        output_func("Selection out of range.")


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


if __name__ == "__main__":
    raise SystemExit(main())
