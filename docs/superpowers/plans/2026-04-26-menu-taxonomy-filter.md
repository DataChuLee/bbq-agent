# Menu Taxonomy Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent chicken recommendation queries from returning chicken burgers or other unrelated product families.

**Architecture:** Add deterministic `product_family` taxonomy metadata during menu indexing, then use query-family inference in `search_menu` to post-filter retrieved candidates. Preserve the existing response shape while adding `product_family` for debugging and downstream inspection.

**Tech Stack:** Python 3.11, unittest, LangChain tools, Chroma metadata, existing BBQ menu JSON.

---

## File Structure

- Create: `tests/test_menu_taxonomy_filter.py`
  - Focused taxonomy tests for metadata classification, query-family inference, retrieval filtering, and final answer preservation.
- Modify: `vectorstore/build_menu_index.py`
  - Add `derive_product_family(item)` and include `product_family` in `build_metadata`.
- Modify: `tools/search_menu.py`
  - Add query-family inference and deterministic post-retrieval filtering.
  - Include `product_family` in each returned result item.
- Modify: `tools/final_answer.py`
  - Preserve `product_family` in `menu_cards.items[]`.
- Modify: `docs/API.md`
  - Document optional `product_family` on menu card items if existing API examples are already being maintained for card metadata.

---

### Task 1: Add Failing Taxonomy Tests

**Files:**
- Create: `tests/test_menu_taxonomy_filter.py`

- [ ] **Step 1: Create focused failing tests**

Create `tests/test_menu_taxonomy_filter.py` with:

```python
import json
import unittest
from unittest.mock import patch

from tools.final_answer import final_answer_menu
from tools.search_menu import infer_requested_family, search_menu
from vectorstore.build_menu_index import build_metadata, derive_product_family


def make_doc(name, category, product_family, spiciness="매움"):
    return type(
        "Doc",
        (),
        {
            "page_content": f"{name} 설명",
            "metadata": {
                "name": name,
                "category": category,
                "price": 25000,
                "spiciness": spiciness,
                "texture": "바삭함",
                "product_family": product_family,
                "imageURL": "https://example.com/menu.png",
            },
        },
    )()


class ProductFamilyMetadataTests(unittest.TestCase):
    def test_derive_product_family_maps_main_chicken_category(self):
        self.assertEqual(
            derive_product_family({"구분": "양념", "메뉴명": "황금올리브치킨™매운양념"}),
            "main_chicken",
        )

    def test_derive_product_family_maps_burger_category(self):
        self.assertEqual(
            derive_product_family({"구분": "피자&버거", "메뉴명": "BBQ 썬더 치킨버거 스파이시"}),
            "burger_pizza",
        )

    def test_derive_product_family_infers_new_menu_side(self):
        self.assertEqual(
            derive_product_family({"구분": "신메뉴", "메뉴명": "뿜치킹 감자튀김"}),
            "side",
        )

    def test_build_metadata_includes_product_family(self):
        metadata = build_metadata({"구분": "후라이드", "메뉴명": "황금올리브치킨™핫크리스피"})

        self.assertEqual(metadata["product_family"], "main_chicken")


class QueryFamilyInferenceTests(unittest.TestCase):
    def test_infer_requested_family_treats_chicken_as_chicken(self):
        self.assertEqual(infer_requested_family("매운 치킨 추천해줘"), "chicken")

    def test_infer_requested_family_treats_chicken_burger_as_burger_pizza(self):
        self.assertEqual(infer_requested_family("치킨버거 추천해줘"), "burger_pizza")

    def test_infer_requested_family_returns_none_for_generic_recommendation(self):
        self.assertIsNone(infer_requested_family("맛있는 메뉴 추천해줘"))


class SearchMenuTaxonomyFilterTests(unittest.TestCase):
    @patch("tools.search_menu._get_retriever")
    def test_chicken_query_excludes_burger_pizza_results(self, mock_get_retriever):
        mock_get_retriever.return_value.invoke.return_value = [
            make_doc("BBQ 썬더 치킨버거 스파이시", "피자&버거", "burger_pizza"),
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "main_chicken"),
        ]

        payload = json.loads(search_menu.func("매운 치킨 추천해줘", {"menu_results": {}}))

        self.assertEqual([item["name"] for item in payload["results"]], ["황금올리브치킨™핫크리스피"])

    @patch("tools.search_menu._get_retriever")
    def test_burger_query_keeps_burger_pizza_results(self, mock_get_retriever):
        mock_get_retriever.return_value.invoke.return_value = [
            make_doc("BBQ 썬더 치킨버거 스파이시", "피자&버거", "burger_pizza"),
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "main_chicken"),
        ]

        payload = json.loads(search_menu.func("치킨버거 추천해줘", {"menu_results": {}}))

        self.assertEqual([item["name"] for item in payload["results"]], ["BBQ 썬더 치킨버거 스파이시"])

    @patch("tools.search_menu._get_retriever")
    def test_missing_product_family_defaults_to_unknown_without_crashing(self, mock_get_retriever):
        doc = make_doc("임시 치킨", "신메뉴", "main_chicken")
        del doc.metadata["product_family"]
        mock_get_retriever.return_value.invoke.return_value = [doc]

        payload = json.loads(search_menu.func("매운 치킨 추천해줘", {"menu_results": {}}))

        self.assertEqual(payload["results"][0]["product_family"], "unknown")


class FinalAnswerTaxonomyTests(unittest.TestCase):
    def test_final_answer_menu_preserves_product_family(self):
        payload = json.loads(
            final_answer_menu.invoke(
                {
                    "items": [
                        {
                            "name": "황금올리브치킨™핫크리스피",
                            "category": "후라이드",
                            "price": 24000,
                            "description": "매운 치킨",
                            "product_family": "main_chicken",
                        }
                    ]
                }
            )
        )

        self.assertEqual(payload["items"][0]["product_family"], "main_chicken")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_taxonomy_filter -v
```

Expected: FAIL because `derive_product_family` and `infer_requested_family` do not exist, and `product_family` is not preserved.

- [ ] **Step 3: Commit failing tests**

```powershell
git add tests/test_menu_taxonomy_filter.py docs/superpowers/plans/2026-04-26-menu-taxonomy-filter.md
git commit -m "test: cover menu taxonomy filtering"
```

---

### Task 2: Add Product Family Metadata

**Files:**
- Modify: `vectorstore/build_menu_index.py`
- Test: `tests/test_menu_taxonomy_filter.py`

- [ ] **Step 1: Implement taxonomy metadata helper**

In `vectorstore/build_menu_index.py`, add constants and helper functions after `COLLECTION_NAME`:

```python
MAIN_CHICKEN_CATEGORIES = {"후라이드", "양념", "구이", "반반"}
COMBO_CHICKEN_CATEGORIES = {"세트메뉴"}
SINGLE_CHICKEN_CATEGORIES = {"1인분 메뉴"}
BURGER_PIZZA_CATEGORIES = {"피자&버거"}
SIDE_CATEGORIES = {"사이드메뉴"}
DRINK_CATEGORIES = {"음료"}
SAUCE_CATEGORIES = {"소스&시즈닝&무"}
SEASONING_CATEGORIES = {"시즈닝"}

BURGER_PIZZA_TERMS = ("버거", "피자")
SIDE_TERMS = (
    "감자튀김",
    "치즈볼",
    "볼",
    "콘립",
    "김말이",
    "고추킹",
    "멘보샤",
    "소떡",
    "맛탕",
    "고로케",
    "떡볶이",
    "닭발튀김",
)
CHICKEN_TERMS = ("치킨", "닭", "윙", "봉", "순살", "통다리")


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def derive_product_family(item: dict) -> str:
    """Return a normalized product family for menu retrieval filtering."""
    category = str(item.get("구분", ""))
    name = str(item.get("메뉴명", ""))
    description = str(item.get("설명", ""))
    searchable = f"{name} {description}"

    if category in MAIN_CHICKEN_CATEGORIES:
        return "main_chicken"
    if category in COMBO_CHICKEN_CATEGORIES:
        return "combo_chicken"
    if category in SINGLE_CHICKEN_CATEGORIES:
        return "single_chicken"
    if category in BURGER_PIZZA_CATEGORIES:
        return "burger_pizza"
    if category in SIDE_CATEGORIES:
        return "side"
    if category in DRINK_CATEGORIES:
        return "drink"
    if category in SAUCE_CATEGORIES:
        return "sauce"
    if category in SEASONING_CATEGORIES:
        return "seasoning"

    if category == "신메뉴":
        if _contains_any(searchable, BURGER_PIZZA_TERMS):
            return "burger_pizza"
        if _contains_any(searchable, SIDE_TERMS):
            return "side"
        if _contains_any(searchable, CHICKEN_TERMS):
            return "main_chicken"

    return "unknown"
```

Update `build_metadata` to include:

```python
"product_family": derive_product_family(item),
```

- [ ] **Step 2: Run taxonomy metadata tests**

Run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_taxonomy_filter.ProductFamilyMetadataTests -v
```

Expected: PASS.

- [ ] **Step 3: Run existing image URL tests**

Run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_image_url -v
```

Expected: PASS. Existing metadata tests should still pass.

- [ ] **Step 4: Commit metadata implementation**

```powershell
git add vectorstore/build_menu_index.py tests/test_menu_taxonomy_filter.py
git commit -m "feat: add menu product family metadata"
```

---

### Task 3: Add Query Family Inference and Search Filtering

**Files:**
- Modify: `tools/search_menu.py`
- Test: `tests/test_menu_taxonomy_filter.py`

- [ ] **Step 1: Add query-family constants and helpers**

In `tools/search_menu.py`, add these constants and helpers after `TOP_K`:

```python
NO_MATCH_MESSAGE = "조건에 맞는 메뉴를 찾지 못했습니다."

CHICKEN_ALLOWED_FAMILIES = {"main_chicken", "single_chicken", "combo_chicken", "unknown"}

QUERY_FAMILY_ALLOWED = {
    "chicken": CHICKEN_ALLOWED_FAMILIES,
    "burger_pizza": {"burger_pizza", "unknown"},
    "side": {"side", "unknown"},
    "drink": {"drink", "unknown"},
    "sauce": {"sauce", "seasoning", "unknown"},
    "seasoning": {"seasoning", "sauce", "unknown"},
}

BURGER_PIZZA_QUERY_TERMS = ("버거", "피자")
SIDE_QUERY_TERMS = (
    "사이드",
    "감자튀김",
    "치즈볼",
    "콘립",
    "김말이",
    "고추킹",
    "멘보샤",
    "소떡",
    "맛탕",
    "고로케",
    "떡볶이",
    "닭발튀김",
)
DRINK_QUERY_TERMS = ("음료", "콜라", "제로콜라", "스프라이트", "레몬보이")
SAUCE_QUERY_TERMS = ("소스", "양념소스", "핫소스", "치킨무", "무")
SEASONING_QUERY_TERMS = ("시즈닝",)
CHICKEN_QUERY_TERMS = ("치킨", "닭", "윙", "봉", "순살", "반마리", "통다리")


def _query_contains_any(query: str, terms: tuple[str, ...]) -> bool:
    return any(term in query for term in terms)


def infer_requested_family(query: str) -> str | None:
    """Infer the requested product family from a raw Korean menu query."""
    normalized = query.replace(" ", "")

    if _query_contains_any(normalized, BURGER_PIZZA_QUERY_TERMS):
        return "burger_pizza"
    if _query_contains_any(normalized, SIDE_QUERY_TERMS):
        return "side"
    if _query_contains_any(normalized, DRINK_QUERY_TERMS):
        return "drink"
    if _query_contains_any(normalized, SAUCE_QUERY_TERMS):
        return "sauce"
    if _query_contains_any(normalized, SEASONING_QUERY_TERMS):
        return "seasoning"
    if _query_contains_any(normalized, CHICKEN_QUERY_TERMS):
        return "chicken"

    return None


def _filter_by_requested_family(items: list[dict], requested_family: str | None) -> list[dict]:
    if not requested_family:
        return items

    allowed = QUERY_FAMILY_ALLOWED.get(requested_family)
    if not allowed:
        return items

    return [
        item
        for item in items
        if str(item.get("product_family") or "unknown") in allowed
    ]
```

- [ ] **Step 2: Include `product_family` in result formatting**

In the result item dict inside `search_menu`, add:

```python
"product_family": meta.get("product_family", "unknown") or "unknown",
```

- [ ] **Step 3: Apply filtering before returning**

Update `search_menu` so it computes the requested family before retrieval and filters after formatting:

```python
requested_family = infer_requested_family(query)

retriever = _get_retriever()
docs = retriever.invoke(query)
```

After the loop that builds `results`, add:

```python
results = _filter_by_requested_family(results, requested_family)
```

Replace hardcoded no-match messages with:

```python
return json.dumps({"results": [], "message": NO_MATCH_MESSAGE}, ensure_ascii=False)
```

- [ ] **Step 4: Run search filtering tests**

Run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_taxonomy_filter.QueryFamilyInferenceTests tests.test_menu_taxonomy_filter.SearchMenuTaxonomyFilterTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit search filtering implementation**

```powershell
git add tools/search_menu.py tests/test_menu_taxonomy_filter.py
git commit -m "feat: filter menu search by product family"
```

---

### Task 4: Preserve Product Family in Final Menu Cards

**Files:**
- Modify: `tools/final_answer.py`
- Test: `tests/test_menu_taxonomy_filter.py`

- [ ] **Step 1: Add `product_family` to final cards**

In `tools/final_answer.py`, add this field to each card dict:

```python
"product_family": item.get("product_family", ""),
```

- [ ] **Step 2: Run final answer taxonomy test**

Run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_taxonomy_filter.FinalAnswerTaxonomyTests -v
```

Expected: PASS.

- [ ] **Step 3: Run existing final answer image URL test**

Run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_image_url.MenuImageURLTests.test_final_answer_menu_preserves_image_url -v
```

Expected: PASS.

- [ ] **Step 4: Commit final answer preservation**

```powershell
git add tools/final_answer.py tests/test_menu_taxonomy_filter.py
git commit -m "feat: preserve menu product family in cards"
```

---

### Task 5: Document API Payload Metadata

**Files:**
- Modify: `docs/API.md`

- [ ] **Step 1: Update menu card item documentation**

Find the section that describes `menu_cards.items[]`. Add `product_family` as optional metadata near `imageURL`:

```json
{
  "name": "황금올리브치킨™핫크리스피",
  "category": "후라이드",
  "price": 24000,
  "spiciness": "매움",
  "texture": "바삭함",
  "imageURL": "https://static.bbqorder.co.kr/menu/...",
  "product_family": "main_chicken"
}
```

Add this explanatory sentence:

```markdown
`product_family` is backend taxonomy metadata used to keep recommendations within the requested product family, such as `main_chicken`, `burger_pizza`, `side`, `drink`, `sauce`, or `seasoning`.
```

- [ ] **Step 2: Commit docs**

```powershell
git add docs/API.md
git commit -m "docs: document menu product family metadata"
```

---

### Task 6: Rebuild Index and Verify

**Files:**
- Generated data: `vectorstore/chroma_db/`

- [ ] **Step 1: Run all focused backend tests**

Run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_taxonomy_filter tests.test_menu_image_url -v
```

Expected: PASS.

- [ ] **Step 2: Rebuild the menu index**

Run:

```powershell
venv\Scripts\python.exe -m vectorstore.build_menu_index
```

Expected: command completes and prints the total number of stored vectors.

- [ ] **Step 3: Manually inspect taxonomy distribution**

Run:

```powershell
venv\Scripts\python.exe - <<'PY'
import json
from collections import Counter
from vectorstore.build_menu_index import derive_product_family

with open("Data/bbq_menu.json", encoding="utf-8") as f:
    data = json.load(f)

counts = Counter(derive_product_family(item) for item in data)
for family, count in sorted(counts.items()):
    print(f"{family}: {count}")
PY
```

Expected: output includes non-zero counts for `main_chicken`, `burger_pizza`, `side`, and `drink`.

- [ ] **Step 4: Commit generated index only if this repository tracks vectorstore data intentionally**

Check status:

```powershell
git status --short vectorstore/chroma_db
```

If the index files are tracked or the project convention is to commit them, run:

```powershell
git add vectorstore/chroma_db
git commit -m "chore: rebuild menu taxonomy index"
```

If the index files are not committed in this branch, leave them unstaged and note that local rebuild is required after pulling the code.

---

## Self-Review

- Spec coverage: the plan covers taxonomy metadata, query family inference, post-retrieval filtering, explicit burger query behavior, final payload preservation, tests, docs, and index rebuild.
- Placeholder scan: no `TBD`, `TODO`, or undefined implementation steps remain.
- Type consistency: `product_family`, `derive_product_family`, and `infer_requested_family` are named consistently across tasks and tests.
