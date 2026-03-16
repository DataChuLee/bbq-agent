# vectorstore/ — 작업 내역

## 파일 목록

| 파일 | 역할 |
|---|---|
| `__init__.py` | 패키지 초기화 |
| `build_menu_index.py` | `bbq_menu.json` → ChromaDB 인덱싱 스크립트 |
| `build_cs_index.py` | `BBQ_CS.xlsx` → FAISS + BM25 인덱싱 스크립트 (Step 4에서 작성) |
| `chroma_db/` | ChromaDB 영구 저장 디렉토리 (인덱싱 실행 후 생성) |
| `faiss_index/` | FAISS 인덱스 저장 디렉토리 (인덱싱 실행 후 생성) |

---

## build_menu_index.py

### 실행 방법
```bash
python -m vectorstore.build_menu_index
```

### 처리 흐름

```
Data/bbq_menu.json (93개 항목)
    │
    ▼
임베딩 텍스트 조합
"메뉴명 | 구분 | 설명 | 알레르기: {알레르기 정보}"
    │
    ▼
메타데이터 추출
{ price, category, allergy, origin, nutrition, options, name }
    │
    ▼
text-embedding-3-large 임베딩
    │
    ▼
ChromaDB 저장 (collection: bbq_menu)
vectorstore/chroma_db/
```

### 필드별 처리 방식

| JSON 필드 | 임베딩 텍스트 | 메타데이터 | 이유 |
|---|---|---|---|
| 메뉴명 | O | O (name) | 의미론적 검색 핵심 |
| 구분 (카테고리) | O | O (category) | 검색 + 필터링 모두 사용 |
| 설명 | O | — | "매운 거", "담백한 거" 추상 쿼리 대응 |
| 알레르기 정보 | O | O (allergy) | 자연어 쿼리 및 제외 필터링 모두 필요 |
| 가격 | — | O (price, int) | 숫자 범위 필터 (`price <= 20000`) |
| 원산지 | — | O (origin) | 의미론적 검색과 무관 |
| 영양 정보 | — | O (nutrition) | 구조화된 숫자 데이터 |
| 구매 옵션 | — | O (options, JSON str) | 복잡한 JSON, 검색 후 후처리로 매핑 |

### SelfQueryRetriever 메타데이터 스키마 (search_menu.py에서 사용)

```python
metadata_field_info = [
    AttributeInfo(name="price",    description="메뉴 가격 (원)", type="integer"),
    AttributeInfo(name="category", description="메뉴 카테고리 (예: 신메뉴, 사이드)", type="string"),
    AttributeInfo(name="allergy",  description="알레르기 유발 성분 목록", type="string"),
]
```

---

## build_cs_index.py

### 실행 방법
```bash
python -m vectorstore.build_cs_index
```

### 데이터 구조 (BBQ_CS.xlsx — 25행 × 7열)

| 컬럼 | 내용 | Document 활용 |
|---|---|---|
| 구분 | 인덱스 번호 | metadata.index |
| CS 구분 | CS 문의 유형 (예: 기프티콘 거부) | page_content + metadata.cs_category |
| 주 내용 | 문의 세부 제목 | page_content |
| 대응 방법 | 상담사 응대 스크립트 | page_content |
| 클레임 카테고리 | 클레임 분류 | metadata.claim_category |
| 조치 사항 | 후속 처리 내용 | page_content |
| 참고 | 추가 메모 | page_content (nan 제외) |

### Document 포맷
```
CS 구분: 기프티콘 거부
주 내용: 단순 기프티콘 거부
대응 방법: 1. 선 사과 ...
조치 사항: 매장코드 매장명 내용 정리하여 ...
참고: 강성인 경우 보상 제안
```

### 처리 흐름
```
Data/BBQ_CS.xlsx (25개 항목)
    │
    ▼
Document 생성 (행 전체를 하나의 텍스트 블록으로)
    │
    ├──▶ FAISS 벡터 인덱스 (text-embedding-3-large)
    │        vectorstore/faiss_index/
    │
    └──▶ BM25Retriever (pickle)
             vectorstore/bm25_index.pkl
```

### EnsembleRetriever 가중치 (search_cs.py에서 사용)
- BM25: 40%
- FAISS Vector: 60%
- top-k: 3
