import uuid

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from api.dependencies import MessageServiceDep, ResponseServiceDep, SessionServiceDep
from api.exceptions import AppError
from api.services.manual_checkpoint import manual_checkpoint_broker
from api.schemas import (
    AssistantResponseOut,
    DataResponse,
    MessageCreate,
    MessageOut,
    ResponseRequest,
    SessionOut,
    SourceRef,
)
from api.streaming import sse_stream

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_session_out(record) -> SessionOut:
    return SessionOut(
        id=record.id,
        status="active",
        storage="memory",
        created_at=record.created_at,
        message_count=record.message_count,
    )


def _require_session(session_id: str, session_svc):
    record = session_svc.get(session_id)
    if record is None:
        raise AppError("SESSION_NOT_FOUND", f"Session '{session_id}' not found", 404)
    return record


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    session_svc: SessionServiceDep,
) -> DataResponse[SessionOut]:
    record = session_svc.create()
    return DataResponse(data=_to_session_out(record))


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    session_svc: SessionServiceDep,
) -> DataResponse[SessionOut]:
    record = _require_session(session_id, session_svc)
    return DataResponse(data=_to_session_out(record))


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    session_svc: SessionServiceDep,
    message_svc: MessageServiceDep,
    limit: int = 50,
    offset: int = 0,
) -> DataResponse[list[dict]]:
    record = _require_session(session_id, session_svc)
    messages = message_svc.get_messages(record, limit=limit, offset=offset)
    return DataResponse(data=messages)


@router.post("/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def add_message(
    session_id: str,
    body: MessageCreate,
    session_svc: SessionServiceDep,
    message_svc: MessageServiceDep,
) -> DataResponse[dict]:
    record = _require_session(session_id, session_svc)
    msg = message_svc.add_user_message(record, body.content)
    return DataResponse(data=msg)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    session_svc: SessionServiceDep,
) -> None:
    if not session_svc.delete(session_id):
        raise AppError("SESSION_NOT_FOUND", f"Session '{session_id}' not found", 404)


@router.post("/{session_id}/manual-checkpoints/{run_id}/resume")
async def resume_manual_checkpoint(
    session_id: str,
    run_id: str,
    session_svc: SessionServiceDep,
) -> DataResponse[dict]:
    _require_session(session_id, session_svc)
    if not manual_checkpoint_broker.resume(session_id, run_id):
        raise AppError(
            "MANUAL_CHECKPOINT_NOT_FOUND",
            f"Manual checkpoint '{run_id}' not found in session '{session_id}'",
            404,
        )
    return DataResponse(data={"resumed": True, "run_id": run_id})


@router.post("/{session_id}/responses")
async def generate_response(
    session_id: str,
    body: ResponseRequest,
    session_svc: SessionServiceDep,
    message_svc: MessageServiceDep,
    response_svc: ResponseServiceDep,
) -> DataResponse[AssistantResponseOut]:
    record = _require_session(session_id, session_svc)

    if body.input:
        message_svc.add_user_message(
            record,
            body.input.content,
            selected_order=(
                body.input.selected_order.model_dump()
                if body.input.selected_order
                else None
            ),
        )
    else:
        src = message_svc.find_by_id(record, body.source_message_id)
        if src is None:
            raise AppError(
                "SOURCE_MESSAGE_NOT_FOUND",
                f"Message '{body.source_message_id}' not found in session",
                404,
            )

    response, intent, sources = await response_svc.generate(record)
    assistant_msg = message_svc.store_assistant_response(record, response, intent)

    resp_id = f"resp_{uuid.uuid4().hex[:8]}"
    return DataResponse(
        data=AssistantResponseOut(
            response_id=resp_id,
            intent=intent,
            message=MessageOut(**assistant_msg),
            sources=[SourceRef(**s) for s in sources],
        )
    )


@router.post("/{session_id}/responses/stream")
async def stream_response(
    session_id: str,
    body: ResponseRequest,
    session_svc: SessionServiceDep,
    message_svc: MessageServiceDep,
    response_svc: ResponseServiceDep,
):
    record = _require_session(session_id, session_svc)

    if body.input:
        message_svc.add_user_message(
            record,
            body.input.content,
            selected_order=(
                body.input.selected_order.model_dump()
                if body.input.selected_order
                else None
            ),
        )
    else:
        src = message_svc.find_by_id(record, body.source_message_id)
        if src is None:
            raise AppError(
                "SOURCE_MESSAGE_NOT_FOUND",
                f"Message '{body.source_message_id}' not found in session",
                404,
            )

    return StreamingResponse(
        sse_stream(record, response_svc, message_svc),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
