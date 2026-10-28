# Benchmarks

## 폴더 목적

검색 품질, 대화 상태 일관성, 캐시 지연을 재현 가능하게 측정하고 포트폴리오용 근거를 남긴다.

## 주요 엔트리포인트

- `run_retrieval.py`: 메뉴 규칙 필터·재랭킹 경로와 벡터 검색 기준선, CS 하이브리드 경로와 FAISS 기준선을 비교한다.
- `run_followup.py`: LangGraph 후속 추천 노드의 중복 메뉴 제거를 측정한다.
- `run_cs_ablation.py`: CS retriever 가중치와 전처리 조합을 비교한다.
- `run_intent_routing.py`: 규칙 기반 LangGraph 의도 라우팅의 정확도와 LLM fallback 비율을 측정한다.
- `run_cache_latency.py`: Redis Cold/Warm Cache 검색 지연을 측정한다.
- `run_sse_latency.py`: 동기 완료 시간, SSE 첫 토큰(TTFT), 토큰이 없는 메뉴 SSE의 첫 message 도착 시간을 분리 측정한다.
- `run_sse_load.py`: warm-cache 메뉴 SSE에 대해 동시성별 성공률, p95, 처리량을 측정한다.
- `run_cost_profile.py`: LangChain callback으로 실제 LLM 사용 토큰과 고정 가격표 기준 추정 비용을 기록한다.
- `run_groundedness.py`: API 최종 답변의 사실 주장을 API 반환 검색 근거와 비교해 claim support rate를 측정한다.
- `metrics.py`: 외부 인프라 없이 단위 테스트 가능한 계산 함수다.

## 로컬 계약

- 실제 인덱스와 골든셋을 사용하며, 결과는 `results/`에 JSON으로 저장한다.
- `baseline`은 기능을 제거한 비교군이며 운영 경로가 아니다.
- 성능 결과는 실행 일자, 데이터셋 크기, 캐시 상태를 함께 기록해야 한다.

## 수정 원칙

- 평가 케이스의 정답 기준은 질의 의도 또는 원천 데이터로 설명 가능해야 한다.
- 측정하지 않은 숫자를 결과 파일이나 문서에 작성하지 않는다.
- 공유 Redis를 대상으로 할 때는 `--clear-cache` 사용 전에 전용 DB인지 확인한다.

## 검증 방법

```powershell
venv\Scripts\python.exe -m pytest benchmarks/test_metrics.py
venv\Scripts\python.exe -m benchmarks.run_retrieval --help
venv\Scripts\python.exe -m benchmarks.run_followup --help
venv\Scripts\python.exe -m benchmarks.run_cache_latency --help
venv\Scripts\python.exe -m benchmarks.run_sse_latency --help
```
