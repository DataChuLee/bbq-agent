from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from dotenv import load_dotenv
from langchain.chains.query_constructor.base import (
    AttributeInfo,
    StructuredQueryOutputParser,
    get_query_constructor_prompt,
)
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.query_constructors.chroma import ChromaTranslator
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from tools.menu_query_rules import (
    build_relaxed_filter_candidates,
    extract_rule_based_filters,
)
from tools.retrieval_cache import RedisRetrieverCache
from tools.recommendation_criteria import (
    build_criteria_retrieval_query,
    detect_recommendation_criteria,
    filter_items_by_recommendation_profile,
    rerank_menu_items,
)


load_dotenv()

CHROMA_PATH = Path(__file__).parent.parent / "vectorstore" / "chroma_db"
COLLECTION_NAME = "bbq_menu"
TOP_K = 5
CRITERIA_TOP_K = 12
FOLLOWUP_TOP_K = 12

NO_MATCH_MESSAGE = "조건에 맞는 메뉴를 찾지 못했습니다."

CHICKEN_ALLOWED_FAMILIES = {
    "chicken",
    "main_chicken",
    "single_chicken",
    "combo_chicken",
    "unknown",
}
DEFAULT_MENU_PRODUCT_TYPES = {"main_menu", "set_menu", "unknown"}

QUERY_FAMILY_ALLOWED = {
    "chicken": CHICKEN_ALLOWED_FAMILIES,
    "burger_pizza": {"burger", "pizza", "burger_pizza", "unknown"},
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

PRICE_QUERY_PATTERN = re.compile(r"\d+\s*(?:만\s*)?원")
PRICE_QUERY_TERMS = ("가격", "이하", "이상", "미만", "초과", "저렴", "싼", "비싼")
EXCLUSION_QUERY_TERMS = (
    "알레르기",
    "제외",
    "빼고",
    "없는",
    "없고",
    "못먹",
    "못 먹",
    "안들어",
    "안 들어",
)
NEGATED_SPICY_TERMS = ("안매운", "안 매운", "덜매운", "덜 매운")
TEXTURE_QUERY_TERMS = ("바삭", "부드러", "쫄깃", "촉촉")
SPICINESS_QUERY_TERMS = ("매운", "매움", "순한", "순함", "보통")

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
        name="product_type",
        description=(
            "상품 역할. 가능한 값: main_menu, set_menu, side, sauce, drink. "
            "일반적인 메뉴 추천이나 식사 추천은 main_menu 또는 set_menu를 우선 사용하고, "
            "소스/음료/사이드를 명시한 경우에만 해당 값을 사용한다."
        ),
        type="string",
    ),
    AttributeInfo(
        name="product_family",
        description="상품군. 가능한 값: chicken, pizza, burger, side, sauce, drink, seasoning",
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
    AttributeInfo(
        name="primary_texture",
        description="메뉴의 대표 식감. 가능한 값: 바삭함, 부드러움, 쫄깃함, 촉촉함",
        type="string",
    ),
    AttributeInfo(
        name="cooking_method",
        description="조리 방식. 가능한 값: fried, grilled, smoked, soup",
        type="string",
    ),
    AttributeInfo(
        name="sauce_style",
        description="소스/양념 스타일. 가능한 값: none, sauced, spicy_sauce, soy_sauce",
        type="string",
    ),
    AttributeInfo(
        name="option_tags",
        description="구매 옵션에서 추출한 태그. 예: 순살, 반마리, 한마리, 윙, 봉, 닭다리, 콤보",
        type="string",
    ),
]

DOCUMENT_CONTENT_DESCRIPTION = "BBQ 메뉴 정보 (메뉴명, 상품유형, 상품군, 카테고리, 설명, 알레르기, 대표 식감, 맵기)"

EXAMPLES = [
    (
        "바삭한 치킨 추천해줘",
        {
            "query": "치킨",
            "filter": 'and(eq("product_family", "chicken"), eq("primary_texture", "바삭함"))',
        },
    ),
    (
        "매운 치킨 뭐 있어?",
        {
            "query": "치킨",
            "filter": 'and(eq("product_family", "chicken"), eq("spiciness", "매움"))',
        },
    ),
    (
        "바삭하고 매운 치킨",
        {
            "query": "치킨",
            "filter": 'and(eq("product_family", "chicken"), eq("primary_texture", "바삭함"), eq("spiciness", "매움"))',
        },
    ),
    (
        "2만원 이하 순한 치킨",
        {
            "query": "치킨",
            "filter": 'and(eq("product_family", "chicken"), lte("price", 20000), eq("spiciness", "순함"))',
        },
    ),
    (
        "부드러운 치킨",
        {
            "query": "치킨",
            "filter": 'and(eq("product_family", "chicken"), eq("primary_texture", "부드러움"))',
        },
    ),
    (
        "안 매운 바삭한 치킨 추천",
        {
            "query": "치킨",
            "filter": 'and(eq("product_family", "chicken"), eq("primary_texture", "바삭함"), eq("spiciness", "순함"))',
        },
    ),
]


def _query_contains_any(query: str, terms: tuple[str, ...]) -> bool:
    return any(term in query for term in terms)


def requires_self_query(query: str) -> bool:
    normalized = query.replace(" ", "")

    if PRICE_QUERY_PATTERN.search(query) or _query_contains_any(
        normalized, PRICE_QUERY_TERMS
    ):
        return True
    if _query_contains_any(query, EXCLUSION_QUERY_TERMS) or _query_contains_any(
        normalized, EXCLUSION_QUERY_TERMS
    ):
        return True
    if _query_contains_any(query, NEGATED_SPICY_TERMS) or _query_contains_any(
        normalized, NEGATED_SPICY_TERMS
    ):
        return True

    trait_count = 0
    if _query_contains_any(normalized, TEXTURE_QUERY_TERMS):
        trait_count += 1
    if _query_contains_any(normalized, SPICINESS_QUERY_TERMS):
        trait_count += 1

    return trait_count >= 1


def infer_requested_family(query: str) -> str | None:
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


def _canonical_product_family(value: object) -> str:
    family = str(value or "unknown")
    if family in {"main_chicken", "single_chicken", "combo_chicken"}:
        return "chicken"
    return family


def _infer_product_type_from_metadata(meta: dict, raw_family: str) -> str:
    product_type = str(meta.get("product_type") or "").strip()
    if product_type:
        return product_type

    category = str(meta.get("category") or "").strip()
    family = str(raw_family or "").strip()
    if family == "combo_chicken" or category == "세트메뉴":
        return "set_menu"
    if family in {"main_chicken", "single_chicken", "chicken"}:
        return "main_menu"
    if family in {"side", "sauce", "drink"}:
        return family
    if category in {"후라이드", "양념", "구이", "1인분 메뉴", "반반", "시즈닝", "피자&버거"}:
        return "main_menu"
    if category == "사이드메뉴":
        return "side"
    if category == "소스&시즈닝&무":
        return "sauce"
    if category == "음료":
        return "drink"
    return "unknown"


def _looks_like_generic_menu_query(
    query: str,
    *,
    requested_family: str | None,
    has_criteria: bool,
) -> bool:
    if requested_family or has_criteria:
        return False
    normalized = query.replace(" ", "")
    return "메뉴" in normalized and ("추천" in normalized or "뭐" in normalized)


def _filter_generic_menu_scope(
    query: str,
    items: list[dict],
    *,
    requested_family: str | None,
    has_criteria: bool,
) -> list[dict]:
    if not _looks_like_generic_menu_query(
        query,
        requested_family=requested_family,
        has_criteria=has_criteria,
    ):
        return items

    return [
        item
        for item in items
        if str(item.get("product_type") or "unknown") in DEFAULT_MENU_PRODUCT_TYPES
    ]


def _apply_post_retrieval_filters(
    query: str,
    items: list[dict],
    *,
    requested_family: str | None,
    has_criteria: bool,
) -> list[dict]:
    filtered = _filter_by_requested_family(items, requested_family)
    filtered = filter_items_by_recommendation_profile(query, filtered)
    return _filter_generic_menu_scope(
        query,
        filtered,
        requested_family=requested_family,
        has_criteria=has_criteria,
    )


@lru_cache(maxsize=1)
def build_self_query_retriever() -> SelfQueryRetriever:
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

    return SelfQueryRetriever(
        query_constructor=query_constructor,
        vectorstore=vectorstore,
        structured_query_translator=ChromaTranslator(),
        search_kwargs={"k": TOP_K},
        verbose=True,
    )


class MenuSearchService:
    def __init__(
        self,
        *,
        retriever_loader: Callable[[], Any] = build_self_query_retriever,
        redis_cache: RedisRetrieverCache | None = None,
    ) -> None:
        self._retriever_loader = retriever_loader
        self._redis_cache = redis_cache

    def search(
        self,
        query: str,
        *,
        k: int = TOP_K,
        cache: dict | None = None,
        use_cache: bool = True,
    ) -> list[dict]:
        criteria = detect_recommendation_criteria(query)
        cache = cache or {}
        if use_cache and query in cache and not criteria:
            return list(cache[query])

        requested_family = infer_requested_family(query)
        cache_key = {"query": query, "k": k}
        docs = None
        if use_cache and self._redis_cache:
            docs = self._redis_cache.get_documents(cache_key)
        if docs is None:
            docs = self._retrieve(query, k=k, has_criteria=bool(criteria))
            if use_cache and self._redis_cache and docs:
                self._redis_cache.set_documents(cache_key, list(docs))

        results = self._documents_to_menu_items(docs)
        results = _apply_post_retrieval_filters(
            query,
            results,
            requested_family=requested_family,
            has_criteria=bool(criteria),
        )

        if not results and not criteria:
            docs = self._invoke_retriever(query, k)
            if use_cache and self._redis_cache and docs:
                self._redis_cache.set_documents(cache_key, list(docs))
            results = self._documents_to_menu_items(docs)
            results = _apply_post_retrieval_filters(
                query,
                results,
                requested_family=requested_family,
                has_criteria=False,
            )

        return rerank_menu_items(query, results)

    def _retrieve(self, query: str, *, k: int, has_criteria: bool) -> Sequence[Any]:
        if has_criteria:
            retrieval_query = build_criteria_retrieval_query(query)
            return self._invoke_retriever(retrieval_query, max(k, CRITERIA_TOP_K))

        strict_filter = extract_rule_based_filters(query)
        if strict_filter:
            return self._rule_filter_search(query, k, strict_filter)
        return self._similarity_search(query, k)

    def _rule_filter_search(
        self,
        query: str,
        k: int,
        strict_filter: dict[str, Any],
    ) -> Sequence[Any]:
        for candidate in build_relaxed_filter_candidates(strict_filter):
            docs = self._similarity_search(query, k, candidate)
            if docs:
                return docs
        return []

    def _invoke_retriever(self, query: str, k: int) -> Sequence[Any]:
        retriever = self._retriever_loader()
        if not hasattr(retriever, "search_kwargs"):
            return retriever.invoke(query)

        original_search_kwargs = dict(getattr(retriever, "search_kwargs") or {})
        retriever.search_kwargs = {**original_search_kwargs, "k": k}
        try:
            return retriever.invoke(query)
        finally:
            retriever.search_kwargs = original_search_kwargs

    def _similarity_search(
        self,
        query: str,
        k: int,
        filter_candidate: dict[str, Any] | None = None,
    ) -> Sequence[Any]:
        retriever = self._retriever_loader()
        vectorstore = getattr(retriever, "vectorstore", None)
        if vectorstore is None or not callable(
            getattr(vectorstore, "similarity_search", None)
        ):
            return self._invoke_retriever(query, k)
        if filter_candidate:
            return vectorstore.similarity_search(query, k=k, filter=filter_candidate)
        return vectorstore.similarity_search(query, k=k)

    def _documents_to_menu_items(self, docs: Sequence[Any]) -> list[dict]:
        results = []
        for doc in docs:
            meta = doc.metadata
            raw_product_family = meta.get("product_family", "unknown") or "unknown"
            product_family = _canonical_product_family(raw_product_family)
            product_type = _infer_product_type_from_metadata(meta, str(raw_product_family))
            results.append(
                {
                    "name": meta.get("name", ""),
                    "category": meta.get("category", ""),
                    "price": meta.get("price", 0),
                    "allergy": meta.get("allergy", ""),
                    "texture": meta.get("texture", ""),
                    "spiciness": meta.get("spiciness", ""),
                    "primary_texture": meta.get(
                        "primary_texture",
                        meta.get("texture", ""),
                    ),
                    "product_type": product_type,
                    "nutrition": meta.get("nutrition", ""),
                    "options": meta.get("options", ""),
                    "description": doc.page_content,
                    "imageURL": meta.get("imageURL", ""),
                    "product_family": product_family,
                    "cooking_method": meta.get("cooking_method", ""),
                    "sauce_style": meta.get("sauce_style", ""),
                    "option_tags": meta.get("option_tags", ""),
                }
            )
        return results
