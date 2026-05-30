"""
search_menu Tool — SelfQueryRetriever + ChromaDB 기반 메뉴 검색.

LLM이 자연어 쿼리에서 가격·카테고리·알레르기·식감·맵기 필터를 자동 추출해 ChromaDB 검색.
Few-shot examples로 한국어 필터 추출 정확도를 보완.
"""

import json
from pathlib import Path
from functools import lru_cache
from typing import Annotated

from dotenv import load_dotenv
from langchain.chains.query_constructor.base import (
    AttributeInfo,
    StructuredQueryOutputParser,
    get_query_constructor_prompt,
)
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.query_constructors.chroma import ChromaTranslator
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.prebuilt import InjectedState
from tools.recommendation_criteria import (
    build_criteria_retrieval_query,
    detect_recommendation_criteria,
    rerank_menu_items,
)

load_dotenv()

CHROMA_PATH = Path(__file__).parent.parent / "vectorstore" / "chroma_db"
COLLECTION_NAME = "bbq_menu"
TOP_K = 5
CRITERIA_TOP_K = 12
FOLLOWUP_TOP_K = 12

NO_MATCH_MESSAGE = "조건에 맞는 메뉴를 찾지 못했습니다."

CHICKEN_ALLOWED_FAMILIES = {"main_chicken", "single_chicken", "combo_chicken", "unknown"}

QUERY_FAMILY_ALLOWED = {
    "chicken": CHICKEN_ALLOWED_FAMILIES,
    "burger_pizza": {"burger_pizza", "unknown"},
    "side": {"side", "unknown"},
    "drink": {"drink", "unknown"},
    "sauce": {"sauce", "seasoning", "unknown"},
    "seasoning": {"seasoning", "sauce", "unknown"},
}

BURGER_PIZZA_QUERY_TERMS = ("버거", "피자")
SIDE_QUERY_TERMS = (
    "사이드",
    "감자튀김",
    "치즈볼",
    "콘립",
    "김말이",
    "고추킹",
    "멘보샤",
    "소떡",
    "맛탕",
    "고로케",
    "떡볶이",
    "닭발튀김",
)
DRINK_QUERY_TERMS = ("음료", "콜라", "제로콜라", "스프라이트", "레몬보이")
SAUCE_QUERY_TERMS = ("소스", "양념소스", "핫소스", "치킨무", "무")
SEASONING_QUERY_TERMS = ("시즈닝",)
CHICKEN_QUERY_TERMS = ("치킨", "닭", "윙", "봉", "순살", "반마리", "통다리")


def _query_contains_any(query: str, terms: tuple[str, ...]) -> bool:
    return any(term in query for term in terms)


def infer_requested_family(query: str) -> str | None:
    """Infer the requested product family from a raw Korean menu query."""
    normalized = query.replace(" ", "")

    if _query_contains_any(normalized, BURGER_PIZZA_QUERY_TERMS):
        return "burger_pizza"
    if _query_contains_any(normalized, SIDE_QUERY_TERMS):
        return "side"
    if _query_contains_any(normalized, DRINK_QUERY_TERMS):
        return "drink"
    if _query_contains_any(normalized, SAUCE_QUERY_TERMS):
        return "sauce"
    if _query_contains_any(normalized, SEASONING_QUERY_TERMS):
        return "seasoning"
    if _query_contains_any(normalized, CHICKEN_QUERY_TERMS):
        return "chicken"

    return None


def _filter_by_requested_family(
    items: list[dict], requested_family: str | None
) -> list[dict]:
    if not requested_family:
        return items

    allowed = QUERY_FAMILY_ALLOWED.get(requested_family)
    if not allowed:
        return items

    return [
        item
        for item in items
        if str(item.get("product_family") or "unknown") in allowed
    ]


METADATA_FIELD_INFO = [
    AttributeInfo(
        name="price",
        description="메뉴 가격 (원 단위 정수). 예: 25000",
        type="integer",
    ),
    AttributeInfo(
        name="category",
        description="메뉴 카테고리. 예: 신메뉴, 사이드메뉴, 세트메뉴, 후라이드, 양념, 구이, 1인분 메뉴",
        type="string",
    ),
    AttributeInfo(
        name="allergy",
        description="알레르기 유발 성분 목록. 예: 밀, 대두, 닭고기, 우유",
        type="string",
    ),
    AttributeInfo(
        name="texture",
        description="메뉴의 식감. 가능한 값: 바삭함, 부드러움, 쫄깃함, 촉촉함",
        type="string",
    ),
    AttributeInfo(
        name="spiciness",
        description="메뉴의 맵기 정도. 가능한 값: 매움, 보통, 순함",
        type="string",
    ),
]

DOCUMENT_CONTENT_DESCRIPTION = "BBQ 치킨 메뉴 정보 (메뉴명, 카테고리, 설명, 알레르기, 식감, 맵기)"

# 한국어 필터 추출을 위한 few-shot examples
EXAMPLES = [
    (
        "바삭한 치킨 추천해줘",
        {
            "query": "치킨",
            "filter": 'eq("texture", "바삭함")',
        },
    ),
    (
        "매운 치킨 뭐 있어?",
        {
            "query": "치킨",
            "filter": 'eq("spiciness", "매움")',
        },
    ),
    (
        "바삭하고 매운 치킨",
        {
            "query": "치킨",
            "filter": 'and(eq("texture", "바삭함"), eq("spiciness", "매움"))',
        },
    ),
    (
        "2만원 이하 순한 치킨",
        {
            "query": "치킨",
            "filter": 'and(lte("price", 20000), eq("spiciness", "순함"))',
        },
    ),
    (
        "부드러운 치킨",
        {
            "query": "치킨",
            "filter": 'eq("texture", "부드러움")',
        },
    ),
    (
        "안 매운 바삭한 치킨 추천",
        {
            "query": "치킨",
            "filter": 'and(eq("texture", "바삭함"), eq("spiciness", "순함"))',
        },
    ),
]


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

    prompt = get_query_constructor_prompt(
        document_contents=DOCUMENT_CONTENT_DESCRIPTION,
        attribute_info=METADATA_FIELD_INFO,
        examples=EXAMPLES,
    )
    output_parser = StructuredQueryOutputParser.from_components()
    query_constructor = prompt | llm | output_parser

    retriever = SelfQueryRetriever(
        query_constructor=query_constructor,
        vectorstore=vectorstore,
        structured_query_translator=ChromaTranslator(),
        search_kwargs={"k": TOP_K},
        verbose=True,
    )
    return retriever


def _invoke_retriever(query: str, k: int):
    retriever = _get_retriever()
    if not hasattr(retriever, "search_kwargs"):
        return retriever.invoke(query)

    original_search_kwargs = dict(getattr(retriever, "search_kwargs") or {})
    retriever.search_kwargs = {**original_search_kwargs, "k": k}
    try:
        return retriever.invoke(query)
    finally:
        retriever.search_kwargs = original_search_kwargs


def _documents_to_menu_items(docs) -> list[dict]:
    results = []
    for doc in docs:
        meta = doc.metadata
        item = {
            "name":      meta.get("name", ""),
            "category":  meta.get("category", ""),
            "price":     meta.get("price", 0),
            "allergy":   meta.get("allergy", ""),
            "texture":   meta.get("texture", ""),
            "spiciness": meta.get("spiciness", ""),
            "nutrition": meta.get("nutrition", ""),
            "options":   meta.get("options", ""),
            "description": doc.page_content,
            "imageURL": meta.get("imageURL", ""),
            "product_family": meta.get("product_family", "unknown") or "unknown",
        }
        results.append(item)
    return results


def search_menu_results(
    query: str,
    state: dict | None = None,
    *,
    k: int = TOP_K,
    use_cache: bool = True,
) -> list[dict]:
    """Return menu result dicts for graph nodes and the search_menu tool."""
    criteria = detect_recommendation_criteria(query)
    cache: dict = (state or {}).get("menu_results") or {}
    if use_cache and query in cache and not criteria:
        return list(cache[query])

    requested_family = infer_requested_family(query)
    retrieval_query = build_criteria_retrieval_query(query)
    search_k = max(k, CRITERIA_TOP_K) if criteria else k
    docs = _invoke_retriever(retrieval_query, search_k)

    results = _documents_to_menu_items(docs)
    results = _filter_by_requested_family(results, requested_family)
    return rerank_menu_items(query, results)


@tool
def search_menu(query: str, state: Annotated[dict, InjectedState]) -> str:
    """BBQ 메뉴를 자연어로 검색합니다.

    가격 범위, 카테고리, 알레르기 제외, 식감, 맵기 등의 조건을 자연어로 포함할 수 있습니다.

    Args:
        query: 자연어 검색 쿼리. 예: "바삭한 치킨", "매운 순살 치킨", "땅콩 알레르기 없는 메뉴"

    Returns:
        검색된 메뉴 목록 (JSON 문자열)
    """
    results = search_menu_results(query, state)

    if not results:
        return json.dumps({"results": [], "message": NO_MATCH_MESSAGE}, ensure_ascii=False)

    return json.dumps({"results": results}, ensure_ascii=False)
