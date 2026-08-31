from __future__ import annotations

import json
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tools.cs_retrieval import (
    NO_MATCH_MESSAGE,
    CsSearchService,
    build_cs_retriever,
)
from tools.retrieval_cache import build_redis_cache


_get_retriever = build_cs_retriever
CS_REDIS_NAMESPACE = "cs_lcel"
CS_REDIS_TTL = 3600


def _get_service() -> CsSearchService:
    return CsSearchService(
        retriever_loader=_get_retriever,
        redis_cache=build_redis_cache(CS_REDIS_NAMESPACE, CS_REDIS_TTL),
    )


def search_cs_results(query: str) -> list[dict]:
    """CS 검색 결과를 반환한다. 세션 캐시 없이 단독으로 호출 가능."""
    return _get_service().search(query)


@tool
def search_cs(query: str, state: Annotated[dict, InjectedState]) -> str:
    """BBQ 고객센터 Q&A에서 유사한 CS 사례를 검색합니다."""
    results = _get_service().search(
        query,
        cache=state.get("cs_results") or {},
    )

    if not results:
        return json.dumps(
            {"results": [], "message": NO_MATCH_MESSAGE},
            ensure_ascii=False,
        )

    return json.dumps({"results": results}, ensure_ascii=False)
