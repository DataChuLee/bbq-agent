# Menu Image URL Delivery Design

## Summary

This design adds menu image rendering to the existing BBQ chat recommendation flow without changing how the LLM reasons about menu recommendations.

The system will treat `imageURL` as UI-only metadata:

- The menu source data keeps `imageURL` in `Data/bbq_menu.json`.
- The menu vector index stores `imageURL` in document metadata.
- Retrieval returns `imageURL` alongside other menu card fields.
- The `menu_cards` API response includes `imageURL` per item.
- The frontend renders images when available and degrades cleanly when they are missing or fail to load.
- The LLM prompt and natural-language recommendation flow remain unchanged.

## Goals

- Show menu images together with recommended menu cards in the chat UI.
- Keep the existing menu recommendation flow and message types stable.
- Avoid sending image URLs into the LLM prompt when they are not needed for reasoning.
- Make the feature resilient to missing image data and image load failures.

## Non-Goals

- Using image URLs as part of the LLM prompt or tool reasoning.
- Adding image-based ranking, reranking, or recommendation logic.
- Introducing a new message type for image cards.
- Redesigning the broader chat UI beyond adding menu images to cards.

## Current Context

The current system already has a stable menu recommendation pipeline:

1. `Data/bbq_menu.json` is the source of menu data.
2. `vectorstore/build_menu_index.py` builds the Chroma menu index.
3. `tools/search_menu.py` retrieves menu documents and returns structured result items.
4. The graph returns a `menu_cards` response.
5. The frontend maps `menu_cards.items[]` into `MenuCard` components.

This makes the feature a metadata extension, not a new retrieval architecture.

## Decision

Adopt approach 1:

- `imageURL` is retrieval output and frontend rendering data only.
- The LLM continues to reason over menu name, category, price, description, allergy, texture, spiciness, nutrition, and options.
- The frontend receives `imageURL` through the existing `menu_cards` payload and renders the image if present.

This is preferred because it keeps prompt cost low, avoids polluting generation context with non-semantic URL strings, and fits the existing card-oriented response pipeline.

## Architecture

### Source Data

`Data/bbq_menu.json` remains the source of truth for menu image URLs. Each menu item may include:

```json
{
  "메뉴명": "뿜치킹",
  "imageURL": "https://static.bbqorder.co.kr/menu/..."
}
```

`imageURL` is optional. Missing values must not block indexing or response generation.

### Vector Index

`vectorstore/build_menu_index.py` will include `imageURL` in document metadata when building Chroma documents.

The embedding text will not change to include URL strings. URLs do not improve semantic search quality and should remain metadata only.

### Retrieval Tool

`tools/search_menu.py` will read `imageURL` from document metadata and include it in each returned result item.

Returned item shape will become:

```json
{
  "name": "뿜치킹",
  "category": "신메뉴",
  "price": 25000,
  "allergy": "우유, 땅콩, 대두, 밀, 닭고기, 쇠고기",
  "texture": "바삭함",
  "spiciness": "순함",
  "nutrition": "열량(kcal): 302 ...",
  "options": "[...]",
  "description": "한입 가득 뿜뿜!! ...",
  "imageURL": "https://static.bbqorder.co.kr/menu/..."
}
```

### Final Response

The existing `menu_cards` response type stays unchanged at the message level. Only each item is extended with `imageURL`.

Response example:

```json
{
  "type": "menu_cards",
  "items": [
    {
      "name": "뿜치킹",
      "category": "신메뉴",
      "price": 25000,
      "description": "한입 가득 뿜뿜!! ...",
      "allergy": "우유, 땅콩, 대두, 밀, 닭고기, 쇠고기",
      "nutrition": "열량(kcal): 302 ...",
      "options": "[...]",
      "imageURL": "https://static.bbqorder.co.kr/menu/..."
    }
  ]
}
```

No new message type is introduced.

### Frontend Rendering

The frontend will extend its `MenuCard` type with `imageURL?: string`.

The card renderer will:

- render a menu image region when `imageURL` exists
- keep the current text-first layout if `imageURL` is missing
- recover cleanly if the image fails to load

The image is decorative support for the recommendation, not the primary content. The menu name, category, description, and price remain the primary readable information.

## Data Flow

1. `bbq_menu.json` stores menu data including optional `imageURL`.
2. Menu index build writes `imageURL` into Chroma metadata.
3. `search_menu(query)` retrieves relevant documents.
4. Retrieval results include `imageURL` in structured menu items.
5. The graph emits the normal `menu_cards` response.
6. SSE and message persistence carry the same `items[]` payload.
7. The frontend maps `imageURL` into `MenuCard`.
8. The UI renders the image if present.

## Components Affected

- `vectorstore/build_menu_index.py`
- `tools/search_menu.py`
- `tools/final_answer.py`
- `frontend/src/types/chat.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/components/chat/MenuCard.tsx`
- `docs/API.md`

## Error Handling

### Missing `imageURL` in source data

Behavior:

- indexing continues normally
- retrieval continues normally
- response item may omit `imageURL` or send it as empty
- frontend renders the existing non-image card layout

This is acceptable because image display is optional metadata.

### Stale vector index

If `bbq_menu.json` has `imageURL` values but the Chroma metadata was built before that field existed, retrieval will not surface the image URL.

Required behavior:

- document the dependency on re-running `python -m vectorstore.build_menu_index`
- do not attempt runtime repair inside request handling

### Image load failure in browser

If the remote image URL fails, the frontend must preserve the card layout and hide or replace the broken image region with a neutral fallback.

This failure must not break rendering of the card body.

### LLM response generation

No behavior change is expected for text generation because the LLM prompt does not depend on `imageURL`.

## Testing

### Backend verification

- rebuild the menu index after the metadata change
- run a menu query and verify `search_menu` returns `imageURL`
- verify `menu_cards.items[]` contains `imageURL` for menus that have it
- verify menus without `imageURL` still return valid items

### Frontend verification

- verify cards render normally when `imageURL` is present
- verify cards render normally when `imageURL` is absent
- verify broken image URLs do not collapse or break the card layout
- verify text content remains readable on mobile and desktop

### Regression verification

- existing menu recommendation responses still stream correctly
- `text` and `clarification` responses remain unchanged
- session message persistence still works with the expanded `items[]` shape

## Acceptance Criteria

- Menu retrieval results can carry `imageURL` end-to-end from source data to frontend card props.
- The LLM prompt path remains unchanged and does not include image URLs.
- Recommended menu cards display images when available.
- Missing or broken images do not break the recommendation experience.
- The API contract and internal docs reflect the new `imageURL` field.

## Rollout Notes

- This feature requires a menu index rebuild after code changes.
- The design assumes the remote `imageURL` values in `bbq_menu.json` are already populated and valid.
- If the team later wants image-aware prompting, that should be treated as a separate design and not folded into this change.
