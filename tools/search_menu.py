"""
search_menu Tool — SelfQueryRetriever + ChromaDB 기반 메뉴 검색.

LLM이 자연어 쿼리에서 가격·카테고리·알레르기 필터를 자동 추출해 ChromaDB 검색.
"""

import json
from pathlib import Path
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()

CHROMA_PATH = Path(__file__).parent.parent / "vectorstore" / "chroma_db"
COLLECTION_NAME = "bbq_menu"
TOP_K = 5

# SelfQueryRetriever 메타데이터 스키마
METADATA_FIELD_INFO = [
    AttributeInfo(
        name="price",
        description="메뉴 가격 (원 단위 정수). 예: 25000",
        type="integer",
    ),
    AttributeInfo(
        name="category",
        description="메뉴 카테고리. 예: 신메뉴, 사이드, 세트, 순살, 한마리",
        type="string",
    ),
    AttributeInfo(
        name="allergy",
        description="알레르기 유발 성분 목록. 예: 밀, 대두, 닭고기, 우유",
        type="string",
    ),
]

DOCUMENT_CONTENT_DESCRIPTION = "BBQ 치킨 메뉴 정보 (메뉴명, 카테고리, 설명, 알레르기)"


@lru_cache(maxsize=1)
def _get_retriever() -> SelfQueryRetriever:
    """SelfQueryRetriever를 한 번만 초기화 (lazy + cached)."""
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_PATH),
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    retriever = SelfQueryRetriever.from_llm(
        llm=llm,
        vectorstore=vectorstore,
        document_contents=DOCUMENT_CONTENT_DESCRIPTION,
        metadata_field_info=METADATA_FIELD_INFO,
        search_kwargs={"k": TOP_K},
        verbose=False,
    )
    return retriever


@tool
def search_menu(query: str) -> str:
    """BBQ 메뉴를 자연어로 검색합니다.

    가격 범위, 카테고리, 알레르기 제외 등의 조건을 자연어로 포함할 수 있습니다.

    Args:
        query: 자연어 검색 쿼리. 예: "2만원 이하 매운 순살 치킨", "땅콩 알레르기 없는 메뉴"

    Returns:
        검색된 메뉴 목록 (JSON 문자열)
    """
    retriever = _get_retriever()
    docs = retriever.invoke(query)

    results = []
    for doc in docs:
        meta = doc.metadata
        item = {
            "name":      meta.get("name", ""),
            "category":  meta.get("category", ""),
            "price":     meta.get("price", 0),
            "allergy":   meta.get("allergy", ""),
            "nutrition": meta.get("nutrition", ""),
            "options":   meta.get("options", ""),
            "description": doc.page_content,
        }
        results.append(item)

    if not results:
        return json.dumps({"results": [], "message": "조건에 맞는 메뉴를 찾지 못했습니다."}, ensure_ascii=False)

    return json.dumps({"results": results}, ensure_ascii=False)
