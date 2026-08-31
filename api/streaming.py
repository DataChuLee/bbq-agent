import json
from collections.abc import AsyncIterator

from api.services.message import MessageService
from api.services.response import ResponseService
from api.services.session import SessionRecord


async def sse_stream(
    session: SessionRecord,
    response_svc: ResponseService,
    message_svc: MessageService,
) -> AsyncIterator[str]:
    """SSE 이벤트 시퀀스: start → intent? → token… → message → done."""
    yield f"data: {json.dumps({'event': 'start'}, ensure_ascii=False)}\n\n"

    final_response: dict = {}
    final_intent: str = "unknown"
    final_sources: list[dict] = []

    try:
        async for item in response_svc.generate_stream(session):
            if item[0] == "token":
                token: str = item[1]
                yield f"data: {json.dumps({'event': 'token', 'token': token}, ensure_ascii=False)}\n\n"
            elif item[0] == "intent":
                intent_value: str = item[1]
                yield f"data: {json.dumps({'event': 'intent', 'intent': intent_value}, ensure_ascii=False)}\n\n"
            elif item[0] == "manual_checkpoint":
                checkpoint: dict = item[1]
                yield f"data: {json.dumps({'event': 'manual_checkpoint', 'checkpoint': checkpoint}, ensure_ascii=False)}\n\n"
            elif item[0] == "done":
                _, final_response, final_intent, final_sources = item
    except Exception as exc:
        yield f"data: {json.dumps({'event': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        return

    assistant_msg = message_svc.store_assistant_response(session, final_response, final_intent)

    yield f"data: {json.dumps({'event': 'message', 'message': assistant_msg, 'sources': final_sources}, ensure_ascii=False, default=str)}\n\n"
    yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"
