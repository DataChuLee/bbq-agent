import asyncio
import json

from api.streaming import sse_stream


class FailingResponseService:
    async def generate_stream(self, session):
        yield ("intent", "cs")
        raise RuntimeError("provider connection failed")


class RecordingMessageService:
    def __init__(self) -> None:
        self.called = False

    def store_assistant_response(self, session, response, intent):
        self.called = True
        return {}


def test_sse_stream_emits_error_without_persisting_partial_response() -> None:
    message_service = RecordingMessageService()

    async def collect() -> list[dict]:
        events = []
        async for raw_event in sse_stream(
            object(), FailingResponseService(), message_service
        ):
            events.append(json.loads(raw_event.removeprefix("data: ")))
        return events

    events = asyncio.run(collect())

    assert [event["event"] for event in events] == ["start", "intent", "error"]
    assert events[-1]["message"] == "provider connection failed"
    assert not message_service.called
