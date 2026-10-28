"""후속 메뉴 추천에서 상태 기반 중복 제거가 동작하는지 측정한다.

실행 예시:
    venv\\Scripts\\python.exe -m benchmarks.run_followup
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from benchmarks.metrics import duplicate_card_rate


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "benchmarks" / "data" / "followup_cases.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


async def run_case(case: dict[str, Any]) -> dict[str, Any]:
    from graph.graph import menu_followup_node
    from tools.search_menu import FOLLOWUP_TOP_K, search_menu_results

    initial_query = str(case["initial_query"])
    candidates = await asyncio.to_thread(
        search_menu_results,
        initial_query,
        {},
        k=FOLLOWUP_TOP_K,
        use_cache=False,
    )
    shown_items = candidates[: int(case.get("initial_display_count", 3))]
    shown_names = [str(item.get("name") or "") for item in shown_items]

    state = {
        "messages": [HumanMessage(content=str(case["followup_query"]))],
        "intent": "menu_followup",
        "response": {},
        "menu_results": {initial_query: shown_items},
        "cs_results": {},
        "selected_order": None,
        "last_menu_query": initial_query,
        "last_cs_query": None,
        "shown_menu_names": shown_names,
    }
    result = await menu_followup_node(state)
    response = result.get("response") or {}
    returned_items = response.get("items", []) if response.get("type") == "menu_cards" else []

    return {
        "id": case["id"],
        "initial_query": initial_query,
        "followup_query": case["followup_query"],
        "shown_names": shown_names,
        "candidate_duplicate_rate": duplicate_card_rate(shown_names, candidates),
        "state_filtered_duplicate_rate": duplicate_card_rate(shown_names, returned_items),
        "returned_names": [str(item.get("name") or "") for item in returned_items],
        "response_type": response.get("type", "text"),
    }


async def run() -> dict[str, Any]:
    cases = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows = [await run_case(case) for case in cases]
    count = len(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "case_count": count,
            "candidate_duplicate_card_rate": (
                sum(row["candidate_duplicate_rate"] for row in rows) / count
                if count
                else 0.0
            ),
            "state_filtered_duplicate_card_rate": (
                sum(row["state_filtered_duplicate_rate"] for row in rows) / count
                if count
                else 0.0
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="후속 메뉴 추천 상태 벤치마크")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = asyncio.run(run())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "followup.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    print(
        "후속 추천 중복률:",
        f"{report['summary']['candidate_duplicate_card_rate']:.3f} → "
        f"{report['summary']['state_filtered_duplicate_card_rate']:.3f}",
    )


if __name__ == "__main__":
    main()
