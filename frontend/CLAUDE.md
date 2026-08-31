# frontend/

## 폴더 목적
- Next.js App Router 기반 채팅 UI와 백엔드 프록시를 담당한다.
- 백엔드의 raw 응답을 프론트엔드 `Message` 유니온 타입으로 변환하는 경계는 `src/app/api/chat/route.ts`다.
- UI 컴포넌트는 백엔드 응답 구조를 직접 해석하지 않고 `src/types/chat.ts`를 기준으로 동작한다.

## 주요 엔트리포인트
| 경로 | 역할 |
|---|---|
| `src/app/page.tsx` | 메인 채팅 페이지 |
| `src/app/api/sessions/route.ts` | `POST /sessions` 프록시 — 세션 생성 |
| `src/app/api/chat/route.ts` | `POST /sessions/{id}/responses/stream` SSE 스트림 프록시 |
| `src/components/chat/` | 메시지, 메뉴 카드, 입력창, 로딩 UI |
| `src/lib/api.ts` | `createSession`, `streamMessage` (SSE 파싱 포함) |
| `src/types/chat.ts` | 프론트엔드 메시지 계약 |

## 로컬 계약
- 세션은 `ChatContainer` 마운트 시 `createSession()`으로 생성한다. 생성된 ID는 `sessionIdRef`에 보관한다.
- 메시지 전송은 `streamMessage(sessionId, content, callbacks)`로 처리한다. 응답-응답이 아니라 SSE 스트림이다.
- SSE 이벤트 순서: `start → intent? → token*/manual_checkpoint* → message → done`. `message`의 `sources`를 최종 `Message`에 보존하고, `done`과 `error`에서 로딩·진행 상태를 종료한다.
- 백엔드 `message` 이벤트 페이로드는 `src/lib/api.ts`의 `toMessage()`에서 `Message` 유니온 타입으로 변환한다. `menu_cards` → `cards`, `content` 정규화 포함.
- `MessageList`는 `streamingContent: string | null` prop을 받아 스트리밍 중 토큰을 말풍선으로 표시한다.
- 새 응답 타입을 추가하면 `api.ts:toMessage`, `src/types/chat.ts`, 렌더러 순서로 확장한다.
- 입력창 Enter 전송 규칙을 바꿀 때는 한글 IME 조합 중 전송 방지를 유지한다.

## 수정 원칙
- 백엔드 응답 shape를 여러 컴포넌트가 직접 다루게 만들지 않는다. 타입 변환은 Route Handler에 집중한다.
- 시각 요소 변경과 데이터 계약 변경을 한 파일에 섞지 않는다.
- 현재 프로젝트가 사용하는 Next.js 버전을 기준으로 판단한다.
- Next.js 동작이나 파일 규칙이 헷갈리면 `node_modules/next/dist/docs/`와 실제 프로젝트 구조를 먼저 확인한다.
- 사용 중단 안내나 경고가 보이면 기존 기억보다 현재 버전 문서를 우선한다.

## 변경 영향
- `route.ts` 변경: `src/lib/api.ts`, `src/types/chat.ts`, 채팅 렌더러 영향
- 메시지 타입 변경: 모든 채팅 렌더러와 초기 상태 생성 코드 영향
- 입력 UX 변경: `InputBar`, `ChatContainer`, 수동 QA 영향

## 검증 방법
- `cd frontend && npm run lint`
- `cd frontend && npm run dev` 후 변경한 채팅 흐름 직접 확인
- 입력창 변경 시 빈 입력, 로딩 중 중복 전송, 한글 IME 입력을 함께 확인
