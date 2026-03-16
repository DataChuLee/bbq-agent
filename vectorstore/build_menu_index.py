"""
BBQ 메뉴 데이터를 ChromaDB에 인덱싱하는 오프라인 스크립트.

실행 방법:
    python -m vectorstore.build_menu_index
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

DATA_PATH = Path(__file__).parent.parent / "Data" / "bbq_menu.json"
CHROMA_PATH = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "bbq_menu"


def build_embedding_text(item: dict) -> str:
    """임베딩에 사용할 텍스트 구성.

    포맷: "메뉴명 | 카테고리 | 설명 | 알레르기: {알레르기 정보}"
    """
    parts = [
        item.get("메뉴명", ""),
        item.get("구분", ""),
        item.get("설명", ""),
        f"알레르기: {item.get('알레르기 정보', '')}",
    ]
    return " | ".join(p for p in parts if p)


def build_metadata(item: dict) -> dict:
    """SelfQueryRetriever 필터용 메타데이터 구성."""
    return {
        "price":    int(item.get("가격", 0)),
        "category": str(item.get("구분", "")),
        "allergy":  str(item.get("알레르기 정보", "")),
        "origin":   str(item.get("원산지", "")),
        "nutrition": str(item.get("영양 정보", "")),
        "options":  str(item.get("구매 옵션", "")),
        "name":     str(item.get("메뉴명", "")),
    }


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
    # 기존 컬렉션 삭제 후 재생성 (멱등성 보장)
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_PATH),
    )
    print(f"      저장 완료. 총 {vectorstore._collection.count()}개 벡터 저장됨.")


if __name__ == "__main__":
    build_index()
