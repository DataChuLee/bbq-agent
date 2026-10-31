# graph TODO

## 완료
- [x] `graph/CLAUDE.md`를 오케스트레이션 계약 중심으로 재구성
- [x] `graph/CLAUDE.md`에 객체 지향 로컬 계약 추가
- [x] intent 휴리스틱과 LLM prompt 생성을 `graph/intent.py`로 분리
- [x] 새 조건이 포함된 메뉴 후속 요청의 재검색과 상태 유지 검증
- [x] 사용하지 않는 intent wrapper(`_looks_like_order_request`, `_looks_like_menu_followup`) 제거
- [x] CS 프롬프트를 고객 문구 전달용으로 교체 (dev: 내부 정보 노출 17/25 → 0/25, 포괄성 63% → 78%)

## 미완료
