# Menu Taxonomy Filter Design

## Goal

Improve BBQ menu recommendation relevance by adding an explicit menu taxonomy to the RAG pipeline. When a user asks for chicken, the system should recommend main chicken products instead of items that only contain the word "chicken", such as chicken burgers.

## Problem

The current menu retrieval pipeline relies on text similarity and metadata such as `category`, `texture`, and `spiciness`. This lets unrelated product families appear in results when their text overlaps with the query.

Example:

- User asks: `매운 치킨 추천해줘`
- Current candidates can include: `BBQ 썬더 치킨버거 스파이시`
- Reason: the item contains `치킨`, has `spiciness=매움`, and is textually close to the query.

This is not primarily an embedding quality problem. It is a missing domain taxonomy problem.

## Scope

In scope:

- Add a normalized `product_family` metadata field to menu index records.
- Infer the user's requested product family from the natural-language query.
- Apply a deterministic post-retrieval filter in `search_menu`.
- Keep explicit burger, pizza, side, drink, and sauce queries working.
- Add focused tests for taxonomy metadata and filtering behavior.

Out of scope:

- Replacing Chroma or SelfQueryRetriever.
- Building a full ranking engine.
- Personalization based on previous user behavior.
- Frontend UI changes.
- Editing the source menu JSON manually unless required by the implementation.

## Taxonomy

The system will normalize menu items into product families:

```text
main_chicken
combo_chicken
single_chicken
burger_pizza
side
drink
sauce
seasoning
unknown
```

Initial category mapping:

```text
후라이드      -> main_chicken
양념          -> main_chicken
구이          -> main_chicken
반반          -> main_chicken
세트메뉴      -> combo_chicken
1인분 메뉴    -> single_chicken
피자&버거     -> burger_pizza
사이드메뉴    -> side
음료          -> drink
소스&시즈닝&무 -> sauce
시즈닝        -> seasoning
신메뉴        -> inferred from menu name and description, default unknown
```

`신메뉴` is mixed and cannot be mapped by category alone. For this category, the implementation should use conservative name and description rules:

- burger or pizza terms imply `burger_pizza`
- side-like terms such as fries, balls, corn ribs, and fried sides imply `side`
- otherwise chicken-like full-menu names imply `main_chicken`
- ambiguous items fall back to `unknown`

## Query Family Inference

`search_menu` will infer the requested product family from the raw user query before invoking SelfQueryRetriever. The inferred family is then used after retrieval to filter the structured candidate items.

Rules:

- If the query explicitly mentions burger or pizza, request `burger_pizza`.
- If the query explicitly mentions side terms, request `side`.
- If the query explicitly mentions drink terms, request `drink`.
- If the query explicitly mentions sauce or seasoning terms, request `sauce` or `seasoning`.
- If the query mentions chicken terms such as `치킨`, `닭`, `윙`, `봉`, `순살`, or `반마리` without burger or pizza terms, request chicken families.
- If no product family is clear, do not apply a product-family filter.

For chicken requests, the allowed families are:

```text
main_chicken
single_chicken
combo_chicken
unknown
```

`unknown` remains allowed only as a compatibility fallback for older indexes or ambiguous new menu records. It should not be used to admit clearly non-chicken families.

## Retrieval Flow

1. The user sends a menu query.
2. `search_menu(query, state)` checks the session cache.
3. If there is no cache hit, SelfQueryRetriever retrieves candidate menu documents.
4. `search_menu` converts documents into structured menu items including `product_family`.
5. `search_menu` applies product-family filtering based on query inference.
6. If filtered results exist, return them.
7. If filtering removes every candidate, return an empty result with a short "no matching menu" message.

The first implementation should not expand into unrelated families automatically. If a user asks for chicken and only burger candidates are found, returning no result is better than recommending the wrong product family.

## Components

### `vectorstore/build_menu_index.py`

Add a helper that derives `product_family` from each source menu item. Include this value in Chroma document metadata through `build_metadata`.

The helper should be deterministic and unit-testable.

### `tools/search_menu.py`

Add helpers that:

- infer the requested family from the user query
- decide whether a result item is allowed for that request
- filter structured result items before returning JSON

The tool must keep the existing response shape:

```json
{
  "results": [
    {
      "name": "...",
      "category": "...",
      "price": 0,
      "allergy": "...",
      "texture": "...",
      "spiciness": "...",
      "nutrition": "...",
      "options": "...",
      "description": "...",
      "imageURL": "...",
      "product_family": "main_chicken"
    }
  ]
}
```

### `tools/final_answer.py`

Preserve `product_family` if present. This is not required for rendering, but it keeps the API payload inspectable and useful for debugging.

## Error Handling

- Missing `product_family` metadata should be treated as `unknown`.
- Malformed or empty metadata should not crash search.
- Existing cache entries without `product_family` should still return valid menu cards.
- If post-filtering removes all candidates, return `{"results": [], "message": "조건에 맞는 메뉴를 찾지 못했습니다."}`.

## Testing

Add or extend tests to verify:

- `build_metadata` includes `product_family`.
- category-based mapping classifies known categories correctly.
- `매운 치킨 추천` excludes `burger_pizza` results.
- `치킨버거 추천` keeps `burger_pizza` results.
- missing `product_family` does not crash retrieval formatting.
- `final_answer_menu` preserves `product_family`.

## Verification

Run focused backend tests:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_image_url -v
```

If new taxonomy tests are added to a separate file, also run:

```powershell
venv\Scripts\python.exe -m unittest tests.test_menu_taxonomy_filter -v
```

After code changes, rebuild the menu index:

```powershell
venv\Scripts\python.exe -m vectorstore.build_menu_index
```

Manual checks:

- `매운 치킨 추천해줘` should not return `BBQ 썬더 치킨버거 스파이시`.
- `치킨버거 추천해줘` should be allowed to return `BBQ 썬더 치킨버거 스파이시`.

## Risks

- `신메뉴` contains mixed item types, so name-based inference must be conservative.
- Existing persisted Chroma metadata will not include `product_family` until the index is rebuilt.
- Allowing `unknown` for chicken queries preserves compatibility but may let ambiguous legacy records through. This is acceptable for the first implementation because explicit non-chicken families are still excluded.

## Acceptance Criteria

- Chicken recommendation queries no longer recommend chicken burgers unless the user explicitly asks for burgers.
- Explicit burger queries still work.
- Taxonomy metadata is stored in the menu index and returned by `search_menu`.
- Existing menu card response fields remain backward compatible.
- Focused tests pass.
