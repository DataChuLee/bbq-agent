"""CS 검색의 retriever 조합과 전처리 유무를 같은 골든셋에서 비교한다."""

from __future__ import annotations

import json
import pickle
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.retrievers import EnsembleRetriever

from benchmarks.metrics import percentile
from eval.custom_rag_metrics import evaluate_rankings


ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = ROOT / "eval" / "cs_retrieval_gold.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"
VARIANTS = {
    "faiss": {"weights": None, "normalization": "raw"},
    "bm25": {"weights": None, "normalization": "raw"},
    "hybrid_04_06": {"weights": (0.4, 0.6), "normalization": "raw"},
    "hybrid_spell_04_06": {"weights": (0.4, 0.6), "normalization": "spell"},
    "hybrid_pre_04_06": {"weights": (0.4, 0.6), "normalization": "full"},
    "hybrid_pre_02_08": {"weights": (0.2, 0.8), "normalization": "full"},
}


def _retrieve_ids(query: str, variant: str) -> tuple[list[str], float]:
    from tools.cs_query_rules import correct_cs_spelling, preprocess_cs_query

    config = VARIANTS[variant]
    normalizer = {
        "raw": lambda value: value,
        "spell": correct_cs_spelling,
        "full": preprocess_cs_query,
    }[config["normalization"]]
    clean_query = normalizer(query)

    if variant == "bm25":
        with open(ROOT / "vectorstore" / "bm25_index.pkl", "rb") as index_file:
            retriever = pickle.load(index_file)
        retriever.k = 3
    else:
        from tools.cs_retrieval import build_cs_retriever

        ensemble = build_cs_retriever()
        bm25_retriever, faiss_retriever = ensemble.retrievers
        if variant == "faiss":
            retriever = faiss_retriever
        else:
            retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, faiss_retriever],
                weights=list(config["weights"]),
            )

    started = time.perf_counter()
    docs = retriever.invoke(clean_query)
    latency_ms = (time.perf_counter() - started) * 1000
    return [str(doc.metadata.get("cs_category") or "") for doc in docs], latency_ms


def run(variants: list[str] | None = None) -> dict[str, Any]:
    cases = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    approaches: dict[str, Any] = {}
    for variant in variants or list(VARIANTS):
        predictions: dict[str, list[str]] = {}
        latencies: list[float] = []
        for case in cases:
            result_ids, latency_ms = _retrieve_ids(str(case["query"]), variant)
            predictions[str(case["id"])] = result_ids
            latencies.append(latency_ms)

        rows, summary = evaluate_rankings(cases, predictions, k_values=(1, 3))
        summary["latency_p50_ms"] = percentile(latencies, 0.5)
        summary["latency_p95_ms"] = percentile(latencies, 0.95)
        approaches[variant] = {"summary": summary, "rows": rows}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "approaches": approaches,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="CS retriever ablation 벤치마크")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--variants", nargs="+", choices=tuple(VARIANTS))
    args = parser.parse_args()

    report = run(args.variants)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_label = "-".join(args.variants) if args.variants else "all"
    output = args.output_dir / f"cs_ablation_{output_label}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    for name, result in report["approaches"].items():
        print(name, f"Hit@3={result['summary']['hit@3']:.3f}", f"MRR={result['summary']['mrr']:.3f}")


if __name__ == "__main__":
    main()
