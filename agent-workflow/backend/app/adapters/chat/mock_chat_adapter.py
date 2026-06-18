from app.adapters.chat.base import ChatAdapter
from app.schemas.chat_message import ChatMessageCreate


class MockChatAdapter(ChatAdapter):
    def __init__(self) -> None:
        self.outbox: list[dict[str, str]] = []

    def listen(self, room_id: str) -> list[ChatMessageCreate]:
        return []

    def send_message(self, room_id: str, text: str) -> None:
        self.outbox.append({"type": "message", "room_id": room_id, "text": text})

    def send_file(self, room_id: str, file_path: str) -> None:
        self.outbox.append({"type": "file", "room_id": room_id, "file_path": file_path})
