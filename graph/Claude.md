# graph/

## 폴더 목적
- LangGraph 상태와 노드 구성을 관리한다.
- 사용자 입력을 `menu`, `cs`, `fallback` 경로로 라우팅한다.
- 세션 캐시(`menu_results`, `cs_results`)를 tool 호출과 연결한다.
- 검색 구현이나 UI 포맷 로직은 이 폴더에 넣지 않는다.

## 주요 엔트리포인트
| 파일 | 역할 |
|---|---|
| `state.py` | 그래프 전체가 공유하는 `AgentState` 정의 |
| `graph.py` | classifier, agent node, fallback node, routing, compiled graph |
| `intent.py` | 휴리스틱 intent 분류, 주문/메뉴 follow-up 감지, LLM 분류 prompt 생성 |

## 로컬 계약
- `AgentState`는 최소 `messages`, `intent`, `response`, `menu_results`, `cs_results`를 유지한다.
- `messages`는 LangChain `BaseMessage` 목록으로 유지한다. 문자열이나 임의 dict로 바꾸지 않는다.
- `menu_results`, `cs_results`는 `{query: results}` 형태의 세션 캐시다.
- 각 노드는 최종적으로 `response: dict`를 남겨야 하며, 최종 타입은 `text`, `clarification`, `menu_cards` 중 하나여야 한다.
- `_extract_response()`는 우선 `ToolMessage`의 typed JSON을 읽고, 없으면 마지막 일반 `AIMessage`를 `text` 응답으로 변환한다.
- `route_intent()`는 `menu_agent`, `menu_followup`, `cs_agent`, `fallback`만 반환한다.

## 객체 지향 로컬 계약
- 그래프 노드 자체는 LangGraph 계약에 맞춰 함수형 인터페이스를 유지한다.
- 여러 노드가 공유하는 정책, 포맷팅, 분기 조건은 작은 클래스로 분리할 수 있다.
- 클래스가 `AgentState` 전체를 장기간 보관하지 않도록 한다. 필요한 값만 메서드 인자로 받는다.
- 그래프 클래스가 검색 실행, 인덱스 로딩, UI 응답 포맷팅까지 직접 책임지지 않게 한다.

## 수정 원칙
- `graph/`는 orchestration 전용이다. 검색 규칙, 데이터 가공, 카드 포맷팅을 이 폴더로 끌어오지 않는다.
- 새 tool을 연결하거나 응답 타입을 추가하면 `main.py`, `frontend/src/app/api/chat/route.ts`, `frontend/src/types/chat.ts`까지 같이 본다.
- `AgentState` 키를 바꾸면 `main.py`의 세션 저장 구조와 `test_graph.py`를 함께 수정한다.
- classifier 기준이나 fallback 정책을 바꿀 때는 `menu`, `menu_followup`, `cs`가 아닌 입력이 어떻게 처리되는지까지 검증한다.

## 변경 영향
- `response` 구조 변경: `main.py`, 프론트 Route Handler, 프론트 타입/렌더러 영향
- 캐시 구조 변경: `main.py`, `tools/search_menu.py`, `tools/search_cs.py` 영향
- 노드 추가/삭제: 라우팅 함수, 테스트 흐름, 스트리밍 이벤트 해석 영향

## 검증 방법
- `python test_graph.py`
- 메뉴 질의 1건과 CS 질의 1건을 실제로 호출해 응답 타입이 기대와 맞는지 확인
- 스트리밍이나 fallback을 건드렸다면 `/chat/stream`과 unknown 입력도 함께 확인
