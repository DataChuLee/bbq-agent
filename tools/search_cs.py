"""
search_cs Tool — EnsembleRetriever (BM25 40% + FAISS 60%) 기반 CS Q&A 검색.

키워드 매칭(BM25)과 의미론적 검색(FAISS)을 결합해 정확도를 높임.
"""

import json
import pickle
from pathlib import Path
from functools import lru_cache
from typing import Annotated

from dotenv import load_dotenv
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langgraph.prebuilt import InjectedState

load_dotenv()

FAISS_PATH = Path(__file__).parent.parent / "vectorstore" / "faiss_index"
BM25_PATH  = Path(__file__).parent.parent / "vectorstore" / "bm25_index.pkl"
TOP_K = 3


@lru_cache(maxsize=1)
def _get_retriever() -> EnsembleRetriever:
    """EnsembleRetriever를 한 번만 초기화 (lazy + cached)."""
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # FAISS 로드
    faiss_vectorstore = FAISS.load_local(
        str(FAISS_PATH),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    faiss_retriever = faiss_vectorstore.as_retriever(search_kwargs={"k": TOP_K})

    # BM25 로드
    with open(BM25_PATH, "rb") as f:
        bm25_retriever = pickle.load(f)
    bm25_retriever.k = TOP_K

    # EnsembleRetriever: BM25 40% + FAISS 60%
    ensemble = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.4, 0.6],
    )
    return ensemble


@tool
def search_cs(query: str, state: Annotated[dict, InjectedState]) -> str:
    """BBQ 고객센터 Q&A에서 유사한 CS 사례를 검색합니다.

    BM25(키워드) + FAISS(의미론적) 하이브리드 검색으로 관련 대응 방법을 반환합니다.

    Args:
        query: 고객 문의 내용. 예: "배달이 너무 늦어요", "환불 받고 싶어요", "기프티콘이 안 돼요"

    Returns:
        관련 CS 사례 목록 (JSON 문자열)
    """
    cache: dict = state.get("cs_results") or {}
    if query in cache:
        return json.dumps({"results": cache[query]}, ensure_ascii=False)

    retriever = _get_retriever()
    docs = retriever.invoke(query)

    results = []
    for doc in docs:
        results.append({
            "content":        doc.page_content,
            "cs_category":    doc.metadata.get("cs_category", ""),
            "claim_category": doc.metadata.get("claim_category", ""),
        })

    if not results:
        return json.dumps({"results": [], "message": "관련 CS 사례를 찾지 못했습니다."}, ensure_ascii=False)

    return json.dumps({"results": results}, ensure_ascii=False)
