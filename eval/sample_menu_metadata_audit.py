"""메뉴 메타데이터 검수 시트를 만든다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.sample_menu_metadata_audit --seed 42
"""

import argparse
import csv
import json
import random
from pathlib import Path

from vectorstore.build_menu_index import DATA_PATH, build_metadata


SAMPLE_SIZE = 50
# 메뉴 조건 평가(ConstraintPass)가 채점에 쓰는 속성만 검수한다.
AUDIT_FIELDS = (
    "product_family",
    "spiciness",
    "primary_texture",
    "cooking_method",
    "sauce_style",
)
OUTPUT_DIR = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    # 수정 과정에서 한 번도 보지 않은 메뉴만 모아 최종 검증용 시트를 만든다.
    parser.add_argument("--holdout", action="store_true")
    args = parser.parse_args()
    name = "holdout" if args.holdout else f"seed{args.seed}"
    # 검수 결과를 덮어쓰지 않도록 시트마다 파일을 나눈다.
    output_path = OUTPUT_DIR / f"menu_metadata_audit_{name}.csv"
    if output_path.exists():
        raise SystemExit(f"이미 있는 검수 시트입니다: {output_path}")

    items = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if args.holdout:
        audited = set()
        for path in OUTPUT_DIR.glob("menu_metadata_audit_seed*.csv"):
            with path.open(encoding="utf-8-sig") as f:
                audited |= {row["메뉴명"] for row in csv.DictReader(f)}
        sample = [item for item in items if item.get("메뉴명", "") not in audited]
    else:
        sample = random.Random(args.seed).sample(items, min(SAMPLE_SIZE, len(items)))
    header = ["메뉴명", "구분", "설명"]
    for field in AUDIT_FIELDS:
        header += [field, f"{field}_ok"]
    header.append("메모")

    # 엑셀에서 한글이 깨지지 않도록 BOM을 붙인다.
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for item in sample:
            metadata = build_metadata(item)
            row = [item.get("메뉴명", ""), item.get("구분", ""), item.get("설명", "")]
            for field in AUDIT_FIELDS:
                row += [metadata[field], ""]
            row.append("")
            writer.writerow(row)
    print(f"{len(sample)}개 메뉴 → {output_path}")


if __name__ == "__main__":
    main()
