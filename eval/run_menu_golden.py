"""메뉴 골든셋으로 기준선(순수 벡터 검색)과 현재 검색 서비스를 비교한다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.run_menu_golden --split dev
"""

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

from eval.custom_rag_metrics import hit_at_k, ndcg_at_k


EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
# 첫 추천 화면이 메뉴 카드 5장이라 사용자가 보는 범위만 채점한다.
K = 5


def mcnemar_exact_p(base_hits: list[float], new_hits: list[float]) -> float:
    """같은 질의에서 한쪽만 맞힌 경우만 세는 정확 McNemar 검정(양측)이다."""
    b = sum(x > y for x, y in zip(base_hits, new_hits))
    c = sum(y > x for x, y in zip(base_hits, new_hits))
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def paired_bootstrap_ci(diffs: list[float], rounds: int = 10000, seed: int = 42) -> tuple[float, float]:
    """질의를 복원 추출해 평균 차이의 95% 신뢰구간을 구한다."""
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(rounds))
    return means[int(rounds * 0.025)], means[int(rounds * 0.975)]


assert mcnemar_exact_p([1, 1, 0], [1, 1, 0]) == 1.0
assert mcnemar_exact_p([0] * 8, [1] * 8) < 0.01


def _systems():
    from tools.menu_retrieval import MenuSearchService, build_self_query_retriever

    vectorstore = build_self_query_retriever().vectorstore
    service = MenuSearchService(redis_cache=None)
    return {
        "baseline": lambda q: [d.metadata["name"] for d in vectorstore.similarity_search(q, k=K)],
        "current": lambda q: [r["name"] for r in service.search(q, k=K, use_cache=False)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    args = parser.parse_args()
    output_path = RESULTS_DIR / f"menu_golden_{args.split}.json"
    # test는 최종 비교에서 한 번만 돌린다. 다시 돌리면 test에 맞춘 튜닝이 된다.
    if args.split == "test" and output_path.exists():
        raise SystemExit(f"test 결과가 이미 있습니다: {output_path}")

    load_dotenv()
    cases = json.loads((EVAL_DIR / "menu_golden_queries.json").read_text(encoding="utf-8"))
    labels = json.loads((EVAL_DIR / "menu_golden_labels.json").read_text(encoding="utf-8"))
    cases = [c for c in cases if c["split"] == args.split]

    rows = []
    for name, search in _systems().items():
        for case in cases:
            grades = labels[case["id"]]
            ranked = search(case["query"])
            rows.append({
                "system": name,
                "id": case["id"],
                "case_type": case["case_type"],
                "query": case["query"],
                "retrieved": ranked,
                # 조건을 모두 만족하는 2점 메뉴가 화면에 떴는지만 성공으로 본다.
                "hit@5": hit_at_k(ranked, [m for m, g in grades.items() if g == 2], K),
                "ndcg@5": ndcg_at_k(ranked, grades, K),
            })

    RESULTS_DIR.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    groups = defaultdict(list)
    for row in rows:
        groups[(row["system"], "전체")].append(row)
        groups[(row["system"], row["case_type"])].append(row)
    print(f"{args.split} n={len(cases)} → {output_path}")
    for (system, case_type), group in sorted(groups.items(), key=lambda x: (x[0][1] != "전체", x[0][1], x[0][0])):
        hit = sum(r["hit@5"] for r in group) / len(group)
        ndcg = sum(r["ndcg@5"] for r in group) / len(group)
        print(f"{case_type:14} {system:9} n={len(group):2}  Hit@5 {hit:.3f}  nDCG@5 {ndcg:.3f}")

    # 주 비교(기준선 vs 현재) 하나만 검정한다. 유형별로 여러 번 검정하면 우연히 유의한 결과가 나온다.
    by_system = {s: [r for r in rows if r["system"] == s] for s in ("baseline", "current")}
    base, curr = by_system["baseline"], by_system["current"]
    p = mcnemar_exact_p([r["hit@5"] for r in base], [r["hit@5"] for r in curr])
    low, high = paired_bootstrap_ci([c["ndcg@5"] - b["ndcg@5"] for b, c in zip(base, curr)])
    print(f"Hit@5 McNemar 정확 검정 p={p:.3f}")
    print(f"nDCG@5 차이(현재-기준선) 95% CI [{low:+.3f}, {high:+.3f}]")


if __name__ == "__main__":
    main()
