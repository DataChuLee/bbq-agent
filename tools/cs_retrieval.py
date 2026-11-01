from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
import pickle
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import create_model

from tools.cs_query_rules import keep_cs_query
from tools.retrieval_cache import RedisRetrieverCache


load_dotenv()

FAISS_PATH = Path(__file__).parent.parent / "vectorstore" / "faiss_index"
BM25_PATH = Path(__file__).parent.parent / "vectorstore" / "bm25_index.pkl"
TOP_K = 3
NO_MATCH_MESSAGE = "관련 CS 사례를 찾지 못했습니다."
NO_CATEGORY = "해당 없음"
# 구분 설명이 상담원 용어라 용어를 풀어 주고, "해당 없음"은 CS와 무관한 질문에만 쓰게 한다.
# dev2에서 "해당 없음" 남용으로 분류 정답이 55/75에 그쳐 추가했다(수정 후 65/75).
CLASSIFIER_PROMPT = """BBQ 고객센터 문의를 아래 CS 구분 중 가장 가까운 하나로 분류하세요.
용어: 패밀리 = 가맹점(매장), 본사 = BBQ 본사, 내점 = 매장에서 먹는 것.
"해당 없음"은 치킨 주문·매장·제품과 관계없는 질문일 때만 고르세요.

[CS 구분]
{categories}

[문의]
{query}
"""


@lru_cache(maxsize=1)
def build_cs_retriever() -> EnsembleRetriever:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    faiss_vectorstore = FAISS.load_local(
        str(FAISS_PATH),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    faiss_retriever = faiss_vectorstore.as_retriever(search_kwargs={"k": TOP_K})

    with open(BM25_PATH, "rb") as f:
        bm25_retriever = pickle.load(f)
    bm25_retriever.k = TOP_K

    return EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.4, 0.6],
    )


class CsCategoryClassifier:
    """CS 문서가 25개로 고정된 분류 문제라, 유사도 검색 대신 구분을 고른 뒤 그 문서를 꺼낸다."""

    def __init__(self, documents: Sequence[Any], llm: Any) -> None:
        self._documents = {doc.metadata["cs_category"]: doc for doc in documents}
        self._categories = "\n".join(
            f"- {name}: {doc.metadata.get('summary', '')}" for name, doc in self._documents.items()
        )
        # 선택지를 고정해 목록에 없는 구분을 지어내지 못하게 한다.
        choice = create_model("CsCategory", category=(Literal[(*self._documents, NO_CATEGORY)], ...))
        self._llm = llm.with_structured_output(choice)

    def invoke(self, query: str) -> list[Any]:
        result = self._llm.invoke(CLASSIFIER_PROMPT.format(categories=self._categories, query=query))
        doc = self._documents.get(result.category)
        return [doc] if doc else []


@lru_cache(maxsize=1)
def build_cs_classifier() -> CsCategoryClassifier:
    vectorstore = FAISS.load_local(
        str(FAISS_PATH),
        OpenAIEmbeddings(model="text-embedding-3-large"),
        allow_dangerous_deserialization=True,
    )
    documents = [vectorstore.docstore.search(i) for i in vectorstore.index_to_docstore_id.values()]
    return CsCategoryClassifier(documents, ChatOpenAI(model="gpt-4o-mini", temperature=0))


class CsSearchService:
    def __init__(
        self,
        *,
        retriever_loader: Callable[[], Any] = build_cs_retriever,
        redis_cache: RedisRetrieverCache | None = None,
        query_normalizer: Callable[[str], str] = keep_cs_query,
    ) -> None:
        self._retriever_loader = retriever_loader
        self._redis_cache = redis_cache
        self._query_normalizer = query_normalizer

    def search(self, query: str, *, cache: dict | None = None) -> list[dict]:
        cache = cache or {}
        clean = self._query_normalizer(query)
        if clean in cache:
            return list(cache[clean])

        cache_key = {"query": clean}
        docs = self._redis_cache.get_documents(cache_key) if self._redis_cache else None
        if docs is None:
            docs = self._retriever_loader().invoke(clean)
            if self._redis_cache and docs:
                self._redis_cache.set_documents(cache_key, list(docs))
        return self._documents_to_results(docs)

    def _documents_to_results(self, docs: Sequence[Any]) -> list[dict]:
        return [
            {
                # page_content는 상담원용 원문이라 고객에게 보낼 수 있는 검수 문구만 넘긴다.
                "content": _customer_content(doc.metadata),
                "cs_category": doc.metadata.get("cs_category", ""),
                "claim_category": doc.metadata.get("claim_category", ""),
            }
            for doc in docs
        ]


def _customer_content(metadata: dict) -> str:
    answer = metadata.get("customer_answer", "")
    request = metadata.get("customer_request", "")
    return f"{answer}\n고객에게 받을 것: {request}" if request else answer
