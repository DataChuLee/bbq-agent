"""골든셋 질문으로 의도 라우팅(규칙 + LLM)을 평가한다.

CS 답변 실험은 CS 에이전트를 직접 불러서 쟀다. 실제 사용자는 그 전에 의도 분류를 거치므로 이 단계를 따로 잰다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.run_intent_golden --split dev

split:
    dev   CS dev·dev2 100개, 메뉴 dev 30개, 무관한 질문 20개 (조정용)
    test  CS test 100개, 메뉴 test 30개, 무관한 질문 20개 (한 번만 실행)
"""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv


EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
INTENTS = ("menu", "cs", "unknown")


def load_cases(split: str) -> list[dict]:
    cs_splits = ("dev", "dev2") if split == "dev" else ("test",)
    cs = [c for c in json.loads((EVAL_DIR / "cs_golden_queries.json").read_text(encoding="utf-8")) if c["split"] in cs_splits]
    menu = [c for c in json.loads((EVAL_DIR / "menu_golden_queries.json").read_text(encoding="utf-8")) if c["split"] == split]
    unknown = [c for c in json.loads((EVAL_DIR / "intent_unknown_queries.json").read_text(encoding="utf-8")) if c["split"] == split]
    # 조각 수·순살 비율·매장 가격처럼 메뉴 질문처럼 보여도 답이 CS 데이터에만 있으면 CS가 정답이다.
    return (
        [{"id": c["id"], "query": c["query"], "expected": "cs"} for c in cs]
        + [{"id": c["id"], "query": c["query"], "expected": "menu"} for c in menu]
        + [{"id": c["id"], "query": c["query"], "expected": "unknown"} for c in unknown]
    )


async def _classify_all(cases: list[dict]) -> list[dict]:
    from graph.graph import _classifier_llm
    from graph.intent import classify_intent

    semaphore = asyncio.Semaphore(8)

    async def one(case: dict) -> dict:
        async with semaphore:
            intent, source = await classify_intent(case["query"], last_menu_query=None, llm=_classifier_llm)
        return {**case, "predicted": intent, "source": source, "correct": intent == case["expected"]}

    return await asyncio.gather(*(one(c) for c in cases))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    args = parser.parse_args()
    output_path = RESULTS_DIR / f"intent_golden_{args.split}.json"
    if args.split == "test" and output_path.exists():
        raise SystemExit(f"test 결과가 이미 있습니다: {output_path}")

    load_dotenv()
    rows = asyncio.run(_classify_all(load_cases(args.split)))
    RESULTS_DIR.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"{args.split} n={len(rows)} → {output_path}")
    print("정답\\예측  " + "  ".join(f"{i:>7}" for i in INTENTS))
    for expected in INTENTS:
        counts = Counter(r["predicted"] for r in rows if r["expected"] == expected)
        total = sum(counts.values())
        cells = "  ".join(f"{counts[i]:>7}" for i in INTENTS)
        print(f"{expected:9} {cells}   재현율 {counts[expected] / max(total, 1):.1%} (n={total})")
    for source in ("rule", "llm"):
        group = [r for r in rows if r["source"] == source]
        print(f"{source:5} 경로 {len(group)}건, 정확도 {sum(r['correct'] for r in group) / max(len(group), 1):.1%}")
    print("\n틀린 질문:")
    for r in rows:
        if not r["correct"]:
            print(f"- [{r['source']}] {r['expected']} → {r['predicted']} | {r['query'][:60]}")


if __name__ == "__main__":
    main()
