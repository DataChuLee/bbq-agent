# tools TODO

## 완료
- [x] `tools/CLAUDE.md`를 tool 입출력 계약 중심으로 재구성
- [x] `tools/CLAUDE.md`에 객체 지향 로컬 계약 추가
- [x] 메뉴 RAG rule filter와 검색 서비스를 `menu_query_rules.py`, `menu_retrieval.py`로 분리
- [x] CS RAG 검색 서비스를 `cs_retrieval.py`로 분리
- [x] Redis retriever 캐시를 `retrieval_cache.py`로 분리하고 메뉴/CS 서비스에 선택 주입
- [x] CS 질의 정규화에서 오타 교정과 유의어 확장을 분리하고, 원문 검색을 기본값으로 전환
- [x] `tools/CLAUDE.md`의 `final_answer.py` 사용 상태 정정

## 미완료
