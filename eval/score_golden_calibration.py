"""사람 판정과 Claude 라벨의 일치도(가중 kappa)를 계산한다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.score_golden_calibration
"""

import csv
import io
import json
from pathlib import Path


EVAL_DIR = Path(__file__).parent
GRADES = (0, 1, 2)


def weighted_kappa(pairs: list[tuple[int, int]]) -> float:
    """0~2점 순서형 라벨이라 1점 차이보다 2점 차이를 더 크게 벌하는 이차 가중을 쓴다."""
    n = len(pairs)
    weight = {(a, b): (a - b) ** 2 / (len(GRADES) - 1) ** 2 for a in GRADES for b in GRADES}
    observed = sum(weight[pair] for pair in pairs) / n
    row = {g: sum(a == g for a, _ in pairs) / n for g in GRADES}
    col = {g: sum(b == g for _, b in pairs) / n for g in GRADES}
    expected = sum(weight[(a, b)] * row[a] * col[b] for a in GRADES for b in GRADES)
    return 1 - observed / expected if expected else 1.0


def _read_sheet(path: Path) -> list[dict]:
    raw = path.read_bytes()
    # 엑셀이 CSV를 CP949로 다시 저장하는 경우가 있어 둘 다 읽는다.
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(encoding))))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 읽을 수 없습니다: {path}")


def main() -> None:
    labels = json.loads((EVAL_DIR / "menu_golden_labels.json").read_text(encoding="utf-8"))
    rows = _read_sheet(EVAL_DIR / "menu_golden_calibration_scored.csv")
    pairs, invalid = [], []
    for row in rows:
        human = row["점수"].strip()
        if human not in {"0", "1", "2"}:
            invalid.append((row["질의ID"], row["메뉴명"], human))
            continue
        pairs.append((int(human), labels[row["질의ID"]].get(row["메뉴명"], 0)))
    if invalid:
        raise SystemExit(f"점수가 0/1/2가 아닌 칸 {len(invalid)}개: {invalid[:5]}")

    agree = sum(a == b for a, b in pairs) / len(pairs)
    print(f"판정 {len(pairs)}칸 | 완전 일치 {agree:.1%} | 가중 kappa {weighted_kappa(pairs):.3f}")
    for human, claude in sorted({p for p in pairs if p[0] != p[1]}):
        count = pairs.count((human, claude))
        print(f"  사람 {human}점 / Claude {claude}점: {count}칸")


assert weighted_kappa([(0, 0), (1, 1), (2, 2)]) == 1.0
assert weighted_kappa([(0, 2), (2, 0)]) < 0

if __name__ == "__main__":
    main()
