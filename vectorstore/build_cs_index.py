"""
BBQ CS 데이터를 FAISS + BM25 인덱스로 인덱싱하는 오프라인 스크립트.

실행 방법:
    python -m vectorstore.build_cs_index
"""

import os
import pickle
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

load_dotenv()

DATA_PATH = Path(__file__).parent.parent / "Data" / "BBQ_CS.xlsx"
FAISS_PATH = Path(__file__).parent / "faiss_index"
BM25_PATH  = Path(__file__).parent / "bm25_index.pkl"


def build_document(row: pd.Series) -> Document:
    """한 행을 하나의 Document로 변환.

    page_content: LLM 검색 및 BM25에 사용할 텍스트
    metadata:     필터링 및 출처 추적용
    """
    lines = []
    if pd.notna(row.get("CS 구분")):
        lines.append(f"CS 구분: {row['CS 구분']}")
    if pd.notna(row.get("주 내용")):
        lines.append(f"주 내용: {row['주 내용']}")
    if pd.notna(row.get("대응 방법")):
        lines.append(f"대응 방법: {row['대응 방법']}")
    if pd.notna(row.get("조치 사항")):
        lines.append(f"조치 사항: {row['조치 사항']}")
    if pd.notna(row.get("참고")) and str(row.get("참고")) != "nan":
        lines.append(f"참고: {row['참고']}")

    metadata = {
        "cs_category":    str(row.get("CS 구분", "")),
        "claim_category": str(row.get("클레임 카테고리", "")),
        "index":          int(row.get("구분", 0)),
    }
    return Document(page_content="\n".join(lines), metadata=metadata)


def build_index() -> None:
    print(f"[1/5] 데이터 로드: {DATA_PATH}")
    df = pd.read_excel(DATA_PATH)
    print(f"      CS 항목 수: {len(df)}")

    print("[2/5] Document 생성")
    documents = [build_document(row) for _, row in df.iterrows()]

    print("[3/5] 임베딩 모델 초기화 (text-embedding-3-large)")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    print(f"[4/5] FAISS 인덱스 생성 → {FAISS_PATH}")
    vectorstore = FAISS.from_documents(documents, embeddings)
    FAISS_PATH.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(FAISS_PATH))
    print(f"      FAISS 저장 완료.")

    print(f"[5/5] BM25 인덱스 생성 → {BM25_PATH}")
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = 3
    with open(BM25_PATH, "wb") as f:
        pickle.dump(bm25_retriever, f)
    print(f"      BM25 저장 완료.")


if __name__ == "__main__":
    build_index()
