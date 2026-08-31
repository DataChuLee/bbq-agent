from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
import pickle
from typing import Any

from dotenv import load_dotenv
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from tools.cs_query_rules import keep_cs_query
from tools.retrieval_cache import RedisRetrieverCache


load_dotenv()

FAISS_PATH = Path(__file__).parent.parent / "vectorstore" / "faiss_index"
BM25_PATH = Path(__file__).parent.parent / "vectorstore" / "bm25_index.pkl"
TOP_K = 3
NO_MATCH_MESSAGE = "관련 CS 사례를 찾지 못했습니다."


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
                "content": doc.page_content,
                "cs_category": doc.metadata.get("cs_category", ""),
                "claim_category": doc.metadata.get("claim_category", ""),
            }
            for doc in docs
        ]
