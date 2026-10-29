# tests TODO

## 완료
- [x] 답변 근거 일치율 집계에서 비사실 항목을 제외하는지 검증
- [x] SSE 실행 오류 시 error 이벤트를 보내고 부분 응답을 저장하지 않는지 검증
- [x] 커스텀 RAG 검색 메트릭 단위 테스트 추가
- [x] 메뉴/CS 골든셋 정답 ID 검증 테스트 추가
- [x] CS 전처리와 메뉴 필터 fallback 규칙 테스트 추가
- [x] 메뉴 rule filter 우선 검색, CS 검색 서비스, intent 휴리스틱 단위 테스트 추가
- [x] Redis retriever 캐시 hit/miss/장애 fallback 테스트 추가
- [x] CS 검색 기본 경로가 실험에서 선택한 원문 질의를 유지하는지 테스트 추가
- [x] 동기 응답과 SSE 완료 이벤트의 source 계약 검증
- [x] CS 검색 실패와 정상 빈 결과를 구분하는 회귀 테스트 추가
- [x] 일반 대화 fallback과 조건 추가 메뉴 follow-up 테스트 추가
- [x] OpenAPI에서 legacy `/search` 제거와 search-preview 계약 유지 검증
- [x] 메뉴 메타데이터 검수에서 찾은 오분류 회귀 테스트 추가

## 미완료
