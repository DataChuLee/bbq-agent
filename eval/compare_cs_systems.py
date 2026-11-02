"""CS 세 시스템의 결과를 같은 질문끼리 짝지어 비교한다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.compare_cs_systems --split test
    venv\\Scripts\\python.exe -m eval.compare_cs_systems --split dev2 --systems customer customer_faiss customer_classify

마지막 시스템을 나머지 각각과 비교한다.
"""

import argparse
import json
import random
from pathlib import Path

from eval.run_menu_golden import mcnemar_exact_p


RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_SYSTEMS = ("baseline", "grounded", "customer")


def cluster_bootstrap_ci(diffs_by_cluster: dict[str, list[float]], rounds: int = 10000, seed: int = 42) -> tuple[float, float]:
    """같은 CS 구분의 질문끼리는 결과가 닮아서, 질문이 아니라 구분을 복원 추출한다."""
    rng = random.Random(seed)
    clusters = list(diffs_by_cluster.values())
    means = []
    for _ in range(rounds):
        sample = [d for cluster in rng.choices(clusters, k=len(clusters)) for d in cluster]
        means.append(sum(sample) / len(sample))
    means.sort()
    return means[int(rounds * 0.025)], means[int(rounds * 0.975)]


assert cluster_bootstrap_ci({"a": [1.0, 1.0], "b": [1.0]}) == (1.0, 1.0)


def reciprocal_rank(retrieved: list[str], gold: list[str], k: int = 3) -> float:
    ranked = list(dict.fromkeys(retrieved))[:k]
    return next((1 / i for i, c in enumerate(ranked, start=1) if c in gold), 0.0)


assert reciprocal_rank(["a", "a", "b"], ["b"]) == 0.5
assert reciprocal_rank(["a"], ["b"]) == 0.0


def _metrics(row: dict) -> dict[str, float]:
    ranked = list(dict.fromkeys(row["retrieved"]))
    return {
        "fully_grounded": float(row["fully_grounded"]),
        "faithful": float(row.get("faithful", False)),
        "no_leak": float(not row["leaked_terms"]),
        "coverage": row["coverage"],
        "top1": float(bool(ranked) and ranked[0] in row["gold_categories"]),
        "hit3": float(any(c in row["gold_categories"] for c in ranked[:3])),
        "mrr": reciprocal_rank(row["retrieved"], row["gold_categories"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test", "dev2"), required=True)
    parser.add_argument("--systems", nargs="+", default=list(DEFAULT_SYSTEMS))
    args = parser.parse_args()
    systems, target = args.systems, args.systems[-1]

    rows = {
        s: {r["id"]: r for r in json.loads((RESULTS_DIR / f"cs_grounding_{args.split}_{s}.json").read_text(encoding="utf-8"))}
        for s in systems
    }
    ids = sorted(rows[target])
    if any(sorted(rows[s]) != ids for s in systems):
        raise SystemExit("시스템마다 질문 목록이 다릅니다.")

    print(f"{args.split} n={len(ids)}, CS 구분 {len({rows[target][i]['gold_categories'][0] for i in ids})}개")
    for s in systems:
        group = [rows[s][i] for i in ids]
        claims = sum(r["claim_count"] for r in group)
        unsupported = sum(r["unsupported_count"] for r in group)
        m = {key: sum(_metrics(r)[key] for r in group) for key in ("faithful", "top1", "hit3", "mrr")}
        print(
            f"{s:17} 최종 정확도 {sum(r['fully_grounded'] for r in group)}/{len(group)}"
            f" | 포괄성 {sum(r['coverage'] for r in group) / len(group):.1%}"
            f" | 노출 {sum(bool(r['leaked_terms']) for r in group)}/{len(group)}"
            f" || 충실도 {m['faithful']:.0f}/{len(group)}"
            f" | Hit@1 {m['top1']:.0f} Hit@3 {m['hit3']:.0f} MRR {m['mrr'] / len(group):.3f}"
            f" | 주장 지지율 {(claims - unsupported) / max(claims, 1):.1%}"
        )

    # 판단은 주 지표(최종 정확도)와 안전 기준으로만 한다(eval/CS_METRICS.md). 나머지 줄은 원인 설명용이다.
    for base in systems[:-1]:
        print(f"\n{base} → {target}")
        for metric in ("fully_grounded", "no_leak", "coverage", "faithful", "top1"):
            before = [_metrics(rows[base][i])[metric] for i in ids]
            after = [_metrics(rows[target][i])[metric] for i in ids]
            by_cluster: dict[str, list[float]] = {}
            for i, b, a in zip(ids, before, after):
                by_cluster.setdefault(rows[target][i]["gold_categories"][0], []).append(a - b)
            low, high = cluster_bootstrap_ci(by_cluster)
            test = f"McNemar p={mcnemar_exact_p(before, after):.4f}, " if metric != "coverage" else ""
            print(f"  {metric:15} 차이 {sum(after) / len(after) - sum(before) / len(before):+.3f}, {test}구분 단위 95% CI [{low:+.3f}, {high:+.3f}]")


if __name__ == "__main__":
    main()
