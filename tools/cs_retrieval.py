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
# 카테고리 설명이 상담원 용어라 용어를 풀어 주고, "해당 없음"은 CS와 무관한 질문에만 쓰게 한다.
CLASSIFIER_PROMPT = """BBQ 고객센터 문의를 아래 큰 카테고리 중 가장 가까운 하나로 분류하세요.
용어: 패밀리 = 가맹점(매장), 본사 = BBQ 본사, 내점 = 매장에서 먹는 것.
"해당 없음"은 치킨 주문·매장·제품과 관계없는 질문일 때만 고르세요.

[큰 카테고리: 포함된 CS 구분(설명) / 세부 상황]
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


class CsHierarchicalRetriever:
    """큰 카테고리는 LLM이 고르고, 그 안의 세부 상황은 벡터 검색이 고른다.

    비슷한 구분(핑킹 현상·방혈 피고임 등)은 같은 큰 카테고리라 분류기는 쉬운 선택만 하고,
    헷갈리는 선택은 후보가 적은 카테고리 안에서 검색이 한다.
    """

    def __init__(self, vectorstore: Any, llm: Any, k: int = TOP_K) -> None:
        self._vectorstore = vectorstore
        self._k = k
        self._size = len(vectorstore.index_to_docstore_id)
        groups: dict[str, dict[str, list[str]]] = {}
        for docstore_id in vectorstore.index_to_docstore_id.values():
            meta = vectorstore.docstore.search(docstore_id).metadata
            subs = groups.setdefault(meta["claim_category"], {}).setdefault(f"{meta['cs_category']}({meta.get('summary', '')})", [])
            if meta.get("sub_case"):
                subs.append(meta["sub_case"])
        self._categories = "\n".join(
            f"- {claim}: " + "; ".join(f"{name}" + (f" / {', '.join(subs)}" if subs else "") for name, subs in members.items())
            for claim, members in groups.items()
        )
        # 선택지를 고정해 목록에 없는 카테고리를 지어내지 못하게 한다.
        choice = create_model("ClaimCategory", category=(Literal[(*groups, NO_CATEGORY)], ...))
        self._llm = llm.with_structured_output(choice)

    def invoke(self, query: str) -> list[Any]:
        try:
            category = self._llm.invoke(CLASSIFIER_PROMPT.format(categories=self._categories, query=query)).category
        except Exception:
            # 분류기 LLM이 실패해도 CS 검색은 멈추지 않게, 필터 없는 검색으로 넘어간다.
            category = NO_CATEGORY
        unfiltered = self._vectorstore.similarity_search(query, k=self._k)
        if category == NO_CATEGORY:
            return unfiltered
        filtered = self._vectorstore.similarity_search(
            query, k=self._k, filter={"claim_category": category}, fetch_k=self._size
        )
        # 분류가 틀려도 정답이 살아남도록, 필터 밖 1위를 목록에 없을 때만 마지막 자리에 둔다.
        fallback = [doc for doc in unfiltered[:1] if doc not in filtered]
        return filtered[: self._k - len(fallback)] + fallback


@lru_cache(maxsize=1)
def build_cs_hierarchical_retriever() -> CsHierarchicalRetriever:
    vectorstore = FAISS.load_local(
        str(FAISS_PATH),
        OpenAIEmbeddings(model="text-embedding-3-large"),
        allow_dangerous_deserialization=True,
    )
    return CsHierarchicalRetriever(vectorstore, ChatOpenAI(model="gpt-4o-mini", temperature=0))


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
