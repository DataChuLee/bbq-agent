"""
BBQ Menu & CS Agent — FastAPI 엔트리포인트.

실행:
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.exceptions import AppError, app_error_handler, validation_error_handler
from api.routers import knowledge as knowledge_router
from api.routers import sessions as sessions_router
from api.services.knowledge import KnowledgeService
from api.services.message import MessageService
from api.services.response import ResponseService
from api.services.session import SessionService


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.session_svc = SessionService()
    app.state.message_svc = MessageService()
    app.state.response_svc = ResponseService()
    app.state.knowledge_svc = KnowledgeService()
    yield


app = FastAPI(
    title="BBQ Menu & CS Agent",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

app.include_router(sessions_router.router)
app.include_router(knowledge_router.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"data": {"status": "ok"}}
