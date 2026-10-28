# Benchmarks TODO

## 완료

- [x] 메뉴 조건 충족률과 후속 추천 중복률 계산 함수 추가
- [x] 메뉴·CS 검색 A/B 실행 도구 추가
- [x] Redis Cold/Warm Cache 지연 측정 도구 추가
- [x] 메뉴 조건 및 후속 추천 시드 시나리오 추가

## 다음 단계

- [ ] 메뉴 조건 케이스를 최소 50건으로 확장
- [ ] CS 골든셋을 최소 40건으로 확장
- [x] HTTP 기반 SSE TTFT/완료 시간 측정 도구 추가
- [x] SSE 성공·오류 건수를 분리해 기록하도록 보완
- [x] 토큰이 없는 메뉴 SSE의 첫 message 이벤트 지연 측정 추가
- [x] SSE 반복 측정과 1·5·10 동시 요청 부하 측정 추가
- [x] LangGraph 실행별 실제 LLM 토큰·추정 비용 프로파일 추가
- [x] API 반환 근거 기반 LLM-as-a-judge 답변 근거 일치율 측정 추가
- [x] CS retriever 가중치 및 전처리 ablation 도구 추가
- [x] 규칙 기반 intent 라우팅 평가 도구 추가
- [ ] CI에서 외부 API 없이 실행 가능한 벤치마크 메트릭 테스트 고정
- [ ] LLM provider 연결 오류를 해결한 뒤 SSE 성공률과 TTFT를 재측정
- [x] 중첩된 benchmark 실행 결과를 Git에서 제외
