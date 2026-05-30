from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel, field_validator, model_validator

# ── 공통 리터럴 타입 ──────────────────────────────────────────────────────────

MessageType = Literal["text", "menu_cards", "clarification", "order_status"]
MessageRole = Literal["user", "assistant"]

# ── Session ───────────────────────────────────────────────────────────────────


class SessionOut(BaseModel):
    id: str
    status: Literal["active"] = "active"
    storage: Literal["memory"] = "memory"
    created_at: datetime
    message_count: int


# ── Message ───────────────────────────────────────────────────────────────────


class MessageOut(BaseModel):
    id: str
    role: MessageRole
    type: MessageType
    content: str | None = None
    items: list[dict] | None = None
    created_at: datetime


class MessageCreate(BaseModel):
    type: Literal["text"] = "text"
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


# ── Response Request ──────────────────────────────────────────────────────────


class SelectedOptionDetailIn(BaseModel):
    group_name: str
    option_name: str
    add_price: int = 0
    required: bool = False


class SelectedOrderIn(BaseModel):
    menu_name: str
    menu_category: str = ""
    options: list[str] = []
    option_details: list[SelectedOptionDetailIn] = []
    order_type: Literal["delivery", "pickup"]


class InlineInput(BaseModel):
    type: Literal["text"] = "text"
    content: str
    selected_order: SelectedOrderIn | None = None


class ResponseRequest(BaseModel):
    input: InlineInput | None = None
    source_message_id: str | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "ResponseRequest":
        has_input = self.input is not None
        has_source = self.source_message_id is not None
        if has_input == has_source:
            raise ValueError(
                "exactly one of 'input' or 'source_message_id' must be provided"
            )
        return self


# ── Assistant Response ────────────────────────────────────────────────────────


class SourceRef(BaseModel):
    source_type: Literal["menu", "cs"]
    source_id: str


class AssistantResponseOut(BaseModel):
    response_id: str
    intent: str
    message: MessageOut
    sources: list[SourceRef] = []


# ── Knowledge ─────────────────────────────────────────────────────────────────


class KnowledgeStatusOut(BaseModel):
    menu_documents: int
    cs_documents: int
    vector_index_status: Literal["ready", "not_loaded", "rebuilding"]
    last_rebuilt_at: datetime | None = None


class SearchPreviewRequest(BaseModel):
    query: str
    knowledge_type: Literal["menu", "cs"] = "menu"
    top_k: int = 5


class SearchPreviewOut(BaseModel):
    knowledge_type: str
    query: str
    results: list[dict]


# ── Response Envelope ──────────────────────────────────────────────────────────

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    data: T


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None
    trace_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
