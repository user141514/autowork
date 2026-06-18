import csv
import json
from pathlib import Path

from app.adapters.chat.base import ChatAdapter
from app.schemas.chat_message import ChatMessageCreate


class ManualExportAdapter(ChatAdapter):
    platform = "manual_export"

    def listen(self, room_id: str) -> list[ChatMessageCreate]:
        return []

    def send_message(self, room_id: str, text: str) -> None:
        return None

    def send_file(self, room_id: str, file_path: str) -> None:
        return None

    def import_file(
        self,
        file_path: str,
        room_id: str,
        platform: str = "manual_export",
        encoding: str = "utf-8",
        sender_display_name: str | None = None,
    ) -> list[ChatMessageCreate]:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._from_json(path, room_id, platform, encoding, sender_display_name)
        if suffix == ".csv":
            return self._from_csv(path, room_id, platform, encoding, sender_display_name)
        if suffix in {".txt", ".md"}:
            return self._from_text(path, room_id, platform, encoding, sender_display_name)
        raise ValueError("supported manual export formats: .txt, .json, .csv, .md")

    def _from_json(
        self,
        path: Path,
        room_id: str,
        platform: str,
        encoding: str,
        sender_display_name: str | None,
    ) -> list[ChatMessageCreate]:
        data = json.loads(path.read_text(encoding=encoding))
        rows = data if isinstance(data, list) else data.get("messages", [])
        return [
            ChatMessageCreate(
                platform=platform,
                room_id=str(row.get("room_id") or room_id),
                sender_hash=str(row.get("sender_hash") or row.get("sender") or "manual-export"),
                sender_display_name=row.get("sender_display_name") or row.get("sender") or sender_display_name,
                message_type=str(row.get("message_type") or "text"),
                text=str(row.get("text") or row.get("content") or ""),
                attachments=row.get("attachments") or [],
                raw_json={"source": "manual_export_json", "raw": row},
            )
            for row in rows
        ]

    def _from_csv(
        self,
        path: Path,
        room_id: str,
        platform: str,
        encoding: str,
        sender_display_name: str | None,
    ) -> list[ChatMessageCreate]:
        with path.open("r", encoding=encoding, newline="") as handle:
            rows = list(csv.DictReader(handle))
        return [
            ChatMessageCreate(
                platform=platform,
                room_id=row.get("room_id") or room_id,
                sender_hash=row.get("sender_hash") or row.get("sender") or "manual-export",
                sender_display_name=row.get("sender_display_name") or row.get("sender") or sender_display_name,
                message_type=row.get("message_type") or "text",
                text=row.get("text") or row.get("content") or "",
                raw_json={"source": "manual_export_csv", "raw": row},
            )
            for row in rows
        ]

    def _from_text(
        self,
        path: Path,
        room_id: str,
        platform: str,
        encoding: str,
        sender_display_name: str | None,
    ) -> list[ChatMessageCreate]:
        lines = [line.strip() for line in path.read_text(encoding=encoding).splitlines() if line.strip()]
        return [
            ChatMessageCreate(
                platform=platform,
                room_id=room_id,
                sender_hash=sender_display_name or "manual-export",
                sender_display_name=sender_display_name,
                text=line,
                raw_json={"source": f"manual_export_{path.suffix.lower().lstrip('.')}", "line": line},
            )
            for line in lines
        ]
