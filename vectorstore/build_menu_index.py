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


def build_embedding_text(item: dict) -> str:
    """임베딩에 사용할 텍스트 구성.

    포맷: "메뉴명 | 카테고리 | 설명 | 알레르기: {알레르기 정보}"
    """
    parts = [
        item.get("메뉴명", ""),
        item.get("구분", ""),
        item.get("설명", ""),
        f"알레르기: {item.get('알레르기 정보', '')}",
        f"식감: {item.get('식감', item.get('texture', ''))}",
        f"맵기: {item.get('맵기', item.get('spiciness', ''))}",
    ]
    return " | ".join(p for p in parts if p)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def derive_product_family(item: dict) -> str:
    """Return a normalized menu family used for retrieval post-filtering."""
    category = str(item.get("구분", ""))
    name = str(item.get("메뉴명", ""))

    if category in BURGER_PIZZA_CATEGORIES:
        return "burger_pizza"
    if category in SINGLE_CHICKEN_CATEGORIES:
        return "single_chicken"
    if category in COMBO_CHICKEN_CATEGORIES:
        return "combo_chicken"
    if category in MAIN_CHICKEN_CATEGORIES:
        return "main_chicken"
    if _contains_any(name, SIDE_NAME_TERMS):
        return "side"
    if _contains_any(name, DRINK_NAME_TERMS):
        return "drink"
    if _contains_any(name, SAUCE_NAME_TERMS):
        return "sauce"
    if _contains_any(name, SEASONING_NAME_TERMS):
        return "seasoning"
    if _contains_any(name, CHICKEN_NAME_TERMS):
        return "main_chicken"
    return "unknown"


def build_metadata(item: dict) -> dict:
    """SelfQueryRetriever 필터용 메타데이터 구성."""
    return {
        "price":    int(item.get("가격", 0)),
        "category": str(item.get("구분", "")),
        "allergy":  str(item.get("알레르기 정보", "")),
        "texture": str(item.get("식감", item.get("texture", ""))),
        "spiciness": str(item.get("맵기", item.get("spiciness", ""))),
        "origin":   str(item.get("원산지", "")),
        "nutrition": str(item.get("영양 정보", "")),
        "options":  str(item.get("구매 옵션", "")),
        "name":     str(item.get("메뉴명", "")),
        "imageURL": str(item.get("imageURL", "")),
        "product_family": derive_product_family(item),
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
