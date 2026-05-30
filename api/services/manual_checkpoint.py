from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ManualCheckpoint:
    session_id: str
    run_id: str
    message: str
    resume_event: threading.Event
    created_at: datetime

    def as_event(self) -> dict[str, Any]:
        return {
            "event": "manual_checkpoint",
            "checkpoint": {
                "session_id": self.session_id,
                "run_id": self.run_id,
                "message": self.message,
                "created_at": self.created_at.isoformat(),
            },
        }


class ManualCheckpointBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, ManualCheckpoint] = {}
        self._listeners: dict[str, set[queue.Queue]] = {}

    def listen(self, session_id: str) -> queue.Queue:
        listener: queue.Queue = queue.Queue()
        with self._lock:
            self._listeners.setdefault(session_id, set()).add(listener)
        return listener

    def unlisten(self, session_id: str, listener: queue.Queue) -> None:
        with self._lock:
            listeners = self._listeners.get(session_id)
            if not listeners:
                return
            listeners.discard(listener)
            if not listeners:
                self._listeners.pop(session_id, None)

    def publish(self, session_id: str, message: str) -> ManualCheckpoint:
        checkpoint = ManualCheckpoint(
            session_id=session_id,
            run_id=f"checkpoint_{uuid.uuid4().hex[:8]}",
            message=message,
            resume_event=threading.Event(),
            created_at=datetime.now(timezone.utc),
        )
        event = checkpoint.as_event()
        with self._lock:
            self._active[session_id] = checkpoint
            listeners = list(self._listeners.get(session_id, set()))

        for listener in listeners:
            listener.put(event)

        return checkpoint

    def resume(self, session_id: str, run_id: str | None = None) -> bool:
        with self._lock:
            checkpoint = self._active.get(session_id)
            if checkpoint is None:
                return False
            if run_id and checkpoint.run_id != run_id:
                return False
            self._active.pop(session_id, None)

        checkpoint.resume_event.set()
        return True

    def clear(self, session_id: str, run_id: str | None = None) -> None:
        with self._lock:
            checkpoint = self._active.get(session_id)
            if checkpoint is None:
                return
            if run_id and checkpoint.run_id != run_id:
                return
            self._active.pop(session_id, None)


manual_checkpoint_broker = ManualCheckpointBroker()
