from __future__ import annotations

from dataclasses import dataclass

import pytest

from tools.cs_retrieval import NO_CATEGORY, CsHierarchicalRetriever, CsSearchService


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
                page_content="대응 방법: 매장 확인 후 안내, 강성인 경우 보상 제안",
                metadata={
                    "cs_category": "배달 지연",
                    "claim_category": "delay",
                    "customer_answer": "매장에 확인해 안내드리겠습니다.",
                    "customer_request": "주문 매장",
                },
            )
        ]
    )
    service = CsSearchService(retriever_loader=lambda: retriever)

    assert service.search("배달이 늦어요") == [
        {
            # 상담원용 원문(page_content)은 고객에게 나가지 않는다.
            "content": "매장에 확인해 안내드리겠습니다.\n고객에게 받을 것: 주문 매장",
            "cs_category": "배달 지연",
            "claim_category": "delay",
        }
    ]
    assert retriever.calls == ["배달이 늦어요"]


def test_cs_search_service_uses_redis_cache_before_retrieval() -> None:
    retriever = FakeRetriever(
        [
            FakeDoc(
                page_content="원문",
                metadata={"customer_answer": "retrieved", "cs_category": "검색", "claim_category": ""},
            )
        ]
    )
    redis_cache = FakeRedisCache(
        docs=[
            FakeDoc(
                page_content="원문",
                metadata={"customer_answer": "cached", "cs_category": "캐시", "claim_category": ""},
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
                page_content="원문",
                metadata={"customer_answer": "retrieved", "cs_category": "검색", "claim_category": ""},
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


class FakeClassifierLlm:
    def __init__(self, category: str) -> None:
        self.category = category
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return self.schema(category=self.category)


class FakeDocstore:
    def __init__(self, docs: list[FakeDoc]) -> None:
        self.docs = {str(i): doc for i, doc in enumerate(docs)}

    def search(self, docstore_id: str) -> FakeDoc:
        return self.docs[docstore_id]


class FakeCsVectorStore:
    """유사도 순서를 문서 목록 순서로 흉내 낸다."""

    def __init__(self, docs: list[FakeDoc]) -> None:
        self.docs = docs
        self.docstore = FakeDocstore(docs)
        self.index_to_docstore_id = {i: str(i) for i in range(len(docs))}

    def similarity_search(self, query: str, k: int, filter: dict | None = None, fetch_k: int | None = None):
        matches = [d for d in self.docs if not filter or all(d.metadata.get(key) == v for key, v in filter.items())]
        return matches[:k]


def cs_doc(name: str, claim: str, sub_case: str = "") -> FakeDoc:
    return FakeDoc(page_content=name, metadata={"cs_category": name, "claim_category": claim, "summary": "", "sub_case": sub_case})


def test_hierarchical_retriever_searches_inside_the_chosen_category_with_fallback() -> None:
    docs = [cs_doc("주문 거부", "주문 거부"), cs_doc("핑킹 현상", "제품 퀄리티"), cs_doc("방혈 피고임", "제품 퀄리티")]
    llm = FakeClassifierLlm("제품 퀄리티")

    result = CsHierarchicalRetriever(FakeCsVectorStore(docs), llm, k=3).invoke("뼈 근처 살이 붉어요")

    # 카테고리 안 후보가 먼저 오고, 분류가 틀렸을 때를 위해 필터 밖 1위가 마지막에 남는다.
    assert [d.metadata["cs_category"] for d in result] == ["핑킹 현상", "방혈 피고임", "주문 거부"]
    assert "- 제품 퀄리티: 핑킹 현상(); 방혈 피고임()" in llm.prompts[0]


def test_hierarchical_retriever_lists_sub_cases_and_falls_back_for_no_category() -> None:
    docs = [cs_doc("전산오류", "전산오류", "결제 오류"), cs_doc("전산오류", "전산오류", "기프티콘 취소 오류")]
    llm = FakeClassifierLlm(NO_CATEGORY)

    result = CsHierarchicalRetriever(FakeCsVectorStore(docs), llm, k=3).invoke("오늘 날씨 어때요")

    assert result == docs
    assert "- 전산오류: 전산오류() / 결제 오류, 기프티콘 취소 오류" in llm.prompts[0]


def test_retrieval_query_keeps_the_customer_message() -> None:
    from langchain_core.messages import AIMessage, HumanMessage

    from tools.search_cs import retrieval_query

    state = {"messages": [HumanMessage(content="기프티콘 내밀었더니 못 받는대요"), AIMessage(content="")]}

    # 에이전트가 줄인 검색어에 "거부" 단서가 없어도 고객 원문이 함께 들어가야 한다.
    assert retrieval_query("기프티콘 사용 관련", state) == "기프티콘 내밀었더니 못 받는대요\n기프티콘 사용 관련"
    assert retrieval_query("질문", {"messages": []}) == "질문"


def test_search_cs_uses_session_cache_keyed_by_agent_query(monkeypatch) -> None:
    import json

    import tools.search_cs as search_cs_module

    def fail_service():
        raise AssertionError("세션 캐시가 있으면 검색하지 않아야 한다")

    monkeypatch.setattr(search_cs_module, "_get_service", fail_service)
    cached = [{"content": "cached", "cs_category": "배달 지연", "claim_category": ""}]
    state = {"messages": [], "cs_results": {"배달 지연": cached}}

    output = search_cs_module.search_cs.func("배달 지연", state)

    assert json.loads(output) == {"results": cached}
