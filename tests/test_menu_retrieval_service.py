from __future__ import annotations

from dataclasses import dataclass

from tools.menu_retrieval import MenuSearchService


@dataclass
class FakeDoc:
    page_content: str
    metadata: dict


class FakeVectorStore:
    def __init__(self, responses: list[list[FakeDoc]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def similarity_search(self, query: str, k: int, filter: dict | None = None):
        self.calls.append({"query": query, "k": k, "filter": filter})
        return self.responses.pop(0) if self.responses else []


class FakeRetriever:
    search_kwargs = {"k": 5}

    def __init__(self, vectorstore: FakeVectorStore) -> None:
        self.vectorstore = vectorstore
        self.calls: list[str] = []

    def invoke(self, query: str):
        self.calls.append(query)
        return []


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


def make_doc(name: str = "황금올리브치킨™핫크리스피") -> FakeDoc:
    return FakeDoc(
        page_content=f"{name} 설명",
        metadata={
            "name": name,
            "category": "후라이드",
            "price": 24000,
            "spiciness": "매움",
            "primary_texture": "바삭함",
            "product_family": "chicken",
            "product_type": "main_menu",
        },
    )


def test_menu_search_service_uses_rule_filter_before_unfiltered_search() -> None:
    vectorstore = FakeVectorStore([[], [make_doc()]])
    retriever = FakeRetriever(vectorstore)
    service = MenuSearchService(retriever_loader=lambda: retriever)

    results = service.search("매운 바삭한 치킨 추천해줘")

    assert [item["name"] for item in results] == ["황금올리브치킨™핫크리스피"]
    assert vectorstore.calls == [
        {
            "query": "매운 바삭한 치킨 추천해줘",
            "k": 5,
            "filter": {
                "$and": [
                    {"spiciness": {"$eq": "매움"}},
                    {"primary_texture": {"$eq": "바삭함"}},
                    {"product_family": {"$eq": "chicken"}},
                ]
            },
        },
        {
            "query": "매운 바삭한 치킨 추천해줘",
            "k": 5,
            "filter": {
                "$and": [
                    {"spiciness": {"$eq": "매움"}},
                    {"primary_texture": {"$eq": "바삭함"}},
                ]
            },
        },
    ]
    assert retriever.calls == []


def test_menu_search_service_uses_session_cache_when_available() -> None:
    vectorstore = FakeVectorStore([[make_doc()]])
    retriever = FakeRetriever(vectorstore)
    service = MenuSearchService(retriever_loader=lambda: retriever)
    cached_items = [{"name": "캐시 메뉴"}]

    results = service.search(
        "치킨 추천해줘",
        cache={"치킨 추천해줘": cached_items},
    )

    assert results == cached_items
    assert vectorstore.calls == []


def test_menu_search_service_uses_redis_cache_before_retrieval() -> None:
    vectorstore = FakeVectorStore([[make_doc("검색 메뉴")]])
    retriever = FakeRetriever(vectorstore)
    redis_cache = FakeRedisCache(docs=[make_doc("Redis 메뉴")])
    service = MenuSearchService(
        retriever_loader=lambda: retriever,
        redis_cache=redis_cache,
    )

    results = service.search("치킨 추천해줘")

    assert [item["name"] for item in results] == ["Redis 메뉴"]
    assert redis_cache.get_calls == [{"query": "치킨 추천해줘", "k": 5}]
    assert redis_cache.set_calls == []
    assert vectorstore.calls == []


def test_menu_search_service_stores_retrieved_docs_in_redis_cache() -> None:
    vectorstore = FakeVectorStore([[make_doc("검색 메뉴")]])
    retriever = FakeRetriever(vectorstore)
    redis_cache = FakeRedisCache()
    service = MenuSearchService(
        retriever_loader=lambda: retriever,
        redis_cache=redis_cache,
    )

    results = service.search("치킨 추천해줘")

    assert [item["name"] for item in results] == ["검색 메뉴"]
    assert redis_cache.set_calls
