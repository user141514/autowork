from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.chat.manual_export_adapter import ManualExportAdapter
from app.database import SessionLocal, init_db
from app.services.message_store import MessageStore


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import copied WeChat text from a file path.")
    parser.add_argument("--chat", required=True, help="Chat/group name to attach to imported messages.")
    parser.add_argument("--file", type=Path, required=True, help="Path to .txt/.md/.csv/.json chat export.")
    parser.add_argument("--encoding", default="utf-8")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.file.exists():
        print(f"[ERROR] file does not exist: {args.file}", file=sys.stderr)
        return 2
    init_db()
    messages = ManualExportAdapter().import_file(str(args.file), room_id=args.chat, encoding=args.encoding)
    with SessionLocal() as db:
        saved = MessageStore(db).import_messages(messages)
    ids = ", ".join(str(message.id) for message in saved)
    print(f"Imported {len(saved)} messages for chat '{args.chat}'.")
    print(f"Message IDs: {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
