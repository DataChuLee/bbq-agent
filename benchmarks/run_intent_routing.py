"""규칙 우선 의도 분기의 커버리지와 정확도를 측정한다."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "benchmarks" / "data" / "intent_cases.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


def run() -> dict[str, Any]:
    from graph.intent import heuristic_classify

    cases: list[dict[str, Any]] = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    direct_rows: list[dict[str, Any]] = []
    for case in cases:
        predicted = heuristic_classify(
            str(case["query"]),
            last_menu_query=case.get("last_menu_query"),
        )
        row = {
            "id": case["id"],
            "expected_intent": case["expected_intent"],
            "predicted_intent": predicted,
            "used_llm_fallback": predicted is None,
            "correct": predicted == case["expected_intent"],
        }
        rows.append(row)
        if predicted is not None:
            direct_rows.append(row)

    total = len(rows)
    direct_total = len(direct_rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "case_count": total,
            "direct_route_rate": direct_total / total if total else 0.0,
            "llm_fallback_rate": (total - direct_total) / total if total else 0.0,
            "direct_route_accuracy": (
                sum(row["correct"] for row in direct_rows) / direct_total
                if direct_total
                else 0.0
            ),
        },
        "rows": rows,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="의도 라우팅 벤치마크")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = run()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "intent_routing.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    print("규칙 직접 라우팅 비율:", f"{report['summary']['direct_route_rate']:.3f}")
    print("규칙 직접 라우팅 정확도:", f"{report['summary']['direct_route_accuracy']:.3f}")


if __name__ == "__main__":
    main()
