from abc import ABC, abstractmethod

from app.schemas.chat_message import ChatMessageCreate


class ChatAdapter(ABC):
    @abstractmethod
    def listen(self, room_id: str) -> list[ChatMessageCreate]:
        raise NotImplementedError

    @abstractmethod
    def send_message(self, room_id: str, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_file(self, room_id: str, file_path: str) -> None:
        raise NotImplementedError
