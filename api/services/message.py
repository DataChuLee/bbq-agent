import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from api.services.session import SessionRecord


class MessageService:
    def add_user_message(
        self,
        session: SessionRecord,
        content: str,
        selected_order: dict | None = None,
    ) -> dict:
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        api_msg: dict = {
            "id": msg_id,
            "role": "user",
            "type": "text",
            "content": content,
            "items": None,
            "created_at": now.isoformat(),
        }
        session.api_messages.append(api_msg)
        session.lc_messages.append(HumanMessage(content=content))
        session.selected_order = selected_order
        return api_msg

    def store_assistant_response(
        self, session: SessionRecord, response: dict, intent: str
    ) -> dict:
        """그래프가 lc_messages를 이미 갱신한 뒤 호출한다. api_messages에만 기록한다."""
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        msg_type = response.get("type", "text")
        content: str | None = (
            response.get("message")
            if msg_type in ("text", "clarification", "order_status")
            else None
        )
        items: list | None = None
        if msg_type == "menu_cards":
            items = response.get("items") or []
        elif msg_type == "order_status":
            items = [response]

        api_msg: dict = {
            "id": msg_id,
            "role": "assistant",
            "type": msg_type,
            "content": content,
            "items": items,
            "created_at": now.isoformat(),
        }
        session.api_messages.append(api_msg)
        return api_msg

    def get_messages(
        self, session: SessionRecord, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        return session.api_messages[offset : offset + limit]

    def find_by_id(self, session: SessionRecord, message_id: str) -> dict | None:
        for msg in session.api_messages:
            if msg["id"] == message_id:
                return msg
        return None
