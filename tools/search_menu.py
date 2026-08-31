from __future__ import annotations

import json
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tools.menu_retrieval import (
    FOLLOWUP_TOP_K,
    NO_MATCH_MESSAGE,
    TOP_K,
    MenuSearchService,
    build_self_query_retriever,
    infer_requested_family,
    requires_self_query,
)
from tools.retrieval_cache import build_redis_cache
from tools.recommendation_criteria import (
    build_criteria_retrieval_query,
    detect_recommendation_criteria,
    rerank_menu_items,
)


_get_retriever = build_self_query_retriever
MENU_REDIS_NAMESPACE = "menu_lcel"
MENU_REDIS_TTL = 86400


def _get_service() -> MenuSearchService:
    return MenuSearchService(
        retriever_loader=_get_retriever,
        redis_cache=build_redis_cache(MENU_REDIS_NAMESPACE, MENU_REDIS_TTL),
    )


def search_menu_results(
    query: str,
    state: dict | None = None,
    *,
    k: int = TOP_K,
    use_cache: bool = True,
) -> list[dict]:
    return _get_service().search(
        query,
        k=k,
        cache=(state or {}).get("menu_results") or {},
        use_cache=use_cache,
    )


@tool
def search_menu(query: str, state: Annotated[dict, InjectedState]) -> str:
    """BBQ 메뉴를 자연어로 검색합니다."""
    results = search_menu_results(query, state)

    if not results:
        return json.dumps({"results": [], "message": NO_MATCH_MESSAGE}, ensure_ascii=False)

    return json.dumps({"results": results}, ensure_ascii=False)
