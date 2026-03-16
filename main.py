"""
BBQ Menu & CS Agent — FastAPI 엔트리포인트.

실행:
    uvicorn main:app --reload
"""

from typing import Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from graph.graph import graph

app = FastAPI(title="BBQ Menu & CS Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 세션별 대화 이력 (서버 메모리 — 프로덕션에서는 Redis 등으로 교체)
_session_store: dict[str, list] = defaultdict(list)


# ── 요청 / 응답 모델 ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    session_id: str
    response: dict   # {"type": "menu_cards"|"text"|"clarification", ...}


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """사용자 자연어 입력을 받아 메뉴 추천 또는 CS 답변을 반환합니다."""
    if not req.user_input.strip():
        raise HTTPException(status_code=400, detail="user_input이 비어 있습니다.")

    # 세션 이력에 새 메시지 추가
    history = _session_store[req.session_id]
    history.append(HumanMessage(content=req.user_input))

    # LangGraph 실행
    result = graph.invoke({
        "messages": history,
        "intent":   None,
        "response": {},
    })

    # 그래프가 업데이트한 messages로 이력 갱신
    _session_store[req.session_id] = list(result["messages"])

    return ChatResponse(
        session_id=req.session_id,
        response=result["response"],
    )


@app.delete("/session/{session_id}")
async def clear_session(session_id: str) -> dict:
    """세션 대화 이력을 초기화합니다."""
    _session_store.pop(session_id, None)
    return {"message": f"세션 '{session_id}' 초기화 완료"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
