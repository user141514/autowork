from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.adapters.chat.base import ChatAdapter
from app.schemas.chat_message import ChatMessageCreate
from app.services.errors import PolicyViolationError


class WeChatDatabaseAdapter(ChatAdapter):
    platform = "wechat_database"

    def __init__(self, db_path: str, allowed_talkers: list[str] | tuple[str, ...]):
        self.db_path = Path(db_path)
        self.allowed_talkers = {_normalize_talker(talker) for talker in allowed_talkers}

    def listen(self, room_id: str) -> list[ChatMessageCreate]:
        return self.fetch_since(room_id, last_ts=0, limit=20)

    def send_message(self, room_id: str, text: str) -> None:
        raise PolicyViolationError("WECHAT_DATABASE_ADAPTER_READ_ONLY")

    def send_file(self, room_id: str, file_path: str) -> None:
        raise PolicyViolationError("WECHAT_DATABASE_ADAPTER_READ_ONLY")

    def fetch_between(self, talker: str, start_ts: int, end_ts: int, limit: int | None = None) -> list[ChatMessageCreate]:
        self._ensure_allowed_talker(talker)
        query = """
            SELECT CreateTime, StrTalker, StrContent, IsSender
            FROM MSG
            WHERE StrTalker = ?
              AND CreateTime BETWEEN ? AND ?
            ORDER BY CreateTime ASC
        """
        params: list[Any] = [talker, start_ts, end_ts]
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        return [self._to_chat_message(row) for row in self._query(query, params)]

    def fetch_since(self, talker: str, last_ts: int, limit: int | None = None) -> list[ChatMessageCreate]:
        self._ensure_allowed_talker(talker)
        query = """
            SELECT CreateTime, StrTalker, StrContent, IsSender
            FROM MSG
            WHERE StrTalker = ?
              AND CreateTime > ?
            ORDER BY CreateTime ASC
        """
        params: list[Any] = [talker, last_ts]
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        return [self._to_chat_message(row) for row in self._query(query, params)]

    def talker_candidates(self, token: str) -> list[str]:
        self._ensure_allowed_talker(token)
        rows = self._query(
            """
            SELECT DISTINCT StrTalker
            FROM MSG
            WHERE StrTalker IS NOT NULL
            ORDER BY StrTalker ASC
            """,
            [],
        )
        talkers = [str(row["StrTalker"]) for row in rows]
        return _matching_talkers(token, talkers, self.allowed_talkers)

    def _ensure_allowed_talker(self, talker: str) -> None:
        if not self.allowed_talkers:
            raise PolicyViolationError("AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS must include allowed talkers")
        if not _is_allowed_talker(talker, self.allowed_talkers):
            raise PolicyViolationError(f"WECHAT_TALKER_NOT_ALLOWED: {talker}")

    def _query(self, query: str, params: list[Any]) -> list[sqlite3.Row]:
        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                return list(conn.execute(query, params))
        except sqlite3.DatabaseError as exc:
            raise RuntimeError(
                "WECHAT_DATABASE_NOT_READABLE: expected a readable SQLite MSG.db copy. "
                "Encrypted WeChat databases must be decrypted outside this project first."
            ) from exc

    def _to_chat_message(self, row: sqlite3.Row) -> ChatMessageCreate:
        create_time = int(row["CreateTime"])
        talker = str(row["StrTalker"])
        text = str(row["StrContent"] or "")
        sender = "self" if int(row["IsSender"] or 0) == 1 else "contact"
        timestamp = datetime.fromtimestamp(create_time, timezone.utc)
        return ChatMessageCreate(
            platform=self.platform,
            room_id=talker,
            sender_hash=f"wechat-db:{talker}:{sender}",
            sender_display_name=sender,
            timestamp=timestamp,
            message_type="text",
            text=text,
            raw_json={"source": "wechat_database", "create_time": create_time, "talker": talker, "is_sender": row["IsSender"]},
            source_message_fingerprint=_database_fingerprint(talker, create_time, sender, text),
        )


def _normalize_talker(value: Any) -> str:
    return " ".join(str(value or "").strip().split()).lower()


def _is_allowed_talker(talker: str, allowed_talkers: set[str]) -> bool:
    normalized_talker = _normalize_talker(talker)
    if not normalized_talker:
        return False
    if normalized_talker in allowed_talkers:
        return True
    return any(
        len(allowed) >= 2 and (allowed in normalized_talker or normalized_talker in allowed)
        for allowed in allowed_talkers
    )


def _matching_talkers(token: str, talkers: list[str], allowed_talkers: set[str]) -> list[str]:
    normalized_token = _normalize_talker(token)
    exact_matches = [talker for talker in talkers if _normalize_talker(talker) == normalized_token]
    if exact_matches:
        return exact_matches
    return [
        talker
        for talker in talkers
        if _is_allowed_talker(talker, {normalized_token}) and _is_allowed_talker(talker, allowed_talkers)
    ]


def _database_fingerprint(talker: str, create_time: int, sender: str, text: str) -> str:
    raw = "|".join([WeChatDatabaseAdapter.platform, talker, str(create_time), sender, text.strip()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
