# graph TODO

## 완료
- [x] `graph/CLAUDE.md`를 오케스트레이션 계약 중심으로 재구성
- [x] `graph/CLAUDE.md`에 객체 지향 로컬 계약 추가
- [x] intent 휴리스틱과 LLM prompt 생성을 `graph/intent.py`로 분리
- [x] 새 조건이 포함된 메뉴 후속 요청의 재검색과 상태 유지 검증
- [x] 사용하지 않는 intent wrapper(`_looks_like_order_request`, `_looks_like_menu_followup`) 제거
- [x] CS 프롬프트를 고객 문구 전달용으로 교체 (dev: 내부 정보 노출 17/25 → 0/25, 포괄성 63% → 78%)
- [x] 의도 라우팅 수정: test(n=150) CS 재현율 68% → 99%, 전체 정확도 114 → 147/150 (메뉴 규칙 축소, LLM 프롬프트에 CS 범위 명시)
- [ ] 규칙 경로 축소로 LLM 분류 호출이 늘어난 만큼의 지연·비용 재측정
- [ ] 주문 마커 "장바구니"가 앱 불편 문의를 메뉴로 보내는 문제 (주문 흐름은 이번 범위 밖)

## 미완료
