import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from langchain_core.messages import BaseMessage


@dataclass
class SessionRecord:
    id: str
    created_at: datetime
    api_messages: list[dict] = field(default_factory=list)
    lc_messages: list[BaseMessage] = field(default_factory=list)
    menu_results: dict = field(default_factory=dict)
    cs_results: dict = field(default_factory=dict)
    selected_order: dict | None = None
    last_menu_query: str | None = None
    shown_menu_names: list[str] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.api_messages)


class SessionService:
    def __init__(self) -> None:
        self._store: dict[str, SessionRecord] = {}

    def create(self) -> SessionRecord:
        sess_id = f"sess_{uuid.uuid4().hex[:8]}"
        record = SessionRecord(
            id=sess_id,
            created_at=datetime.now(timezone.utc),
        )
        self._store[sess_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        return self._store.get(session_id)

    def delete(self, session_id: str) -> bool:
        if session_id not in self._store:
            return False
        del self._store[session_id]
        return True
