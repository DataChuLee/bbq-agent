"""사람 판정과 CS 채점자 판정의 일치도를 계산한다.

같은 주장 목록을 후보 모델에 다시 판정시켜, 채점 모델을 사람 기준으로 고른다.

실행 방법:
    venv\Scripts\python.exe -m eval.score_cs_judge_calibration --model gpt-5.4-mini
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from eval.run_cs_grounding import _load_reference_rows, verify_claims
from eval.score_golden_calibration import _read_sheet, weighted_kappa


EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"

# 0/1 두 값만 있으면 이차 가중이 상수배로 약분되어 Cohen's kappa와 같다.
assert weighted_kappa([(0, 0), (1, 1), (0, 1), (1, 0)]) == 0.0
assert weighted_kappa([(0, 0), (1, 1)]) == 1.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    load_dotenv()
    sheet = _read_sheet(EVAL_DIR / "cs_grounding_calibration_scored.csv")
    rows = json.loads((RESULTS_DIR / "cs_grounding_dev_baseline.json").read_text(encoding="utf-8"))
    # 보정 시트는 채점 결과의 주장 순서대로 만들었으므로, 순서가 어긋나면 결과 파일이 다시 생성된 것이다.
    if [r["주장"] for r in sheet] != [v["claim"] for row in rows for v in row["verdicts"]]:
        raise SystemExit("보정 시트와 채점 결과의 주장이 다릅니다. dev 기준선 결과를 다시 만들지 마세요.")

    references = _load_reference_rows()
    verdicts = []
    for row in rows:
        reference = "\n\n".join(f"[{i}] {references[c]}" for i, c in enumerate(row["gold_categories"], start=1))
        verdicts += verify_claims([v["claim"] for v in row["verdicts"]], reference, model=args.model)
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / f"cs_judge_calibration_{args.model}.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    judge = [int(v["verdict"] == "supported") for v in verdicts]
    human = [int(r["최종 판정"]) for r in sheet]
    pairs = list(zip(human, judge))
    agree = sum(a == b for a, b in pairs)
    print(f"{args.model}: kappa {weighted_kappa(pairs):.3f}, 일치 {agree}/{len(pairs)} = {agree / len(pairs):.1%}")
    print("(사람, 채점자) 분포:", dict(Counter(pairs)))
    print(f"근거 있는 주장 비율: 사람 {sum(human) / len(human):.1%}, 채점자 {sum(judge) / len(judge):.1%}")
    for r, h, j, v in zip(sheet, human, judge, verdicts):
        if h != j:
            print(f"- {r['질의ID']} 사람={h} 채점자={j} | {r['주장']}\n  사람: {r['판정 근거']}\n  채점자: {v['reason']}")


if __name__ == "__main__":
    main()
