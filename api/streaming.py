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
    """SSE 이벤트 시퀀스: start → token… → message → done"""
    yield f"data: {json.dumps({'event': 'start'}, ensure_ascii=False)}\n\n"

    final_response: dict = {}
    final_intent: str = "unknown"

    try:
        async for item in response_svc.generate_stream(session):
            if item[0] == "token":
                token: str = item[1]
                yield f"data: {json.dumps({'event': 'token', 'token': token}, ensure_ascii=False)}\n\n"
            elif item[0] == "manual_checkpoint":
                checkpoint: dict = item[1]
                yield f"data: {json.dumps({'event': 'manual_checkpoint', 'checkpoint': checkpoint}, ensure_ascii=False)}\n\n"
            elif item[0] == "done":
                final_response = item[1]
                final_intent = item[2]
    except Exception as exc:
        yield f"data: {json.dumps({'event': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        return

    assistant_msg = message_svc.store_assistant_response(session, final_response, final_intent)

    yield f"data: {json.dumps({'event': 'message', 'message': assistant_msg}, ensure_ascii=False, default=str)}\n\n"
    yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"
