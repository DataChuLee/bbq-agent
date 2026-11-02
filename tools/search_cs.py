from __future__ import annotations

import json
from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tools.cs_retrieval import (
    NO_MATCH_MESSAGE,
    CsSearchService,
    build_cs_retriever,
)
from tools.retrieval_cache import build_redis_cache


_get_retriever = build_cs_retriever
# v3: 세부 상황 단위 인덱스로 바뀌어 예전 캐시(v2: 구분 단위)를 쓰지 않도록 이름을 바꿨다.
CS_REDIS_NAMESPACE = "cs_lcel_v3"
CS_REDIS_TTL = 3600


def retrieval_query(query: str, state: dict) -> str:
    """에이전트가 질문을 짧게 바꿔 쓰면서 "거부" 같은 핵심 단서가 빠지므로 고객 원문을 함께 검색한다."""
    last_user = next(
        (str(m.content) for m in reversed(state.get("messages") or []) if isinstance(m, HumanMessage)),
        "",
    )
    return f"{last_user}\n{query}" if last_user and last_user != query else query


def _get_service() -> CsSearchService:
    return CsSearchService(
        retriever_loader=_get_retriever,
        redis_cache=build_redis_cache(CS_REDIS_NAMESPACE, CS_REDIS_TTL),
    )


@tool
def search_cs(query: str, state: Annotated[dict, InjectedState]) -> str:
    """BBQ 고객센터 Q&A에서 유사한 CS 사례를 검색합니다."""
    # graph는 세션 캐시를 에이전트 검색어 키로 저장하므로, 원문을 붙이기 전에 그 키로 먼저 찾는다.
    cached = (state.get("cs_results") or {}).get(query)
    results = list(cached) if cached is not None else _get_service().search(retrieval_query(query, state))

    if not results:
        return json.dumps(
            {"results": [], "message": NO_MATCH_MESSAGE},
            ensure_ascii=False,
        )

    return json.dumps({"results": results}, ensure_ascii=False)
