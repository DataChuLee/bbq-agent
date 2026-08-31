"""
BBQ 메뉴 데이터를 ChromaDB에 인덱싱하는 오프라인 스크립트.

실행 방법:
    python -m vectorstore.build_menu_index
"""

import json
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

DATA_PATH = Path(__file__).parent.parent / "Data" / "bbq_menu.json"
CHROMA_PATH = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "bbq_menu"

MAIN_CHICKEN_CATEGORIES = {"후라이드", "양념", "구이"}
SINGLE_CHICKEN_CATEGORIES = {"1인분 메뉴"}
COMBO_CHICKEN_CATEGORIES = {"세트메뉴"}
BURGER_PIZZA_CATEGORIES = {"피자&버거"}
SIDE_CATEGORIES = {"사이드메뉴"}
DRINK_CATEGORIES = {"음료"}
SAUCE_CATEGORIES = {"소스&시즈닝&무"}
CHICKEN_STYLE_CATEGORIES = {"반반", "시즈닝"}

SIDE_NAME_TERMS = (
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
    "볼",
)
DRINK_NAME_TERMS = ("콜라", "스프라이트", "레몬보이")
SAUCE_NAME_TERMS = ("소스", "치킨무", "무")
SEASONING_NAME_TERMS = ("시즈닝",)
CHICKEN_NAME_TERMS = ("치킨", "닭", "윙", "봉", "순살", "반마리", "통다리")
PIZZA_NAME_TERMS = ("피자",)
BURGER_NAME_TERMS = ("버거",)
SPICY_NAME_TERMS = ("핫", "매운", "마라", "땡쇼크", "맵소디", "고추")
SAUCED_NAME_TERMS = ("양념", "왕갈비", "자메이카", "빠리", "뿜치킹", "소떡만나")
SOY_SAUCE_NAME_TERMS = ("간장", "블랙페퍼")
SMOKED_NAME_TERMS = ("스모크", "훈연")
BAKED_NAME_TERMS = ("베이크", "구이")
SOUP_NAME_TERMS = ("탕", "떡볶이")
OPTION_TAG_TERMS = ("순살", "반마리", "한마리", "윙", "봉", "닭다리", "콤보")


def build_embedding_text(item: dict) -> str:
    """임베딩에 사용할 텍스트 구성.

    포맷: "메뉴명 | 카테고리 | 설명 | 알레르기: {알레르기 정보}"
    """
    metadata = build_metadata(item)
    parts = [
        item.get("메뉴명", ""),
        item.get("구분", ""),
        item.get("설명", ""),
        f"상품유형: {metadata['product_type']}",
        f"상품군: {metadata['product_family']}",
        f"조리방식: {metadata['cooking_method']}",
        f"소스스타일: {metadata['sauce_style']}",
        f"주요식감: {metadata['primary_texture']}",
        f"알레르기: {item.get('알레르기 정보', '')}",
        f"식감: {metadata['texture']}",
        f"맵기: {metadata['spiciness']}",
        f"옵션태그: {metadata['option_tags']}",
    ]
    return " | ".join(p for p in parts if p)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _item_text(item: dict) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in ("구분", "메뉴명", "설명")
    )


def _option_text(item: dict) -> str:
    return str(item.get("구매 옵션", ""))


def derive_product_type(item: dict) -> str:
    """Return the catalog role used for hard retrieval filtering."""
    category = str(item.get("구분", ""))
    name = str(item.get("메뉴명", ""))

    if category in SAUCE_CATEGORIES:
        return "sauce"
    if category in DRINK_CATEGORIES or _contains_any(name, DRINK_NAME_TERMS):
        return "drink"
    if category in SIDE_CATEGORIES:
        return "side"
    if category == "신메뉴" and _contains_any(name, SIDE_NAME_TERMS):
        return "side"
    if category in COMBO_CHICKEN_CATEGORIES:
        return "set_menu"
    if category in BURGER_PIZZA_CATEGORIES:
        return "main_menu"
    if category in MAIN_CHICKEN_CATEGORIES | SINGLE_CHICKEN_CATEGORIES | CHICKEN_STYLE_CATEGORIES:
        return "main_menu"
    if _contains_any(name, CHICKEN_NAME_TERMS):
        return "main_menu"
    if category == "신메뉴":
        return "main_menu"
    return "unknown"


def derive_product_family(item: dict) -> str:
    """Return a normalized menu family used for retrieval post-filtering."""
    category = str(item.get("구분", ""))
    name = str(item.get("메뉴명", ""))
    product_type = derive_product_type(item)

    if product_type == "sauce":
        if _contains_any(name, SEASONING_NAME_TERMS):
            return "seasoning"
        return "sauce"
    if product_type == "drink":
        return "drink"
    if product_type == "side":
        return "side"
    if category in BURGER_PIZZA_CATEGORIES or _contains_any(name, PIZZA_NAME_TERMS + BURGER_NAME_TERMS):
        if _contains_any(name, PIZZA_NAME_TERMS):
            return "pizza"
        if _contains_any(name, BURGER_NAME_TERMS):
            return "burger"
        return "burger_pizza"
    if product_type in {"main_menu", "set_menu"}:
        return "chicken"
    return "unknown"


def derive_cooking_method(item: dict) -> str:
    category = str(item.get("구분", ""))
    text = _item_text(item)
    product_type = derive_product_type(item)

    if product_type in {"sauce", "drink"}:
        return ""
    if _contains_any(text, SMOKED_NAME_TERMS):
        return "smoked"
    if category == "구이" or _contains_any(text, BAKED_NAME_TERMS):
        return "grilled"
    if product_type == "side" and _contains_any(text, SOUP_NAME_TERMS):
        return "soup"
    if product_type in {"main_menu", "set_menu", "side"}:
        return "fried"
    return ""


def derive_sauce_style(item: dict) -> str:
    category = str(item.get("구분", ""))
    text = _item_text(item)
    product_type = derive_product_type(item)

    if product_type in {"sauce", "drink"}:
        return ""
    if _contains_any(text, SPICY_NAME_TERMS) and (
        category == "양념" or _contains_any(text, SAUCED_NAME_TERMS)
    ):
        return "spicy_sauce"
    if _contains_any(text, SOY_SAUCE_NAME_TERMS):
        return "soy_sauce"
    if category == "양념" or _contains_any(text, SAUCED_NAME_TERMS):
        return "sauced"
    return "none"


def derive_option_tags(item: dict) -> str:
    text = " ".join((str(item.get("메뉴명", "")), _option_text(item)))
    tags = [term for term in OPTION_TAG_TERMS if term in text]
    return ",".join(tags)


def derive_primary_texture(item: dict) -> str:
    product_type = derive_product_type(item)
    if product_type in {"sauce", "drink"}:
        return ""

    cooking_method = derive_cooking_method(item)
    sauce_style = derive_sauce_style(item)
    raw_texture = str(item.get("식감", item.get("texture", "")))

    if sauce_style in {"sauced", "spicy_sauce", "soy_sauce"}:
        return "촉촉함"
    if cooking_method in {"grilled", "smoked"}:
        return "촉촉함"
    return raw_texture


def derive_search_texture(item: dict) -> str:
    if derive_product_type(item) in {"sauce", "drink"}:
        return ""
    return str(item.get("식감", item.get("texture", "")))


def derive_search_spiciness(item: dict) -> str:
    if derive_product_type(item) in {"sauce", "drink"}:
        return ""
    return str(item.get("맵기", item.get("spiciness", "")))


def build_metadata(item: dict) -> dict:
    """SelfQueryRetriever 필터용 메타데이터 구성."""
    return {
        "price":    int(item.get("가격", 0)),
        "category": str(item.get("구분", "")),
        "allergy":  str(item.get("알레르기 정보", "")),
        "texture": derive_search_texture(item),
        "spiciness": derive_search_spiciness(item),
        "primary_texture": derive_primary_texture(item),
        "product_type": derive_product_type(item),
        "product_family": derive_product_family(item),
        "cooking_method": derive_cooking_method(item),
        "sauce_style": derive_sauce_style(item),
        "option_tags": derive_option_tags(item),
        "origin":   str(item.get("원산지", "")),
        "nutrition": str(item.get("영양 정보", "")),
        "options":  str(item.get("구매 옵션", "")),
        "name":     str(item.get("메뉴명", "")),
        "imageURL": str(item.get("imageURL", "")),
    }


def _clear_existing_collection(persist_directory: Path, collection_name: str) -> None:
    if not persist_directory.exists():
        return

    client = chromadb.PersistentClient(path=str(persist_directory))
    try:
        client.delete_collection(collection_name)
    except Exception as exc:
        message = str(exc).lower()
        if "does not exist" not in message and "not found" not in message:
            raise


def build_index() -> None:
    print(f"[1/4] 데이터 로드: {DATA_PATH}")
    with open(DATA_PATH, encoding="utf-8") as f:
        menu_data = json.load(f)
    print(f"      메뉴 항목 수: {len(menu_data)}")

    print("[2/4] Document 생성")
    documents = []
    for item in menu_data:
        doc = Document(
            page_content=build_embedding_text(item),
            metadata=build_metadata(item),
        )
        documents.append(doc)

    print("[3/4] 임베딩 모델 초기화 (text-embedding-3-large)")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    print(f"[4/4] ChromaDB 저장: {CHROMA_PATH} / collection={COLLECTION_NAME}")
    _clear_existing_collection(CHROMA_PATH, COLLECTION_NAME)
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_PATH),
    )
    print(f"      저장 완료. 총 {vectorstore._collection.count()}개 벡터 저장됨.")


if __name__ == "__main__":
    build_index()
