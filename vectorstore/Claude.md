# vectorstore/

## 폴더 목적
- 원천 데이터를 검색 인덱스로 변환하는 오프라인 빌드 스크립트를 관리한다.
- 런타임 요청을 처리하지 않는다. 검색 경로와 메타데이터 계약을 안정적으로 만드는 것이 목적이다.

## 주요 엔트리포인트
| 파일/경로 | 역할 |
|---|---|
| `build_menu_index.py` | `Data/bbq_menu.json`을 Chroma 컬렉션으로 빌드 |
| `build_cs_index.py` | `Data/BBQ_CS.xlsx`를 FAISS + BM25 인덱스로 빌드 |
| `chroma_db/` | 메뉴 검색용 Chroma 영속 저장소 |
| `faiss_index/` | CS 검색용 FAISS 저장소 |
| `bm25_index.pkl` | CS 검색용 BM25 저장소 |

## 로컬 계약
- 메뉴 인덱스는 `collection_name="bbq_menu"`를 유지한다.
- 메뉴 메타데이터는 최소 `price`, `category`, `allergy`, `texture`, `spiciness`, `origin`, `nutrition`, `options`, `name` 키를 유지한다.
- 메뉴 임베딩 텍스트는 메뉴명, 카테고리, 설명, 알레르기, 식감, 맵기 정보를 포함한다.
- CS 문서는 한 행을 하나의 `Document`로 만들고, 메타데이터에 최소 `cs_category`, `claim_category`, `index`를 유지한다.
- 산출물 경로가 바뀌면 `tools/search_menu.py`, `tools/search_cs.py`의 상수 경로도 같이 바꿔야 한다.

## 수정 원칙
- 원천 데이터 컬럼명이나 JSON 키를 바꾸면 build 스크립트와 tool 로딩 규칙을 동시에 맞춘다.
- 메타데이터 스키마를 줄이거나 이름을 바꾸기 전에 검색 필터와 반환 JSON에 어떤 영향이 나는지 먼저 확인한다.
- 임베딩 모델, 컬렉션명, 저장 경로를 바꾸면 기존 인덱스를 재사용하지 말고 새로 빌드한다.
- 대용량 산출물은 소스 데이터가 바뀐 경우에만 갱신한다.

## 재빌드가 필요한 경우
- `Data/bbq_menu.json`, `Data/BBQ_CS.xlsx`가 바뀐 경우
- 메타데이터 키/컬럼 매핑이 바뀐 경우
- 임베딩 모델, 저장 경로, 컬렉션명, 문서 구성 방식이 바뀐 경우

## 검증 방법
- 메뉴 변경: `python -m vectorstore.build_menu_index`
- CS 변경: `python -m vectorstore.build_cs_index`
- 빌드 후 메뉴 질의 1건, CS 질의 1건을 실제 검색 흐름으로 확인
