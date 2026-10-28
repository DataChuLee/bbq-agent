"""메뉴와 CS 검색의 현재 구현 및 축소 기준선을 비교한다.

실행 예시:
    venv\\Scripts\\python.exe -m benchmarks.run_retrieval --mode enhanced
    venv\\Scripts\\python.exe -m benchmarks.run_retrieval --mode baseline
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.metrics import evaluate_menu_constraints
from eval.custom_rag_metrics import evaluate_rankings


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
DATA_DIR = ROOT / "benchmarks" / "data"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


def _load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _menu_predictions(cases: list[dict[str, Any]], mode: str) -> dict[str, list[dict]]:
    from tools.menu_query_rules import extract_rule_based_filters
    from tools.menu_retrieval import (
        MenuSearchService,
        _apply_post_retrieval_filters,
        build_self_query_retriever,
        infer_requested_family,
    )
    from tools.recommendation_criteria import (
        detect_recommendation_criteria,
        rerank_menu_items,
    )

    service = MenuSearchService(redis_cache=None)
    predictions: dict[str, list[dict]] = {}
    for case in cases:
        query = str(case["query"])
        retriever = build_self_query_retriever()
        if mode == "baseline":
            docs = retriever.vectorstore.similarity_search(query, k=5)
            predictions[str(case["id"])] = service._documents_to_menu_items(docs)
        else:
            strict_filter = extract_rule_based_filters(query)
            if strict_filter:
                docs = service._rule_filter_search(query, 5, strict_filter)
            else:
                docs = retriever.vectorstore.similarity_search(query, k=5)
            criteria = detect_recommendation_criteria(query)
            items = service._documents_to_menu_items(docs)
            items = _apply_post_retrieval_filters(
                query,
                items,
                requested_family=infer_requested_family(query),
                has_criteria=bool(criteria),
            )
            predictions[str(case["id"])] = rerank_menu_items(query, items)
    return predictions


def _cs_predictions(cases: list[dict[str, Any]], mode: str) -> dict[str, list[str]]:
    from tools.cs_retrieval import CsSearchService, build_cs_retriever

    predictions: dict[str, list[str]] = {}
    if mode == "enhanced":
        service = CsSearchService(redis_cache=None)
        for case in cases:
            results = service.search(str(case["query"]))
            predictions[str(case["id"])] = [item["cs_category"] for item in results]
        return predictions

    ensemble = build_cs_retriever()
    faiss_retriever = ensemble.retrievers[1]
    for case in cases:
        docs = faiss_retriever.invoke(str(case["query"]))
        predictions[str(case["id"])] = [
            str(doc.metadata.get("cs_category") or "") for doc in docs
        ]
    return predictions


def run(mode: str) -> dict[str, Any]:
    menu_gold = _load_json(EVAL_DIR / "menu_retrieval_gold.json")
    cs_gold = _load_json(EVAL_DIR / "cs_retrieval_gold.json")
    constraint_cases = _load_json(DATA_DIR / "menu_constraint_cases.json")

    menu_results = _menu_predictions(menu_gold, mode)
    menu_rows, menu_summary = evaluate_rankings(menu_gold, {
        case_id: [item.get("name", "") for item in items]
        for case_id, items in menu_results.items()
    }, k_values=(1, 3, 5))

    constraint_predictions = _menu_predictions(constraint_cases, mode)
    constraint_rows, constraint_summary = evaluate_menu_constraints(
        constraint_cases,
        constraint_predictions,
        k=3,
    )

    cs_results = _cs_predictions(cs_gold, mode)
    cs_rows, cs_summary = evaluate_rankings(
        cs_gold,
        cs_results,
        k_values=(1, 3),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "menu_ranking": {"summary": menu_summary, "rows": menu_rows},
        "menu_constraints": {"summary": constraint_summary, "rows": constraint_rows},
        "cs_ranking": {"summary": cs_summary, "rows": cs_rows},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BBQ 검색 품질 벤치마크")
    parser.add_argument("--mode", choices=("baseline", "enhanced"), required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = run(args.mode)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"retrieval_{args.mode}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"저장 완료: {output}")
    print("메뉴 Hit@3:", f"{report['menu_ranking']['summary']['hit@3']:.3f}")
    print("메뉴 ConstraintPass@3:", f"{report['menu_constraints']['summary']['constraint_pass@k']:.3f}")
    print("CS Hit@3:", f"{report['cs_ranking']['summary']['hit@3']:.3f}")


if __name__ == "__main__":
    main()
