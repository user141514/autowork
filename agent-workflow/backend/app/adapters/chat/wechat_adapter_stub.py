from app.adapters.chat.base import ChatAdapter
from app.schemas.chat_message import ChatMessageCreate


class WeChatAdapter(ChatAdapter):
    def listen(self, room_id: str) -> list[ChatMessageCreate]:
        raise NotImplementedError("Real WeChat login and polling are outside the MVP.")

    def send_message(self, room_id: str, text: str) -> None:
        raise NotImplementedError("Real WeChat send_message is outside the MVP.")

    def send_file(self, room_id: str, file_path: str) -> None:
        raise NotImplementedError("Real WeChat send_file is outside the MVP.")
