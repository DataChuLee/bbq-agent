from __future__ import annotations

from dataclasses import dataclass

import pytest

from tools.cs_retrieval import CsSearchService


@dataclass
class FakeDoc:
    page_content: str
    metadata: dict


class FakeRetriever:
    def __init__(self, docs: list[FakeDoc]) -> None:
        self.docs = docs
        self.calls: list[str] = []

    def invoke(self, query: str):
        self.calls.append(query)
        return self.docs


class FailingRetriever:
    def invoke(self, query: str):
        raise RuntimeError("retriever unavailable")


class FakeRedisCache:
    def __init__(self, docs=None) -> None:
        self.docs = docs
        self.get_calls = []
        self.set_calls = []

    def get_documents(self, key):
        self.get_calls.append(key)
        return self.docs

    def set_documents(self, key, docs):
        self.set_calls.append((key, docs))


def test_cs_search_service_returns_existing_cache_without_retrieval() -> None:
    retriever = FakeRetriever([])
    service = CsSearchService(retriever_loader=lambda: retriever)
    cached = [{"content": "cached", "cs_category": "배달 지연", "claim_category": ""}]

    assert service.search("배달이 늦어요", cache={"배달이 늦어요": cached}) == cached
    assert retriever.calls == []


def test_cs_search_service_uses_raw_query_by_default() -> None:
    retriever = FakeRetriever([])
    service = CsSearchService(retriever_loader=lambda: retriever)

    service.search("배딜이 늦어요")

    assert retriever.calls == ["배딜이 늦어요"]


def test_cs_search_service_maps_documents_to_tool_contract() -> None:
    retriever = FakeRetriever(
        [
            FakeDoc(
                page_content="대응 방법: 매장 확인 후 안내",
                metadata={"cs_category": "배달 지연", "claim_category": "delay"},
            )
        ]
    )
    service = CsSearchService(retriever_loader=lambda: retriever)

    assert service.search("배달이 늦어요") == [
        {
            "content": "대응 방법: 매장 확인 후 안내",
            "cs_category": "배달 지연",
            "claim_category": "delay",
        }
    ]
    assert retriever.calls == ["배달이 늦어요"]


def test_cs_search_service_uses_redis_cache_before_retrieval() -> None:
    retriever = FakeRetriever(
        [
            FakeDoc(
                page_content="retrieved",
                metadata={"cs_category": "검색", "claim_category": ""},
            )
        ]
    )
    redis_cache = FakeRedisCache(
        docs=[
            FakeDoc(
                page_content="cached",
                metadata={"cs_category": "캐시", "claim_category": ""},
            )
        ]
    )
    service = CsSearchService(
        retriever_loader=lambda: retriever,
        redis_cache=redis_cache,
    )

    assert service.search("배달이 늦어요") == [
        {"content": "cached", "cs_category": "캐시", "claim_category": ""}
    ]
    assert redis_cache.get_calls == [{"query": "배달이 늦어요"}]
    assert retriever.calls == []


def test_cs_search_service_stores_retrieved_docs_in_redis_cache() -> None:
    retriever = FakeRetriever(
        [
            FakeDoc(
                page_content="retrieved",
                metadata={"cs_category": "검색", "claim_category": ""},
            )
        ]
    )
    redis_cache = FakeRedisCache()
    service = CsSearchService(
        retriever_loader=lambda: retriever,
        redis_cache=redis_cache,
    )

    assert service.search("배달이 늦어요") == [
        {"content": "retrieved", "cs_category": "검색", "claim_category": ""}
    ]
    assert redis_cache.set_calls


def test_cs_search_service_returns_empty_results_without_cache_write() -> None:
    retriever = FakeRetriever([])
    redis_cache = FakeRedisCache()
    service = CsSearchService(
        retriever_loader=lambda: retriever,
        redis_cache=redis_cache,
    )

    assert service.search("존재하지 않는 문의") == []
    assert retriever.calls == ["존재하지 않는 문의"]
    assert redis_cache.set_calls == []


def test_cs_search_service_propagates_retriever_failure() -> None:
    service = CsSearchService(retriever_loader=FailingRetriever)

    with pytest.raises(RuntimeError, match="retriever unavailable"):
        service.search("배달 문의")
