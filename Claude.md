# BBQ Menu & CS Agent

## 문서 역할
- 루트 `CLAUDE.md`는 저장소 공통 작업 규칙의 단일 기준 문서다.
- 하위 폴더 `CLAUDE.md`는 해당 폴더 전용 책임, 계약, 수정 영향, 검증 기준만 다룬다.
- 하위 문서는 루트 문서를 보완하며, 공통 규칙을 중복해서 반복하지 않는다.

## 프로젝트 구조
- `main.py`: FastAPI 진입점. lifespan으로 서비스 초기화, 라우터 등록.
- `api/`: HTTP 레이어 — 스키마, 예외, 의존성, 서비스, 라우터, SSE 어댑터.
- `graph/`: LangGraph 상태, 의도 분기, 에이전트 실행 흐름 제어.
- `tools/`: 메뉴 검색, CS 검색 등 그래프가 호출하는 도구 구현.
- `vectorstore/`: 메뉴/CS 원천 데이터를 검색 인덱스로 빌드.
- `test_graph.py`: 그래프 동작 확인용 스모크 테스트.
- `frontend/src/`: Next.js App Router, API 프록시, 채팅 UI, 공용 타입.

## API 엔드포인트 (v2)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/sessions` | 세션 생성 |
| GET | `/sessions/{id}` | 세션 메타데이터 조회 |
| GET | `/sessions/{id}/messages` | 메시지 이력 조회 (limit/offset) |
| POST | `/sessions/{id}/messages` | AI 없이 메시지 저장 |
| DELETE | `/sessions/{id}` | 세션 삭제 |
| POST | `/sessions/{id}/responses` | 동기 AI 응답 생성 |
| POST | `/sessions/{id}/responses/stream` | SSE 스트리밍 응답 (웹 메인 경로) |
| GET | `/knowledge/status` | 인덱스 상태 확인 |
| GET | `/knowledge/documents` | 지식 문서 목록 |
| POST | `/knowledge/indexes/rebuild` | 인덱스 재빌드 (202 비동기) |
| POST | `/knowledge/retrieval/search-preview` | RAG 검색 미리보기 |
| GET | `/health` | 헬스체크 |

## 폴더 경계
| 폴더 | 책임 | 여기서 하지 말 것 |
|---|---|---|
| `api/` | HTTP 계약, 요청/응답 직렬화, 서비스 조합 | 그래프 로직, 인덱스 빌드, LangChain 직접 호출 |
| `graph/` | 상태 정의, 의도 분기, 에이전트 orchestration, 검색 캐시 연결 | 검색 구현, 인덱스 빌드, UI 포맷 |
| `tools/` | 개별 tool 입출력 계약, retriever 호출, 결과 JSON 구성 | 세션 관리, 라우팅, 프론트 렌더링 |
| `vectorstore/` | 원천 데이터 로드, 문서/메타데이터 생성, 인덱스 산출물 저장 | 요청 처리, 실시간 API 응답 |
| `frontend/` | 채팅 UI, Route Handler, 프론트 타입 변환 | 백엔드 검색 규칙, 인덱스 생성 |

## 주요 명령
- 백엔드 가상환경 생성: `python -m venv venv && .\venv\Scripts\activate`
- 백엔드 의존성 설치: `pip install -r requirements.txt`
- 백엔드 실행: `uvicorn main:app --reload`
- 그래프 확인: `python test_graph.py`
- 메뉴 인덱스 재빌드: `python vectorstore\build_menu_index.py`
- CS 인덱스 재빌드: `python vectorstore\build_cs_index.py`
- 프론트 의존성 설치: `cd frontend && npm install`
- 프론트 개발 서버: `cd frontend && npm run dev`
- 프론트 린트: `cd frontend && npm run lint`

## 공통 작업 원칙
- 백엔드 에이전트 로직은 `graph/`, `tools/`에 둔다.
- UI 관련 변경은 `frontend/src/` 안에서 처리한다.
- `CLAUDE.md`에는 작업 로그, 완료 현황판, 긴 회고를 쌓지 않는다.
- 크로스폴더 계약을 바꾸기 전에 관련 폴더 `CLAUDE.md`를 먼저 확인한다.
- 응답 타입, 세션 구조, 인덱스 경로나 메타데이터처럼 여러 폴더에 영향을 주는 규칙을 바꾸면 관련 문서도 함께 갱신한다.

## 코딩 규칙
- Python은 4칸 들여쓰기를 사용하고 PEP 8을 따른다.
- Python 함수, 변수, 모듈 이름은 `snake_case`를 사용한다.
- FastAPI와 LangGraph 코드는 가능한 범위에서 타입을 유지한다.
- 프론트엔드는 TypeScript를 사용하고, 컴포넌트 파일명은 `ChatContainer.tsx`처럼 PascalCase를 사용한다.
- 프론트 helper는 `src/lib/` 아래에서 camelCase를 사용한다.
- 큰 파일 하나에 여러 책임을 섞기보다 작은 모듈로 나눈다.

## 주석 규칙
- 주석은 꼭 필요한 경우에만 단다.
- 주석은 동작을 다시 읽어주는 말보다 의도, 이유, 주의점을 설명해야 한다.
- 주석은 처음 보는 사람이 바로 이해할 수 있게 쉽게 쓴다.
- 코드 주석은 한글로만 작성한다.

## 크로스폴더 계약
- 백엔드 최종 응답 타입은 `text`, `clarification`, `menu_cards`만 사용한다.
- `main.py`는 세션별 `messages`, `menu_results`, `cs_results`를 유지하고 `graph/`에 전달한다.
- `graph/`의 `response`는 FastAPI 응답으로 전달되고, `frontend/src/app/api/chat/route.ts`에서 프론트엔드 `Message` 타입으로 변환된다.
- `vectorstore/`의 메타데이터 키와 저장 경로는 `tools/search_menu.py`, `tools/search_cs.py`와 일치해야 한다.
- `/chat/stream`을 변경하면 토큰 이벤트와 최종 `response` 이벤트가 모두 유지되는지 확인한다.

## 검증 기준
- `graph/`, `tools/` 변경 후: `python test_graph.py`
- `frontend/` 변경 후: `cd frontend && npm run lint`
- 검색 데이터나 인덱스 로직 변경 후: 관련 인덱스 재빌드 + 메뉴 질의 1건, CS 질의 1건 수동 확인
- 스트리밍 또는 응답 계약 변경 후: `/chat`, `/chat/stream` 둘 다 확인

## 커밋과 PR 규칙
- 최근 히스토리처럼 짧고 직접적인 제목을 사용하되, 가능하면 변경 영역을 앞에 붙인다.
- 예시: `graph: route unknown intents to fallback`
- 커밋은 한 가지 관심사에 맞게 작게 나눈다.
- PR에는 요약, 영향받은 경로, 수동 테스트 방법, 화면 변경 시 스크린샷을 포함한다.
- 환경 변수나 인덱스 재빌드가 필요하면 PR 본문에 적는다.

## 보안과 설정
- 비밀 값은 `.env`에 저장하고 저장소에 커밋하지 않는다.
- `vectorstore/` 아래 대용량 인덱스 산출물은 원천 데이터가 바뀐 경우에만 갱신한다.

## 문서 유지 규칙
- 변경한 파일이 속한 폴더의 `CLAUDE.md`를 최신 규칙에 맞게 갱신한다.
- 변경한 파일이 속한 폴더의 `TODO.md`를 체크하거나, 없으면 생성한다.
- 새 하위 `CLAUDE.md`는 `폴더 목적`, `주요 엔트리포인트`, `로컬 계약`, `수정 원칙`, `검증 방법` 순서를 기본으로 삼는다.
