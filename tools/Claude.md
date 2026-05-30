# tools/

## 폴더 목적
- 그래프가 호출하는 도메인 tool을 정의한다.
- tool 출력은 사람이 아니라 다른 계층이 읽는 계약이므로 JSON 구조를 안정적으로 유지한다.
- 인덱스 로딩, 검색, 결과 정규화는 여기서 처리하고 세션 관리나 라우팅은 하지 않는다.

## 주요 엔트리포인트
| 파일 | 상태 | 역할 |
|---|---|---|
| `search_menu.py` | 사용 중 | Chroma + SelfQueryRetriever 기반 메뉴 검색 |
| `search_cs.py` | 사용 중 | FAISS + BM25 EnsembleRetriever 기반 CS 검색 |
| `ask_clarification.py` | 보류 | 재질문용 typed 응답 helper |
| `final_answer.py` | 보류 | 메뉴 카드 응답 포맷 helper |

## 로컬 계약
- 활성 tool은 모두 JSON 문자열을 반환한다. Python dict를 직접 반환하지 않는다.
- `search_menu(query, state)`는 `{"results": [...]}`를 기본으로 반환한다.
- `search_menu` 결과 각 항목은 최소 `name`, `category`, `price`, `allergy`, `texture`, `spiciness`, `nutrition`, `options`, `description` 키를 유지한다.
- `search_cs(query, state)`는 `{"results": [{"content", "cs_category", "claim_category"}]}` 형태를 유지한다.
- 두 검색 tool 모두 `state`에서 세션 캐시를 읽는다. 캐시 키는 원문 `query` 그대로다.
- `ask_clarification.py`, `final_answer.py`는 현재 그래프에 연결되어 있지 않다. 재사용할 때는 `graph/graph.py` wiring까지 같이 수정한다.

## 수정 원칙
- 검색 정확도 개선을 위해 메타데이터 키를 바꾸면 `vectorstore/CLAUDE.md`와 빌드 스크립트도 함께 갱신한다.
- 프론트 응답 타입에 직접 맞추기 위해 tool 출력 구조를 바꾸지 않는다. 최종 응답 계약은 `graph/`와 API 계층을 통해 노출된다.
- retriever 초기화 경로, collection 이름, top-k를 바꾸면 캐시된 인덱스와 문서도 같이 검증한다.
- 사용하지 않는 helper를 살릴 때는 실제 호출 경로와 종료 조건을 먼저 문서화한다.

## 변경 영향
- `search_menu` 메타데이터 키 변경: `vectorstore/build_menu_index.py`, menu 추천 품질 영향
- `search_cs` 로딩 경로/가중치 변경: `vectorstore/build_cs_index.py`, CS 답변 품질 영향
- 반환 JSON 키 변경: `graph/_extract_response()` 또는 후속 포맷팅 로직 영향

## 검증 방법
- `python test_graph.py`
- 메뉴 검색 규칙을 바꿨다면 메뉴 질의 1건 직접 확인
- CS 검색 규칙을 바꿨다면 CS 질의 1건 직접 확인
- 인덱스 의존 경로/스키마를 바꿨다면 관련 인덱스를 재빌드한 뒤 다시 확인
