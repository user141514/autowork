from __future__ import annotations

import hashlib
import html
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.chat_message import ChatMessageCreate
from app.schemas.wechat_directory import (
    ConversationKind,
    WeChatConversationRead,
    WeChatMessageCursor,
    WeChatMessagePageItem,
    WeChatMessagePageResponse,
)


MAX_CONVERSATION_LIMIT = 200
MAX_MESSAGE_PAGE_LIMIT = 200
DEFAULT_MESSAGE_PAGE_LIMIT = 50


@dataclass(frozen=True)
class ContactName:
    username: str
    remark: str | None = None
    nickname: str | None = None
    alias: str | None = None
    session_name: str | None = None

    @property
    def display_name(self) -> str:
        return self.remark or self.nickname or self.alias or self.session_name or self.username

    @property
    def source(self) -> str:
        if self.remark:
            return "Contact.Remark"
        if self.nickname:
            return "Contact.NickName"
        if self.alias:
            return "Contact.Alias"
        if self.session_name:
            return "Session.strNickName"
        return "raw_id"


@dataclass(frozen=True)
class ConversationStats:
    message_count: int = 0
    latest_time: int = 0
    last_preview: str = ""


@dataclass(frozen=True)
class WeChatRow:
    create_time: int
    str_talker: str
    is_sender: int
    str_content: str
    db_name: str
    local_id: int | None = None
    msg_svr_id: str | None = None
    raw_type: int | None = None
    sub_type: int | None = None
    display_content: str | None = None


class WeChatDirectoryService:
    """Read-only directory and message paging service for already-readable WeChat databases.

    The service never decrypts databases and never scans outside the caller-provided directory.
    """

    def __init__(self, decrypted_dir: Path):
        self.decrypted_dir = Path(decrypted_dir)
        self.micro_msg_path = self.decrypted_dir / "de_MicroMsg.db"

    def list_conversations(
        self,
        kind: ConversationKind = "all",
        query: str | None = None,
        limit: int = 100,
    ) -> list[WeChatConversationRead]:
        limit = _safe_limit(limit, MAX_CONVERSATION_LIMIT)
        contacts = self._load_contact_names()
        stats = self._load_conversation_stats()
        usernames = set(contacts) | set(stats)
        rows: list[WeChatConversationRead] = []
        for username in sorted(usernames):
            row_kind = _conversation_kind(username)
            if kind != "all" and row_kind != kind:
                continue
            contact = contacts.get(username, ContactName(username=username))
            item_stats = stats.get(username, ConversationStats())
            row = WeChatConversationRead(
                id=username,
                kind=row_kind,
                displayName=contact.display_name,
                rawName=username,
                remark=contact.remark,
                nickName=contact.nickname,
                alias=contact.alias,
                sessionName=contact.session_name,
                messageCount=item_stats.message_count,
                latestTime=_dt(item_stats.latest_time),
                lastPreview=_preview(item_stats.last_preview, 120) if item_stats.last_preview else None,
                source=contact.source,
            )
            if query and not _matches_query(query, row):
                continue
            rows.append(row)
        rows.sort(key=_conversation_sort_key, reverse=True)
        return rows[:limit]

    def resolve_display_name(self, username: str) -> str:
        return self._load_contact_names().get(username, ContactName(username=username)).display_name

    def get_conversation(self, username: str) -> WeChatConversationRead | None:
        contacts = self._load_contact_names()
        stats = self._load_conversation_stats()
        if username not in contacts and username not in stats:
            return None
        contact = contacts.get(username, ContactName(username=username))
        item_stats = stats.get(username, ConversationStats())
        return WeChatConversationRead(
            id=username,
            kind=_conversation_kind(username),
            displayName=contact.display_name,
            rawName=username,
            remark=contact.remark,
            nickName=contact.nickname,
            alias=contact.alias,
            sessionName=contact.session_name,
            messageCount=item_stats.message_count,
            latestTime=_dt(item_stats.latest_time),
            lastPreview=_preview(item_stats.last_preview, 120) if item_stats.last_preview else None,
            source=contact.source,
        )

    def page_messages(
        self,
        conversation_id: str,
        before_ts: int | None = None,
        before_local_id: int | None = None,
        limit: int = DEFAULT_MESSAGE_PAGE_LIMIT,
    ) -> WeChatMessagePageResponse:
        limit = _safe_limit(limit, MAX_MESSAGE_PAGE_LIMIT)
        rows = self._read_message_rows(conversation_id, before_ts=before_ts, before_local_id=before_local_id, limit=limit + 1)
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [self.row_to_page_item(row) for row in rows]
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = WeChatMessageCursor(beforeTs=last.create_time, beforeLocalId=last.local_id)
        return WeChatMessagePageResponse(items=items, count=len(items), limit=limit, hasMore=has_more, nextCursor=next_cursor)

    def row_to_page_item(self, row: WeChatRow) -> WeChatMessagePageItem:
        normalized = self.normalize_row(row)
        return WeChatMessagePageItem(
            conversationId=normalized["conversation_id"],
            conversationDisplayName=normalized["conversation_display_name"],
            senderId=normalized["sender_id"],
            senderDisplayName=normalized["sender_display_name"],
            timestamp=datetime.fromtimestamp(row.create_time, timezone.utc),
            createTime=row.create_time,
            localId=row.local_id,
            msgSvrId=row.msg_svr_id,
            messageType=normalized["message_type"],
            rawType=row.raw_type,
            text=normalized["text"],
            originalText=row.str_content,
            sourceDb=row.db_name,
        )

    def row_to_chat_message(self, row: WeChatRow) -> ChatMessageCreate:
        normalized = self.normalize_row(row)
        return ChatMessageCreate(
            platform="wechat_database",
            room_id=normalized["conversation_id"],
            sender_hash=f"wechat-db:{normalized['sender_id']}",
            sender_display_name=normalized["sender_display_name"],
            timestamp=datetime.fromtimestamp(row.create_time, timezone.utc),
            message_type=normalized["message_type"],
            text=normalized["text"],
            raw_json={
                "source": "decrypted_wechat_database",
                "source_db": row.db_name,
                "local_id": row.local_id,
                "msg_svr_id": row.msg_svr_id,
                "create_time": row.create_time,
                "talker": row.str_talker,
                "room_display_name": normalized["conversation_display_name"],
                "sender_wxid": normalized["sender_id"],
                "sender_display_name": normalized["sender_display_name"],
                "is_sender": row.is_sender,
                "message_type_raw": row.raw_type,
                "sub_type": row.sub_type,
                "display_content": row.display_content,
                "original_text": row.str_content,
            },
            source_message_fingerprint=_database_fingerprint(
                talker=row.str_talker,
                create_time=row.create_time,
                is_sender=row.is_sender,
                text=row.str_content,
                local_id=row.local_id,
                msg_svr_id=row.msg_svr_id,
            ),
        )

    def normalize_row(self, row: WeChatRow) -> dict[str, str]:
        contacts = self._load_contact_names()
        conversation_id = row.str_talker
        conversation_display_name = contacts.get(conversation_id, ContactName(username=conversation_id)).display_name
        sender_id, cleaned_text = _extract_sender_and_text(row.str_content, row.str_talker, row.is_sender)
        if row.is_sender == 1:
            sender_id = "self"
            sender_display_name = "我"
        else:
            sender_display_name = self._resolve_sender_display_name(row.str_talker, sender_id, contacts)
        message_type = _normalize_wechat_message_type(row.raw_type, cleaned_text)
        text = _clean_message_text(cleaned_text or row.display_content or row.str_content, message_type)
        return {
            "conversation_id": conversation_id,
            "conversation_display_name": conversation_display_name,
            "sender_id": sender_id,
            "sender_display_name": sender_display_name,
            "message_type": message_type,
            "text": text,
        }

    def latest_rows(self, conversation_id: str | None, limit: int) -> list[WeChatRow]:
        if not conversation_id:
            return []
        return self._read_message_rows(conversation_id, limit=_safe_limit(limit, MAX_MESSAGE_PAGE_LIMIT))

    def _resolve_sender_display_name(self, room_id: str, sender_id: str, contacts: dict[str, ContactName]) -> str:
        if sender_id in {"contact", "unknown", ""}:
            return contacts.get(room_id, ContactName(username=room_id)).display_name if not room_id.endswith("@chatroom") else "群成员"
        display_names = self._load_chatroom_display_names().get(room_id, {})
        if sender_id in display_names and display_names[sender_id]:
            return display_names[sender_id]
        if sender_id in contacts:
            return contacts[sender_id].display_name
        return sender_id

    def _load_contact_names(self) -> dict[str, ContactName]:
        if not self.micro_msg_path.exists():
            return {}
        contacts: dict[str, ContactName] = {}
        with sqlite3.connect(f"file:{self.micro_msg_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            contact_cols = _table_columns(conn, "Contact")
            if contact_cols:
                selected = [name for name in ("UserName", "Remark", "NickName", "Alias") if name in contact_cols]
                if "UserName" in selected:
                    query = f"SELECT {', '.join(selected)} FROM Contact"
                    for row in conn.execute(query):
                        username = str(row["UserName"] or "")
                        if not username:
                            continue
                        contacts[username] = ContactName(
                            username=username,
                            remark=_field(row, "Remark"),
                            nickname=_field(row, "NickName"),
                            alias=_field(row, "Alias"),
                        )
            session_cols = _table_columns(conn, "Session")
            if {"strUsrName", "strNickName"}.issubset(session_cols):
                for row in conn.execute("SELECT strUsrName, strNickName FROM Session"):
                    username = str(row["strUsrName"] or "")
                    if not username:
                        continue
                    current = contacts.get(username, ContactName(username=username))
                    contacts[username] = ContactName(
                        username=username,
                        remark=current.remark,
                        nickname=current.nickname,
                        alias=current.alias,
                        session_name=_field(row, "strNickName") or current.session_name,
                    )
        return contacts

    def _load_chatroom_display_names(self) -> dict[str, dict[str, str]]:
        if not self.micro_msg_path.exists():
            return {}
        with sqlite3.connect(f"file:{self.micro_msg_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cols = _table_columns(conn, "ChatRoom")
            if not {"ChatRoomName", "UserNameList", "DisplayNameList"}.issubset(cols):
                return {}
            result: dict[str, dict[str, str]] = {}
            for row in conn.execute("SELECT ChatRoomName, UserNameList, DisplayNameList FROM ChatRoom"):
                room = str(row["ChatRoomName"] or "")
                users = _split_room_list(str(row["UserNameList"] or ""))
                display_names = _split_room_list(str(row["DisplayNameList"] or ""))
                mapping = {user: display_names[index] for index, user in enumerate(users) if index < len(display_names) and display_names[index]}
                if room and mapping:
                    result[room] = mapping
            return result

    def _load_conversation_stats(self) -> dict[str, ConversationStats]:
        stats: dict[str, ConversationStats] = {}
        for db_path in self._msg_db_paths():
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                cols = _table_columns(conn, "MSG")
                if not {"StrTalker", "CreateTime"}.issubset(cols):
                    continue
                rows = conn.execute(
                    """
                    SELECT StrTalker, COUNT(*) AS count, MAX(CreateTime) AS latest_time
                    FROM MSG
                    WHERE StrTalker IS NOT NULL AND StrTalker != ''
                    GROUP BY StrTalker
                    """
                ).fetchall()
                for row in rows:
                    talker = str(row["StrTalker"] or "")
                    if not talker:
                        continue
                    current = stats.get(talker, ConversationStats())
                    count = current.message_count + int(row["count"] or 0)
                    latest_time = max(current.latest_time, int(row["latest_time"] or 0))
                    last_preview = current.last_preview
                    if latest_time > current.latest_time:
                        last_preview = self._latest_text_from_db(db_path, talker)
                    stats[talker] = ConversationStats(message_count=count, latest_time=latest_time, last_preview=last_preview)
        return stats

    def _latest_text_from_db(self, db_path: Path, talker: str) -> str:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cols = _table_columns(conn, "MSG")
            content_col = "StrContent" if "StrContent" in cols else None
            if content_col is None:
                return ""
            row = conn.execute(
                f"SELECT {content_col} FROM MSG WHERE StrTalker = ? ORDER BY CreateTime DESC LIMIT 1",
                (talker,),
            ).fetchone()
        return str(row[content_col] or "") if row else ""

    def _read_message_rows(
        self,
        conversation_id: str,
        before_ts: int | None = None,
        before_local_id: int | None = None,
        limit: int = DEFAULT_MESSAGE_PAGE_LIMIT,
    ) -> list[WeChatRow]:
        rows: list[WeChatRow] = []
        for db_path in self._msg_db_paths():
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                cols = _table_columns(conn, "MSG")
                if not {"CreateTime", "StrTalker", "IsSender", "StrContent"}.issubset(cols):
                    continue
                select_cols = _message_select_columns(cols)
                query = f"SELECT {', '.join(select_cols)} FROM MSG WHERE StrTalker = ?"
                params: list[Any] = [conversation_id]
                if before_ts is not None:
                    if before_local_id is not None and "localId" in cols:
                        query += " AND (CreateTime < ? OR (CreateTime = ? AND localId < ?))"
                        params.extend([before_ts, before_ts, before_local_id])
                    else:
                        query += " AND CreateTime < ?"
                        params.append(before_ts)
                query += " ORDER BY CreateTime DESC"
                if "localId" in cols:
                    query += ", localId DESC"
                query += " LIMIT ?"
                params.append(max(limit, 1))
                rows.extend(_row_from_sqlite(row, db_path.name) for row in conn.execute(query, params))
        rows.sort(key=lambda item: (item.create_time, item.local_id or 0), reverse=True)
        return rows[:limit]

    def _msg_db_paths(self) -> list[Path]:
        return sorted(self.decrypted_dir.glob("de_MSG*.db"))


def _message_select_columns(cols: set[str]) -> list[str]:
    return [
        name
        for name in ("CreateTime", "StrTalker", "IsSender", "StrContent", "localId", "MsgSvrID", "Type", "SubType", "DisplayContent")
        if name in cols
    ]


def _row_from_sqlite(row: sqlite3.Row, db_name: str) -> WeChatRow:
    return WeChatRow(
        create_time=int(row["CreateTime"] or 0),
        str_talker=str(row["StrTalker"] or ""),
        is_sender=int(row["IsSender"] or 0),
        str_content=str(row["StrContent"] or ""),
        db_name=db_name,
        local_id=_int_or_none(_field(row, "localId")),
        msg_svr_id=_field(row, "MsgSvrID"),
        raw_type=_int_or_none(_field(row, "Type")),
        sub_type=_int_or_none(_field(row, "SubType")),
        display_content=_field(row, "DisplayContent"),
    )


def _field(row: sqlite3.Row, name: str) -> str | None:
    try:
        value = row[name]
    except (IndexError, KeyError):
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.DatabaseError:
        return set()


def _conversation_kind(username: str) -> ConversationKind:
    if username == "filehelper":
        return "filehelper"
    if username.endswith("@chatroom"):
        return "chatroom"
    if username.startswith("gh_") or username.startswith("mp"):
        return "official"
    if username:
        return "contact"
    return "unknown"


def _safe_limit(limit: int | None, max_limit: int) -> int:
    if limit is None:
        return min(DEFAULT_MESSAGE_PAGE_LIMIT, max_limit)
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = DEFAULT_MESSAGE_PAGE_LIMIT
    return max(1, min(parsed, max_limit))


def _dt(timestamp: int) -> datetime | None:
    return datetime.fromtimestamp(timestamp, timezone.utc) if timestamp else None


def _preview(text: str, limit: int) -> str:
    normalized = _clean_plain_text(text)
    return normalized if len(normalized) <= limit else normalized[: max(0, limit - 3)] + "..."


def _conversation_sort_key(row: WeChatConversationRead) -> tuple[int, int, str]:
    latest_epoch = int(row.latest_time.timestamp()) if row.latest_time else 0
    return (latest_epoch, row.message_count, row.display_name or row.id)


def _matches_query(query: str, row: WeChatConversationRead) -> bool:
    token = _norm(query)
    if not token:
        return True
    if _looks_like_raw_wechat_id(token):
        raw_haystack = _norm(" ".join(str(item or "") for item in [row.id, row.raw_name]))
        return token in raw_haystack
    name_fields = [row.display_name, row.remark, row.nickname, row.alias, row.session_name]
    name_haystack = _norm(" ".join(str(item or "") for item in name_fields))
    if token in name_haystack:
        return True
    compact_token = _compact_match_text(query)
    if not compact_token:
        return False
    for field in name_fields:
        compact_field = _compact_match_text(str(field or ""))
        if compact_token in compact_field:
            return True
        if _fuzzy_name_match(compact_token, compact_field):
            return True
    return False


def _looks_like_raw_wechat_id(token: str) -> bool:
    return "@chatroom" in token or token.startswith("wxid_") or token in {"filehelper"}


def _norm(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _compact_match_text(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(value or "").lower())


def _fuzzy_name_match(compact_token: str, compact_field: str) -> bool:
    if len(compact_token) < 3 or not compact_field:
        return False
    if len(compact_field) < len(compact_token):
        return SequenceMatcher(None, compact_token, compact_field).ratio() >= 0.82
    window_size = len(compact_token)
    best = 0.0
    for start in range(0, max(1, len(compact_field) - window_size + 1)):
        window = compact_field[start : start + window_size]
        best = max(best, SequenceMatcher(None, compact_token, window).ratio())
        if best >= 0.74:
            return True
    return False


def _split_room_list(value: str) -> list[str]:
    if not value:
        return []
    separators = ["\x07", "^G", ",", ";", "、", "\n"]
    normalized = value
    for sep in separators:
        normalized = normalized.replace(sep, "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def _extract_sender_and_text(text: str, talker: str, is_sender: int) -> tuple[str, str]:
    if is_sender == 1:
        return "self", text
    if talker.endswith("@chatroom"):
        match = re.match(r"([^:\n\r]{2,80}):\s*(?:\r?\n)?(.*)", text or "", flags=re.DOTALL)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        xml_sender = _xml_sender(text)
        if xml_sender:
            return xml_sender, text
        return "unknown", text
    return talker or "contact", text


def _xml_sender(text: str) -> str | None:
    match = re.search(r"fromusername=['\"]([^'\"]+)['\"]", text or "")
    return match.group(1).strip() if match else None


def _normalize_wechat_message_type(raw_type: int | None, text: str) -> str:
    if raw_type == 1 or raw_type is None:
        return "text" if text else "unknown"
    if raw_type == 3:
        return "image"
    if raw_type == 34:
        return "voice"
    if raw_type == 43:
        return "video"
    if raw_type == 47:
        return "emoji"
    if raw_type == 49:
        return "link"
    if raw_type == 10000:
        return "system"
    return "unknown"


def _clean_message_text(text: str, message_type: str) -> str:
    text = _clean_plain_text(text)
    if message_type == "emoji":
        return "[emoji]"
    if message_type == "image":
        return "[image]"
    if message_type == "voice":
        return "[voice]"
    if message_type == "video":
        return "[video]"
    if message_type == "link" and text.startswith("<"):
        return _extract_xml_title(text) or "[link/file]"
    if text.startswith("<msg") or text.startswith("<?xml"):
        return _extract_xml_title(text) or "[xml]"
    return text


def _extract_xml_title(text: str) -> str | None:
    for tag in ("title", "des", "appname"):
        match = re.search(rf"<{tag}>(.*?)</{tag}>", text or "", flags=re.DOTALL | re.IGNORECASE)
        if match:
            value = _clean_plain_text(match.group(1))
            if value:
                return value
    return None


def _clean_plain_text(text: str) -> str:
    text = html.unescape(text or "")
    return " ".join(text.replace("\r", "\n").split())


def _database_fingerprint(talker: str, create_time: int, is_sender: int, text: str, local_id: int | None, msg_svr_id: str | None) -> str:
    raw = "|".join(["wechat_database", talker, str(create_time), str(is_sender), str(local_id or ""), str(msg_svr_id or ""), text.strip()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
