import hashlib
from datetime import datetime, timezone
from typing import Any

from app.adapters.chat.base import ChatAdapter
from app.config import get_settings
from app.schemas.chat_message import ChatMessageCreate
from app.services.errors import PolicyViolationError


class WxautoAdapter(ChatAdapter):
    platform = "personal_wechat"

    def __init__(self, whitelist_rooms: list[str] | tuple[str, ...] | None = None):
        settings = get_settings()
        self.whitelist_rooms = set(whitelist_rooms or settings.wechat_whitelist_rooms)
        self._wechat = None

    def listen(self, room_id: str) -> list[ChatMessageCreate]:
        return self.read_recent_messages(room_id)

    def read_recent_messages(self, room_id: str, limit: int = 20) -> list[ChatMessageCreate]:
        if not get_settings().personal_wechat_enabled:
            raise PolicyViolationError("PERSONAL_WECHAT_DISABLED")
        self._ensure_allowed_room(room_id)
        limit = min(limit, get_settings().wechat_read_limit)
        wechat = self._client()
        self._switch_to_chat(wechat, room_id)
        raw_messages = self._get_messages(wechat)
        indexed_messages = list(enumerate(raw_messages))
        indexed_messages = indexed_messages[-limit:] if limit > 0 else indexed_messages
        return [self._to_chat_message(room_id, raw, raw_index) for raw_index, raw in indexed_messages]

    def send_message(self, room_id: str, text: str) -> None:
        if not get_settings().personal_wechat_enabled:
            raise PolicyViolationError("PERSONAL_WECHAT_DISABLED")
        if not get_settings().wechat_send_enabled:
            raise PolicyViolationError("WECHAT_SEND_DISABLED")
        self._ensure_allowed_room(room_id)
        wechat = self._client()
        self._switch_to_chat(wechat, room_id)
        if hasattr(wechat, "SendMsg"):
            try:
                wechat.SendMsg(text, who=room_id)
            except TypeError:
                wechat.SendMsg(text)
            return
        raise RuntimeError("wxauto client does not expose SendMsg")

    def send_file(self, room_id: str, file_path: str) -> None:
        if not get_settings().personal_wechat_enabled:
            raise PolicyViolationError("PERSONAL_WECHAT_DISABLED")
        if not get_settings().wechat_send_enabled:
            raise PolicyViolationError("WECHAT_SEND_DISABLED")
        self._ensure_allowed_room(room_id)
        wechat = self._client()
        self._switch_to_chat(wechat, room_id)
        if hasattr(wechat, "SendFiles"):
            try:
                wechat.SendFiles(file_path, who=room_id)
            except TypeError:
                wechat.SendFiles(file_path)
            return
        raise RuntimeError("wxauto client does not expose SendFiles")

    def _client(self) -> Any:
        if self._wechat is not None:
            return self._wechat
        try:
            from wxauto import WeChat
        except ImportError as exc:
            raise RuntimeError("wxauto is not installed. Install it only on Windows hosts with WeChat Desktop.") from exc
        self._wechat = WeChat()
        return self._wechat

    def health_check(self) -> dict:
        settings = get_settings()
        result = {
            "enabled": settings.personal_wechat_enabled,
            "send_enabled": settings.wechat_send_enabled,
            "whitelist_rooms": list(self.whitelist_rooms),
            "adapter": "wxauto",
            "ok": False,
            "error_code": None,
        }
        if not settings.personal_wechat_enabled:
            result["error_code"] = "PERSONAL_WECHAT_DISABLED"
            return result
        if not self.whitelist_rooms:
            result["error_code"] = "WECHAT_ROOM_WHITELIST_EMPTY"
            return result
        try:
            self._client()
        except Exception as exc:
            result["error_code"] = str(exc)
            return result
        result["ok"] = True
        return result

    def fetch_recent(self, room_id: str, limit: int | None = None) -> list[ChatMessageCreate]:
        return self.read_recent_messages(room_id, limit or get_settings().wechat_read_limit)

    def _ensure_allowed_room(self, room_id: str) -> None:
        if not self.whitelist_rooms:
            raise PolicyViolationError("AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS must include allowed group names")
        if room_id not in self.whitelist_rooms:
            raise PolicyViolationError(f"WECHAT_ROOM_NOT_ALLOWED: {room_id}")

    def _switch_to_chat(self, wechat: Any, room_id: str) -> None:
        if hasattr(wechat, "ChatWith"):
            wechat.ChatWith(room_id)

    def _get_messages(self, wechat: Any) -> list[Any]:
        if hasattr(wechat, "GetAllMessage"):
            messages = wechat.GetAllMessage()
            return list(messages or [])
        if hasattr(wechat, "GetAllMessages"):
            messages = wechat.GetAllMessages()
            return list(messages or [])
        raise RuntimeError("wxauto client does not expose GetAllMessage")

    def _to_chat_message(self, room_id: str, raw: Any, raw_index: int) -> ChatMessageCreate:
        sender = _get_attr(raw, ["sender", "Sender", "who", "name"], default="unknown")
        text = _get_attr(raw, ["content", "Content", "text", "msg"], default=str(raw))
        message_type = _get_attr(raw, ["type", "Type"], default="text")
        timestamp = _get_attr(raw, ["time", "Time", "timestamp"], default=None)
        fingerprint_timestamp = timestamp.isoformat() if isinstance(timestamp, datetime) else "no-timestamp"
        if not isinstance(timestamp, datetime):
            timestamp = datetime.now(timezone.utc)
        raw_payload = _safe_raw(raw)
        return ChatMessageCreate(
            platform=self.platform,
            room_id=room_id,
            sender_hash=f"wechat:{sender}",
            sender_display_name=str(sender),
            timestamp=timestamp,
            message_type=str(message_type),
            text=str(text or ""),
            raw_json={"source": "wxauto", "raw_index": raw_index, "raw": raw_payload},
            source_message_fingerprint=_wxauto_source_fingerprint(
                room_id=room_id,
                sender=str(sender),
                message_type=str(message_type),
                text=str(text or ""),
                timestamp=fingerprint_timestamp,
                raw_index=raw_index,
                raw_payload=raw_payload,
            ),
        )


class PersonalWeChatAdapter(WxautoAdapter):
    pass


def _get_attr(raw: Any, names: list[str], default: Any) -> Any:
    if isinstance(raw, dict):
        for name in names:
            if name in raw:
                return raw[name]
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    if isinstance(raw, (tuple, list)) and raw:
        if "sender" in names:
            return raw[0]
        if "content" in names and len(raw) > 1:
            return raw[1]
    return default


def _safe_raw(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, int, float, bool)) or raw is None:
        return raw
    if isinstance(raw, (tuple, list)):
        return list(raw)
    return repr(raw)


def _wxauto_source_fingerprint(
    room_id: str,
    sender: str,
    message_type: str,
    text: str,
    timestamp: str,
    raw_index: int,
    raw_payload: Any,
) -> str:
    raw = "|".join(
        [
            WxautoAdapter.platform,
            room_id,
            sender,
            timestamp,
            message_type,
            text.strip(),
            str(raw_index),
            repr(raw_payload),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
