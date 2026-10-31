"""CS 세 시스템의 결과를 같은 질문끼리 짝지어 비교한다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.compare_cs_systems --split test
"""

import argparse
import json
import random
from pathlib import Path

from eval.run_menu_golden import mcnemar_exact_p


RESULTS_DIR = Path(__file__).parent / "results"
SYSTEMS = ("baseline", "grounded", "customer")


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


def _metrics(row: dict) -> dict[str, float]:
    return {
        "fully_grounded": float(row["fully_grounded"]),
        "no_leak": float(not row["leaked_terms"]),
        "coverage": row["coverage"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    args = parser.parse_args()

    rows = {
        s: {r["id"]: r for r in json.loads((RESULTS_DIR / f"cs_grounding_{args.split}_{s}.json").read_text(encoding="utf-8"))}
        for s in SYSTEMS
    }
    ids = sorted(rows["customer"])
    if any(sorted(rows[s]) != ids for s in SYSTEMS):
        raise SystemExit("시스템마다 질문 목록이 다릅니다.")

    print(f"{args.split} n={len(ids)}, CS 구분 {len({rows['customer'][i]['gold_categories'][0] for i in ids})}개")
    for s in SYSTEMS:
        group = [rows[s][i] for i in ids]
        claims = sum(r["claim_count"] for r in group)
        unsupported = sum(r["unsupported_count"] for r in group)
        print(
            f"{s:9} 근거 없는 주장 없는 답변 {sum(r['fully_grounded'] for r in group)}/{len(group)}"
            f" | 주장 지지율 {(claims - unsupported) / max(claims, 1):.1%}"
            f" | 포괄성 {sum(r['coverage'] for r in group) / len(group):.1%}"
            f" | 노출 {sum(bool(r['leaked_terms']) for r in group)}/{len(group)}"
            f" | 검색 적중 {sum(r['retrieval_hit'] for r in group)}/{len(group)}"
        )

    # 미리 정한 비교 두 개만 검정한다. 비교를 늘릴수록 우연히 유의한 결과가 나온다.
    for base in ("baseline", "grounded"):
        print(f"\n{base} → customer")
        for metric in ("fully_grounded", "no_leak", "coverage"):
            before = [_metrics(rows[base][i])[metric] for i in ids]
            after = [_metrics(rows["customer"][i])[metric] for i in ids]
            by_cluster: dict[str, list[float]] = {}
            for i, b, a in zip(ids, before, after):
                by_cluster.setdefault(rows["customer"][i]["gold_categories"][0], []).append(a - b)
            low, high = cluster_bootstrap_ci(by_cluster)
            test = f"McNemar p={mcnemar_exact_p(before, after):.4f}, " if metric != "coverage" else ""
            print(f"  {metric:15} 차이 {sum(after) / len(after) - sum(before) / len(before):+.3f}, {test}구분 단위 95% CI [{low:+.3f}, {high:+.3f}]")


if __name__ == "__main__":
    main()
