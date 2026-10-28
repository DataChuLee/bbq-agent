# Benchmarks

`benchmarks`는 포트폴리오에 사용할 검색 품질, 후속 추천 일관성, 캐시 지연 측정 도구를 둡니다. 결과 파일은 Git에 포함하지 않습니다.

## 사전 조건

- 메뉴 ChromaDB와 CS FAISS/BM25 인덱스가 준비되어 있어야 합니다.
- 검색 품질 평가는 `OPENAI_API_KEY`가 필요합니다.
- 캐시 평가는 Redis 실행 및 `REDIS_CACHE_ENABLED=true`가 필요합니다.
- SSE 평가는 FastAPI 서버를 별도로 실행해야 합니다.

## 검색 품질 A/B 평가

동일 골든셋에서 현재 검색 경로와 축소 기준선을 별도로 실행합니다.

```powershell
venv\Scripts\python.exe -m benchmarks.run_retrieval --mode baseline
venv\Scripts\python.exe -m benchmarks.run_retrieval --mode enhanced
```

- `baseline`: 메뉴는 메타데이터 필터와 재랭킹 없이 벡터 유사도 검색만 수행하고, CS는 FAISS 검색만 수행합니다.
- `enhanced`: 서비스의 규칙 기반 메뉴 조건 필터·재랭킹 및 CS 하이브리드 검색을 수행합니다. LLM Self-Query 단계는 변동성을 분리하기 위해 이 평가에서 제외합니다.
- 결과: `benchmarks/results/retrieval_{mode}.json`

비교할 지표는 메뉴 `Hit@3`, `ConstraintPass@3`, CS `Hit@3`, `MRR`입니다. 두 실행은 같은 인덱스와 골든셋, 같은 실행 환경에서 연속 실행합니다.

## 후속 추천 상태 평가

```powershell
venv\Scripts\python.exe -m benchmarks.run_followup
```

초기 추천에서 이미 노출한 메뉴와 후속 추천 응답의 메뉴를 비교합니다. `candidate_duplicate_card_rate`는 상태 필터 적용 전 후보군이고, `state_filtered_duplicate_card_rate`는 LangGraph 후속 추천 노드의 최종 응답입니다.

## CS 검색 가중치 실험

```powershell
venv\Scripts\python.exe -m benchmarks.run_cs_ablation
venv\Scripts\python.exe -m benchmarks.run_cs_ablation --variants bm25
```

FAISS, BM25, 하이브리드 가중치 2종과 전처리 유무를 같은 CS 골든셋에서 비교합니다. 가장 높은 Hit@3만 선택하지 말고 MRR와 지연 시간도 함께 확인합니다.

## 의도 라우팅 평가

```powershell
venv\Scripts\python.exe -m benchmarks.run_intent_routing
```

메뉴·후속 추천·CS·알 수 없는 요청 각 6건으로 규칙 기반 직접 라우팅 비율, LLM fallback 비율, 직접 라우팅 정확도를 계산합니다.

## Redis Cold/Warm Cache 지연 평가

`--clear-cache`는 `rag:menu_lcel:*` 또는 `rag:cs_lcel:*` 키를 삭제하고 새로 측정합니다. 공유 Redis에서는 전용 DB를 사용하세요.

```powershell
venv\Scripts\python.exe -m benchmarks.run_cache_latency --kind menu --clear-cache
venv\Scripts\python.exe -m benchmarks.run_cache_latency --kind cs --clear-cache
```

4개의 메뉴 질의와 3개의 CS 질의를 고정해 Cold/Warm p50, p95와 `cache_hit_rate`를 비교합니다. 캐시 성능은 네트워크·OpenAI 응답 시간에 영향을 받으므로 최소 3회 실행 후 중앙값을 포트폴리오에 기록합니다.

## SSE 체감 지연 평가

CS 질의는 토큰 스트리밍 경로를 사용하므로, 동기 응답 완료 시간과 스트리밍 첫 토큰 도착 시간을 분리해 측정합니다.

```powershell
uvicorn main:app --reload
venv\Scripts\python.exe -m benchmarks.run_sse_latency --base-url http://localhost:8000
```

`stream_ttft_p50_ms`는 스트리밍의 첫 토큰 도착 시간이며, `sync_complete_p50_ms`와의 차이는 사용자가 최종 답변 전에 확인할 수 있는 체감 대기 시간입니다. SSE가 모델 추론 자체를 빠르게 했다고 해석하지 않습니다.

`stream_error_count`가 0이 아닌 실행은 TTFT 성과로 사용하지 않습니다. 먼저 오류 원인을 해결한 뒤 재실행합니다.

## 포트폴리오 기록 원칙

- 결과 파일에 저장된 실제 수치만 이력서에 사용합니다.
- 실행 날짜, Git 커밋, 인덱스 재빌드 여부, 케이스 수를 함께 기록합니다.
- 성능 수치는 Cold Cache와 Warm Cache를 분리해 표기합니다.
