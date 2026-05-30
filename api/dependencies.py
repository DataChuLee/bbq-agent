from typing import Annotated

from fastapi import Depends, Request

from api.services.knowledge import KnowledgeService
from api.services.message import MessageService
from api.services.response import ResponseService
from api.services.session import SessionService


def _session_svc(request: Request) -> SessionService:
    return request.app.state.session_svc


def _message_svc(request: Request) -> MessageService:
    return request.app.state.message_svc


def _response_svc(request: Request) -> ResponseService:
    return request.app.state.response_svc


def _knowledge_svc(request: Request) -> KnowledgeService:
    return request.app.state.knowledge_svc


SessionServiceDep = Annotated[SessionService, Depends(_session_svc)]
MessageServiceDep = Annotated[MessageService, Depends(_message_svc)]
ResponseServiceDep = Annotated[ResponseService, Depends(_response_svc)]
KnowledgeServiceDep = Annotated[KnowledgeService, Depends(_knowledge_svc)]
