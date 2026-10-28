"""Redis를 사용하는 검색 경로의 Cold/Warm Cache 지연을 측정한다.

실행 예시:
    venv\\Scripts\\python.exe -m benchmarks.run_cache_latency --kind menu --clear-cache
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from benchmarks.metrics import percentile


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "benchmarks" / "data" / "latency_queries.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


def _load_queries(kind: str) -> list[str]:
    queries = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [str(query) for query in queries[kind]]


def _measure(search: Callable[[str], object], queries: list[str]) -> list[float]:
    durations: list[float] = []
    for query in queries:
        started = time.perf_counter()
        search(query)
        durations.append((time.perf_counter() - started) * 1000)
    return durations


def run(kind: str, iterations: int, clear_cache: bool) -> dict[str, Any]:
    if kind == "menu":
        from tools.menu_retrieval import MenuSearchService
        from tools.retrieval_cache import build_redis_cache

        cache = build_redis_cache("menu_lcel", 86400)
        service = MenuSearchService(redis_cache=cache)
        search = lambda query: service.search(query, use_cache=True)
    else:
        from tools.cs_retrieval import CsSearchService
        from tools.retrieval_cache import build_redis_cache

        cache = build_redis_cache("cs_lcel", 3600)
        service = CsSearchService(redis_cache=cache)
        search = lambda query: service.search(query)

    if cache is None:
        raise RuntimeError("Redis 캐시가 비활성화되어 있습니다. 환경 변수를 확인하세요.")
    try:
        cache.redis.ping()
    except Exception as exc:
        raise RuntimeError("Redis에 연결할 수 없습니다.") from exc

    if clear_cache:
        cache.flush()

    queries = _load_queries(kind)
    cold = _measure(search, queries)
    warm = [duration for _ in range(iterations) for duration in _measure(search, queries)]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "query_count": len(queries),
        "warm_iterations": iterations,
        "cache_hit_rate": cache.hit_rate,
        "cold_ms": {"p50": percentile(cold, 0.5), "p95": percentile(cold, 0.95)},
        "warm_ms": {"p50": percentile(warm, 0.5), "p95": percentile(warm, 0.95)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Redis 검색 캐시 지연 벤치마크")
    parser.add_argument("--kind", choices=("menu", "cs"), required=True)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--clear-cache", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations는 1 이상이어야 합니다.")

    report = run(args.kind, args.iterations, args.clear_cache)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"cache_latency_{args.kind}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    print("Cold p95(ms):", f"{report['cold_ms']['p95']:.1f}")
    print("Warm p95(ms):", f"{report['warm_ms']['p95']:.1f}")


if __name__ == "__main__":
    main()
