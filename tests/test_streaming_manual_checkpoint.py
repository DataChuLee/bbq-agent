import json
import unittest

from api.streaming import sse_stream


class FakeSession:
    lc_messages = []
    menu_results = None
    cs_results = None
    selected_order = None


class FakeResponseService:
    async def generate_stream(self, session):
        yield (
            "manual_checkpoint",
            {
                "run_id": "checkpoint_1234",
                "message": "Complete login in the browser.",
            },
        )
        yield (
            "done",
            {"type": "text", "message": "finished"},
            "menu",
            [
                {
                    "source_type": "menu",
                    "content": "메뉴 설명",
                    "score": None,
                    "metadata": {"name": "황금올리브치킨"},
                }
            ],
        )


class FakeMessageService:
    def store_assistant_response(self, session, response, intent):
        return {
            "id": "msg_1",
            "role": "assistant",
            "type": response["type"],
            "content": response["message"],
            "items": None,
            "created_at": "2026-04-29T00:00:00+00:00",
        }


class StreamingManualCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_sse_stream_emits_manual_checkpoint_event(self) -> None:
        chunks = []
        async for chunk in sse_stream(
            FakeSession(), FakeResponseService(), FakeMessageService()
        ):
            chunks.append(chunk)

        payloads = [
            json.loads(chunk.removeprefix("data: ").strip())
            for chunk in chunks
            if chunk.startswith("data: ")
        ]

        self.assertEqual(
            [payload["event"] for payload in payloads],
            ["start", "manual_checkpoint", "message", "done"],
        )
        self.assertIn(
            {
                "event": "manual_checkpoint",
                "checkpoint": {
                    "run_id": "checkpoint_1234",
                    "message": "Complete login in the browser.",
                },
            },
            payloads,
        )
        message_event = next(
            payload for payload in payloads if payload["event"] == "message"
        )
        self.assertEqual(
            message_event["sources"],
            [
                {
                    "source_type": "menu",
                    "content": "메뉴 설명",
                    "score": None,
                    "metadata": {"name": "황금올리브치킨"},
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
