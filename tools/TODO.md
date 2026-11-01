# tools TODO

## 완료
- [x] `tools/CLAUDE.md`를 tool 입출력 계약 중심으로 재구성
- [x] `tools/CLAUDE.md`에 객체 지향 로컬 계약 추가
- [x] 메뉴 RAG rule filter와 검색 서비스를 `menu_query_rules.py`, `menu_retrieval.py`로 분리
- [x] CS RAG 검색 서비스를 `cs_retrieval.py`로 분리
- [x] Redis retriever 캐시를 `retrieval_cache.py`로 분리하고 메뉴/CS 서비스에 선택 주입
- [x] CS 질의 정규화에서 오타 교정과 유의어 확장을 분리하고, 원문 검색을 기본값으로 전환
- [x] `tools/CLAUDE.md`의 `final_answer.py` 사용 상태 정정
- [x] 사용하지 않는 `_build_order_task`, `_build_order_resume_task`, `search_cs_results` 제거
- [x] Self-Query `cooking_method` 값에 `baked` 추가
- [x] 메뉴 검색: 부정·제외 조건, 사이드·국물 규칙어, 명시 속성 우선, 제품군 보존 완화 추가 (골든셋 dev 실패 분석)
- [x] 상황 추천 질의에서 Self-Query가 0건이면 LLM 없이 벡터 검색으로 폴백
- [x] CS 검색 결과를 상담원용 원문 대신 검수한 고객 안내 문구로 교체, Redis namespace `cs_lcel_v2`
- [x] CS 검색에 고객 원문을 함께 넣어 에이전트의 검색어 축약 문제 해결 (dev2 근거성 47 → 54/75)
- [x] CS LLM 구분 분류기 실험: 1위 정답은 올랐지만 답변 품질 차이가 없어 실험용으로만 유지

## 미완료
