import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_menu_gold_expected_ids_exist_in_menu_data() -> None:
    menu_items = json.loads((ROOT / "Data/bbq_menu.json").read_text(encoding="utf-8"))
    known_names = {item["메뉴명"] for item in menu_items}
    cases = json.loads((ROOT / "eval/menu_retrieval_gold.json").read_text(encoding="utf-8"))

    missing = {
        expected_id
        for case in cases
        for expected_id in case["expected_ids"]
        if expected_id not in known_names
    }

    assert missing == set()


def test_cs_gold_expected_ids_exist_in_cs_data() -> None:
    cs_df = pd.read_excel(ROOT / "Data/BBQ_CS.xlsx")
    known_categories = set(cs_df["CS 구분"].dropna().astype(str))
    cases = json.loads((ROOT / "eval/cs_retrieval_gold.json").read_text(encoding="utf-8"))

    missing = {
        expected_id
        for case in cases
        for expected_id in case["expected_ids"]
        if expected_id not in known_categories
    }

    assert missing == set()
