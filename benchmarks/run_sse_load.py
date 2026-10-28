"""동시 SSE 요청에서 성공률, 첫 콘텐츠 지연, 처리량을 측정한다."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.metrics import percentile
from benchmarks.run_sse_latency import _measure_stream


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "benchmarks" / "data" / "sse_menu_queries.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


def _measure_one(base_url: str, case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        ttft_ms, first_content_ms, complete_ms, error = _measure_stream(
            base_url,
            str(case["query"]),
        )
    except Exception as exc:
        ttft_ms = None
        first_content_ms = None
        complete_ms = None
        error = str(exc)
    return {
        "id": case["id"],
        "ttft_ms": ttft_ms,
        "first_content_ms": first_content_ms,
        "complete_ms": complete_ms,
        "error": error,
        "client_elapsed_ms": (time.perf_counter() - started) * 1000,
    }


def _summary(rows: list[dict[str, Any]], batch_elapsed_ms: float) -> dict[str, float | int]:
    successful = [row for row in rows if row["error"] is None]
    first_content = [
        row["first_content_ms"]
        for row in successful
        if row["first_content_ms"] is not None
    ]
    complete = [row["complete_ms"] for row in successful if row["complete_ms"] is not None]
    return {
        "request_count": len(rows),
        "success_count": len(successful),
        "error_count": len(rows) - len(successful),
        "success_rate": len(successful) / len(rows) if rows else 0.0,
        "first_content_p50_ms": percentile(first_content, 0.5),
        "first_content_p95_ms": percentile(first_content, 0.95),
        "complete_p50_ms": percentile(complete, 0.5),
        "complete_p95_ms": percentile(complete, 0.95),
        "batch_elapsed_ms": batch_elapsed_ms,
        "throughput_rps": len(successful) / (batch_elapsed_ms / 1000)
        if batch_elapsed_ms
        else 0.0,
    }


def run(
    base_url: str,
    cases: list[dict[str, Any]],
    concurrency_levels: list[int],
    rounds: int,
) -> dict[str, Any]:
    if rounds <= 0 or any(level <= 0 for level in concurrency_levels):
        raise ValueError("rounds and concurrency must be at least 1")

    profiles: list[dict[str, Any]] = []
    for concurrency in concurrency_levels:
        requests = [
            cases[index % len(cases)]
            for index in range(concurrency * rounds)
        ]
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(_measure_one, base_url, case) for case in requests
            ]
            rows = [future.result() for future in as_completed(futures)]
        batch_elapsed_ms = (time.perf_counter() - started) * 1000
        profiles.append(
            {
                "concurrency": concurrency,
                "summary": _summary(rows, batch_elapsed_ms),
                "rows": rows,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "cache_state": "warm",
        "rounds_per_worker": rounds,
        "profiles": profiles,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SSE 동시 요청 부하 측정")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--queries-file", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    cases = json.loads(args.queries_file.read_text(encoding="utf-8"))
    if not cases:
        parser.error("queries file must contain at least one case")
    report = run(args.base_url.rstrip("/"), cases, args.concurrency, args.rounds)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "sse_load.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    for profile in report["profiles"]:
        summary = profile["summary"]
        print(
            f"c={profile['concurrency']}: success={summary['success_rate']:.0%}, "
            f"p95={summary['first_content_p95_ms']:.1f}ms, "
            f"rps={summary['throughput_rps']:.2f}"
        )


if __name__ == "__main__":
    main()
