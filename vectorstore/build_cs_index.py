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
# 원본은 상담원용 매뉴얼이라 내부 정책(보상 조건 등)이 섞여 있다. 고객에게는 검수한 문구만 보낸다.
CUSTOMER_PATH = Path(__file__).parent.parent / "Data" / "BBQ_CS_customer.csv"
FAISS_PATH = Path(__file__).parent / "faiss_index"
BM25_PATH  = Path(__file__).parent / "bm25_index.pkl"


# 원본에 클레임 카테고리가 비어 있는 구분은 성격이 같은 카테고리로 채운다.
MISSING_CLAIM_CATEGORY = {"치킨 조각 수": "제품 문의"}


def build_document(row: pd.Series, customer: pd.Series) -> Document:
    """세부 상황 하나를 Document 하나로 만든다.

    page_content: 검색(임베딩, BM25)에만 쓰는 텍스트. 고객 문의 말투와 가까운 고객 안내 문구로 검색한다.
    metadata:     고객 안내 문구, 계층 필터(claim_category → cs_category → sub_case), 출처 추적용
    """
    name = str(row["CS 구분"])
    summary = " ".join(str(row.get("주 내용", "")).split())
    sub_case = str(customer["세부 상황"])
    lines = [f"CS 구분: {name}", f"주 내용: {summary}"]
    if sub_case:
        lines.append(f"세부 상황: {sub_case}")
    lines.append(f"고객 안내: {customer['고객 안내']}")

    claim = row.get("클레임 카테고리")
    metadata = {
        "cs_category":    name,
        "claim_category": str(claim) if pd.notna(claim) else MISSING_CLAIM_CATEGORY[name],
        "index":          int(row.get("구분", 0)),
        "summary":        summary,
        "sub_case":       sub_case,
        "customer_answer":  str(customer["고객 안내"]),
        "customer_request": str(customer["고객에게 받을 것"]),
    }
    return Document(page_content="\n".join(lines), metadata=metadata)


def build_index() -> None:
    print(f"[1/5] 데이터 로드: {DATA_PATH}")
    df = pd.read_excel(DATA_PATH)
    print(f"      CS 항목 수: {len(df)}")

    print("[2/5] Document 생성")
    customer = pd.read_csv(CUSTOMER_PATH, encoding="utf-8-sig", keep_default_na=False)
    missing = set(df["CS 구분"].astype(str)) - set(customer["CS 구분"])
    if missing:
        raise SystemExit(f"고객 안내 문구가 없는 CS 구분: {sorted(missing)}")
    rows = {str(row["CS 구분"]): row for _, row in df.iterrows()}
    documents = [build_document(rows[c["CS 구분"]], c) for _, c in customer.iterrows()]
    print(f"      세부 상황 문서 수: {len(documents)}")

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
