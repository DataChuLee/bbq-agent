# tools/ — 작업 내역

## 파일 목록

| 파일 | Agent | 역할 |
|---|---|---|
| `search_menu.py` | Menu Agent | SelfQueryRetriever + ChromaDB 기반 메뉴 검색 |
| `search_cs.py` | CS Agent | EnsembleRetriever (BM25 40% + FAISS 60%) 기반 CS 검색 |
| `ask_clarification.py` | Menu Agent | 모호한 쿼리 → 사용자 재질문 |
| `final_answer.py` | Menu / CS Agent | 최종 응답 포맷팅 (메뉴 카드 / CS 자연어) |

---

## Tool 상세

### search_menu
```python
search_menu(query: str) -> str
```
- SelfQueryRetriever가 `query`에서 `price`, `category`, `allergy` 필터 자동 추출
- ChromaDB top-5 검색 → `{"results": [...]}` JSON 반환
- `_get_retriever()` `@lru_cache` — 앱 생명주기 동안 1회만 초기화

### search_cs
```python
search_cs(query: str) -> str
```
- BM25(40%) + FAISS(60%) EnsembleRetriever, top-3
- `{"results": [{"content", "cs_category", "claim_category"}, ...]}` 반환
- `_get_retriever()` `@lru_cache` — 1회만 초기화

### ask_clarification
```python
ask_clarification(question: str) -> str
```
- API 호출 없음 — 질문 문자열을 JSON으로 래핑만 함
- `{"type": "clarification", "question": "..."}` 반환
- graph에서 이 타입을 감지해 사용자 응답 대기 처리

### final_answer_menu
```python
final_answer_menu(items: List[dict]) -> str
```
- API 호출 없음 — 메뉴 항목 리스트를 카드 JSON으로 포맷팅
- `{"type": "menu_cards", "items": [...]}` 반환

### final_answer_cs
```python
final_answer_cs(query: str, retrieved_docs: List[str]) -> str
```
- RAG: `retrieved_docs` + `query` → GPT-4o-mini → 자연어 답변
- `{"type": "text", "message": "..."}` 반환
- 참고 자료에 없는 내용은 생성하지 않도록 프롬프트에 명시

---

## ReAct 루프에서의 Tool 호출 흐름

```
[Menu Agent]
Thought → search_menu(query) → Observe
       → ask_clarification(question) → 사용자 답변 대기
       → final_answer_menu(items) → 종료

[CS Agent]
Thought → search_cs(query) → Observe
       → final_answer_cs(query, retrieved_docs) → 종료
```
