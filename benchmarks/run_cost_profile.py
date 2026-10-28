"""LangChain 콜백으로 그래프 실행의 실제 모델 토큰 사용량을 기록한다."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

os.environ["LANGSMITH_TRACING"] = "false"

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "benchmarks" / "data" / "cost_profile_queries.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"
INPUT_PRICE_PER_MILLION_USD = 0.15
OUTPUT_PRICE_PER_MILLION_USD = 0.60
PRICING_SOURCE = "https://developers.openai.com/api/docs/models/gpt-4o-mini"


class UsageCollector(BaseCallbackHandler):
    """LLM 종료 이벤트에서 provider가 반환한 토큰 사용량만 수집한다."""

    def __init__(self) -> None:
        self.calls: list[dict[str, int]] = []

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        **_: Any,
    ) -> None:
        usage = _usage_from_response(response)
        if usage is not None:
            self.calls.append(usage)


def _usage_from_response(response: Any) -> dict[str, int] | None:
    llm_output = getattr(response, "llm_output", None) or {}
    token_usage = llm_output.get("token_usage") or {}
    if token_usage:
        return {
            "input_tokens": int(token_usage.get("prompt_tokens") or 0),
            "output_tokens": int(token_usage.get("completion_tokens") or 0),
            "total_tokens": int(token_usage.get("total_tokens") or 0),
        }

    for generation_group in getattr(response, "generations", []):
        for generation in generation_group:
            usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
            if usage:
                return {
                    "input_tokens": int(usage.get("input_tokens") or 0),
                    "output_tokens": int(usage.get("output_tokens") or 0),
                    "total_tokens": int(usage.get("total_tokens") or 0),
                }
    return None


def _estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * INPUT_PRICE_PER_MILLION_USD
        + output_tokens * OUTPUT_PRICE_PER_MILLION_USD
    ) / 1_000_000


async def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    from graph.graph import graph

    collector = UsageCollector()
    result = await graph.ainvoke(
        {
            "session_id": f"benchmark-{case['id']}",
            "messages": [HumanMessage(content=str(case["query"]))],
            "intent": None,
            "response": {},
            "menu_results": {},
            "cs_results": {},
            "selected_order": None,
            "last_menu_query": None,
            "last_cs_query": None,
            "shown_menu_names": [],
        },
        config={"callbacks": [collector]},
    )
    input_tokens = sum(call["input_tokens"] for call in collector.calls)
    output_tokens = sum(call["output_tokens"] for call in collector.calls)
    return {
        "id": case["id"],
        "query": case["query"],
        "intent": result.get("intent") or "unknown",
        "llm_call_count": len(collector.calls),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": _estimate_cost_usd(input_tokens, output_tokens),
        "usage_available": bool(collector.calls),
    }


async def run(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        try:
            rows.append(await _run_case(case))
        except Exception as exc:
            rows.append({"id": case["id"], "query": case["query"], "error": str(exc)})

    successful = [row for row in rows if "error" not in row]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "gpt-4o-mini",
        "pricing": {
            "input_usd_per_million_tokens": INPUT_PRICE_PER_MILLION_USD,
            "output_usd_per_million_tokens": OUTPUT_PRICE_PER_MILLION_USD,
            "source": PRICING_SOURCE,
        },
        "summary": {
            "case_count": len(rows),
            "success_count": len(successful),
            "error_count": len(rows) - len(successful),
            "llm_call_count": sum(row["llm_call_count"] for row in successful),
            "input_tokens": sum(row["input_tokens"] for row in successful),
            "output_tokens": sum(row["output_tokens"] for row in successful),
            "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in successful),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph LLM 사용량·비용 프로파일")
    parser.add_argument("--queries-file", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    cases = json.loads(args.queries_file.read_text(encoding="utf-8"))
    report = asyncio.run(run(cases))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "cost_profile.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    print("LLM call count:", report["summary"]["llm_call_count"])
    print("Estimated cost (USD):", f"{report['summary']['estimated_cost_usd']:.8f}")


if __name__ == "__main__":
    main()
