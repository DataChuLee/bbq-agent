# tools/

## 폴더 목적
- 그래프가 호출하는 도메인 tool을 정의한다.
- tool 출력은 사람이 아니라 다른 계층이 읽는 계약이므로 JSON 구조를 안정적으로 유지한다.
- 인덱스 로딩, 검색, 결과 정규화는 여기서 처리하고 세션 관리나 라우팅은 하지 않는다.

## 주요 엔트리포인트
| 파일 | 상태 | 역할 |
|---|---|---|
| `search_menu.py` | 사용 중 | 메뉴 검색 LangGraph tool 어댑터 |
| `menu_retrieval.py` | 사용 중 | Chroma + rule filter + SelfQuery fallback 기반 메뉴 검색 서비스 |
| `menu_query_rules.py` | 사용 중 | 메뉴 자연어 조건을 Chroma metadata filter로 변환 |
| `search_cs.py` | 사용 중 | CS 검색 LangGraph tool 어댑터 |
| `cs_retrieval.py` | 사용 중 | FAISS + BM25 EnsembleRetriever 기반 CS 검색 서비스 |
| `retrieval_cache.py` | 사용 중 | Redis 기반 retriever 결과 캐시 |
| `ask_clarification.py` | 보류 | 재질문용 typed 응답 helper |
| `final_answer.py` | 보류 | 메뉴 카드 응답 포맷 helper |

## 로컬 계약
- 활성 tool은 모두 JSON 문자열을 반환한다. Python dict를 직접 반환하지 않는다.
- `search_menu(query, state)`는 `{"results": [...]}`를 기본으로 반환한다.
- `search_menu` 결과 각 항목은 최소 `name`, `category`, `price`, `allergy`, `texture`, `spiciness`, `nutrition`, `options`, `description` 키를 유지한다.
- 메뉴 조건 질의는 `menu_query_rules.py`의 규칙 기반 metadata filter를 먼저 사용하고, 결과가 없으면 완화된 filter와 fallback 검색을 순서대로 사용한다.
- `search_cs(query, state)`는 `{"results": [{"content", "cs_category", "claim_category"}]}` 형태를 유지한다.
- 두 검색 tool 모두 `state`에서 세션 캐시를 읽는다. 캐시 키는 원문 `query` 그대로다.
- Redis 캐시는 retriever 문서 결과만 저장하는 성능 최적화 계층이다. Redis 조회/쓰기 실패 시 검색 결과 생성은 계속 진행해야 한다.
- 기본 Redis TTL은 메뉴 `86400`초, CS `3600`초다. `REDIS_CACHE_ENABLED=false`면 Redis 캐시를 사용하지 않는다.
- `ask_clarification.py`, `final_answer.py`는 현재 그래프에 연결되어 있지 않다. 재사용할 때는 `graph/graph.py` wiring까지 같이 수정한다.

## 객체 지향 로컬 계약
- retriever 초기화, 검색 실행, 결과 정규화가 함께 움직이는 로직은 서비스 클래스로 묶는다.
- tool 함수는 LangGraph와 연결되는 얇은 어댑터로 유지하고, 실제 검색 로직은 서비스 클래스에 위임한다.
- 서비스 클래스는 인덱스 경로, retriever, top-k 같은 의존성을 생성자에서 받는다.
- 서비스 클래스는 세션 관리나 라우팅을 직접 하지 않는다. 필요한 캐시 데이터는 호출 시 명시적으로 전달한다.
- Redis 캐시는 서비스 클래스에 주입하며, 서비스가 Redis client를 직접 생성하지 않는다.
- 반환 JSON 계약은 기존 tool 함수에서 유지한다.

## 수정 원칙
- 검색 정확도 개선을 위해 메타데이터 키를 바꾸면 `vectorstore/CLAUDE.md`와 빌드 스크립트도 함께 갱신한다.
- 프론트 응답 타입에 직접 맞추기 위해 tool 출력 구조를 바꾸지 않는다. 최종 응답 계약은 `graph/`와 API 계층을 통해 노출된다.
- retriever 초기화 경로, collection 이름, top-k를 바꾸면 캐시된 인덱스와 문서도 같이 검증한다.
- 사용하지 않는 helper를 살릴 때는 실제 호출 경로와 종료 조건을 먼저 문서화한다.

## 변경 영향
- `search_menu` 메타데이터 키 변경: `vectorstore/build_menu_index.py`, menu 추천 품질 영향
- `search_cs` 로딩 경로/가중치/질의 정규화 변경: `vectorstore/build_cs_index.py`, CS 답변 품질 영향
- Redis namespace/TTL 변경: 반복 질의 응답 속도와 캐시 신선도 영향
- 반환 JSON 키 변경: `graph/_extract_response()` 또는 후속 포맷팅 로직 영향

## 검증 방법
- `python test_graph.py`
- 메뉴 검색 규칙을 바꿨다면 메뉴 질의 1건 직접 확인
- CS 검색 규칙을 바꿨다면 CS 질의 1건 직접 확인
- 인덱스 의존 경로/스키마를 바꿨다면 관련 인덱스를 재빌드한 뒤 다시 확인
