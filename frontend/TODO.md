# Frontend TODO

## 완료
- [x] 타입 정의 (`src/types/chat.ts`) 및 `Message` 유니온 구성
- [x] Mock API (`src/lib/mockApi.ts`) 추가
- [x] API 레이어 (`src/lib/api.ts`) 구성
- [x] `ChatContainer` 채팅 상태 관리 및 에러 핸들링
- [x] `MessageList` 자동 스크롤 및 빈 상태 UI
- [x] `MessageBubble` text / clarification 렌더링
- [x] `MenuCard` / `MenuCardList` 메뉴 카드 렌더링
- [x] `InputBar` 자동 높이, Enter 전송, Shift+Enter 줄바꿈
- [x] `TypingIndicator` 로딩 애니메이션
- [x] `globals.css` Tailwind v4 및 전체 높이 레이아웃
- [x] Production build 통과
- [x] `react-markdown` + `remark-gfm` 적용
- [x] `MenuCard` allergy / options 조건부 표시와 가격 강조
- [x] `MenuCardList` 헤더 강조 및 BBQ 브랜딩 반영
- [x] 실제 백엔드 API 연동 (`src/lib/api.ts`)
- [x] `/api/chat` Next.js Route Handler 추가
- [x] `frontend/CLAUDE.md`를 폴더 전용 작업 지침으로 재구성
- [x] 프론트 전용 규칙을 `frontend/CLAUDE.md`로 통합
- [x] 프론트 중복 지침 파일 정리

## 미완료
- [ ] 스트리밍 응답 지원 (ReadableStream / SSE)
- [ ] 대화 히스토리 백엔드 전송
- [ ] 에러 바운더리 컴포넌트 추가
- [ ] 접근성 개선: 새 메시지용 `aria-live`
