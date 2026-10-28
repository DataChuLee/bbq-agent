"""동기 응답과 SSE 스트리밍의 사용자 체감 지연을 비교한다.

FastAPI 서버를 실행한 뒤 사용한다.

실행 예시:
    venv\\Scripts\\python.exe -m benchmarks.run_sse_latency --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from benchmarks.metrics import percentile


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "benchmarks" / "data" / "sse_queries.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


def _post_json(url: str, payload: dict[str, Any]):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urlopen(request, timeout=180)


def _create_session(base_url: str) -> str:
    request = Request(f"{base_url}/sessions", data=b"", method="POST")
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload["data"]["id"])


def _response_payload(query: str) -> dict[str, Any]:
    return {"input": {"type": "text", "content": query}}


def _measure_sync(base_url: str, query: str) -> float:
    session_id = _create_session(base_url)
    started = time.perf_counter()
    with _post_json(
        f"{base_url}/sessions/{session_id}/responses",
        _response_payload(query),
    ) as response:
        response.read()
    return (time.perf_counter() - started) * 1000


def _measure_stream(
    base_url: str, query: str
) -> tuple[float | None, float | None, float, str | None]:
    session_id = _create_session(base_url)
    started = time.perf_counter()
    first_token_ms: float | None = None
    first_content_ms: float | None = None
    error: str | None = None

    with _post_json(
        f"{base_url}/sessions/{session_id}/responses/stream",
        _response_payload(query),
    ) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            event = json.loads(line.removeprefix("data: "))
            if event.get("event") == "token" and first_token_ms is None:
                first_token_ms = (time.perf_counter() - started) * 1000
            if event.get("event") in {"token", "message"} and first_content_ms is None:
                first_content_ms = (time.perf_counter() - started) * 1000
            if event.get("event") == "error":
                error = str(event.get("message") or "Unknown SSE error")
                break
            if event.get("event") == "done":
                break

    return (
        first_token_ms,
        first_content_ms,
        (time.perf_counter() - started) * 1000,
        error,
    )


def _build_menu_cache_resetter() -> Callable[[], None]:
    from tools.retrieval_cache import build_redis_cache

    cache = build_redis_cache("menu_lcel", 86400)
    if cache is None:
        raise RuntimeError("메뉴 Redis 캐시가 비활성화되어 있습니다.")
    try:
        cache.redis.ping()
    except Exception as exc:
        raise RuntimeError("메뉴 Redis 캐시에 연결할 수 없습니다.") from exc
    return cache.flush


def run(
    base_url: str,
    data_path: Path = DATA_PATH,
    reset_menu_cache: bool = False,
    iterations: int = 1,
) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations must be at least 1")

    queries = json.loads(data_path.read_text(encoding="utf-8"))
    reset_cache = _build_menu_cache_resetter() if reset_menu_cache else None
    rows: list[dict[str, Any]] = []
    for iteration in range(1, iterations + 1):
        for case in queries:
            row = _run_case(base_url, case, reset_cache)
            row["iteration"] = iteration
            rows.append(row)

    successful_rows = [
        row
        for row in rows
        if row["sync_error"] is None and row["stream_error"] is None
    ]
    ttft_values = [
        row["stream_ttft_ms"]
        for row in successful_rows
        if row["stream_ttft_ms"] is not None
    ]
    first_content_values = [
        row["stream_first_content_ms"]
        for row in successful_rows
        if row["stream_first_content_ms"] is not None
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "iterations": iterations,
        "summary": {
            "case_count": len(rows),
            "sync_error_count": sum(row["sync_error"] is not None for row in rows),
            "stream_success_count": len(successful_rows),
            "stream_error_count": len(rows) - len(successful_rows),
            "sync_complete_p50_ms": percentile(
                [row["sync_complete_ms"] for row in successful_rows], 0.5
            ),
            "sync_complete_p95_ms": percentile(
                [row["sync_complete_ms"] for row in successful_rows], 0.95
            ),
            "stream_ttft_p50_ms": percentile(ttft_values, 0.5),
            "stream_ttft_p95_ms": percentile(ttft_values, 0.95),
            "stream_first_content_p50_ms": percentile(first_content_values, 0.5),
            "stream_first_content_p95_ms": percentile(first_content_values, 0.95),
            "stream_complete_p50_ms": percentile(
                [row["stream_complete_ms"] for row in successful_rows], 0.5
            ),
            "stream_complete_p95_ms": percentile(
                [row["stream_complete_ms"] for row in successful_rows], 0.95
            ),
        },
        "rows": rows,
    }


def _run_case(
    base_url: str,
    case: dict[str, Any],
    reset_cache: Callable[[], None] | None,
) -> dict[str, Any]:
    query = str(case["query"])
    sync_complete_ms: float | None = None
    sync_error: str | None = None
    try:
        if reset_cache is not None:
            reset_cache()
        sync_complete_ms = _measure_sync(base_url, query)
    except Exception as exc:
        sync_error = str(exc)

    ttft_ms: float | None = None
    first_content_ms: float | None = None
    stream_complete_ms: float | None = None
    stream_error: str | None = None
    try:
        if reset_cache is not None:
            reset_cache()
        (
            ttft_ms,
            first_content_ms,
            stream_complete_ms,
            stream_error,
        ) = _measure_stream(base_url, query)
    except Exception as exc:
        stream_error = str(exc)
    return {
        "id": case["id"],
        "query": query,
        "sync_complete_ms": sync_complete_ms,
        "sync_error": sync_error,
        "stream_ttft_ms": ttft_ms,
        "stream_first_content_ms": first_content_ms,
        "stream_complete_ms": stream_complete_ms,
        "stream_error": stream_error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SSE 체감 지연 벤치마크")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--queries-file", type=Path, default=DATA_PATH)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--reset-menu-cache",
        action="store_true",
        help="각 동기·스트리밍 요청 전에 메뉴 검색 캐시만 비웁니다.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = run(
        args.base_url.rstrip("/"),
        args.queries_file,
        args.reset_menu_cache,
        args.iterations,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"sse_latency_{args.queries_file.stem}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    print("SSE TTFT p50(ms):", f"{report['summary']['stream_ttft_p50_ms']:.1f}")
    print(
        "SSE first content p50(ms):",
        f"{report['summary']['stream_first_content_p50_ms']:.1f}",
    )


if __name__ == "__main__":
    main()
