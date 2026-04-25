# Menu Image URL Design

- Date: 2026-04-25
- Status: Approved for planning
- Scope: Menu recommendation result cards only

## Context

The current `menu agent` uses text-first retrieval over `Data/bbq_menu.json` and returns `menu_cards` without any image field. The immediate goal is to enrich the recommendation cards with official BBQ menu images without changing retrieval behavior.

The project already has a stable text RAG flow:

- `vectorstore/build_menu_index.py` builds menu documents and metadata.
- `tools/search_menu.py` retrieves menu entries and returns structured card data.
- `tools/final_answer.py` formats `menu_cards`.
- `frontend/src/components/chat/MenuCard.tsx` renders each recommended menu card.

## Goals

- Add official BBQ menu image URLs to menu recommendation results.
- Keep the current text retrieval behavior unchanged.
- Refresh image URLs as part of the existing menu index rebuild flow.
- Use only official BBQ site data as the image source.

## Non-Goals

- Do not introduce multimodal RAG in this phase.
- Do not use image embeddings, image similarity, or visual reranking.
- Do not support user-uploaded image search.
- Do not add fuzzy matching between local menu data and official site menus.
- Do not fail the full build when some menus have no matching official image.

## Options Considered

### 1. Recommended: Enrich menu data, keep text RAG unchanged

Collect official image URLs during menu rebuild, attach `image_url` to each menu record, store it as metadata, and return it in the existing `menu_cards` flow.

Why this is selected:

- It matches the immediate goal exactly: better result presentation.
- It minimizes changes to the current retrieval architecture.
- It keeps runtime independent from the official site.
- It can evolve later into a richer image system if needed.

### 2. Separate image manifest joined at build/runtime

Store a separate `menu_images` mapping and join it into results later.

Why this is not selected now:

- It adds an extra synchronization surface.
- It makes the current code path more complex without improving the user-facing goal.

### 3. Multimodal/image-aware RAG

Use image-derived signals in retrieval.

Why this is deferred:

- Current phase only needs result-card imagery.
- Existing menu text and metadata already carry the retrieval value.
- Complexity is not justified until there is a real visual-search use case.

## Selected Design

The selected design is `text RAG + image URL metadata`.

- Retrieval remains text-driven.
- Official image URLs are collected during menu rebuild.
- Each local menu record may receive an optional `image_url`.
- `image_url` is returned with search results and rendered in the card UI when present.

## Architecture

The menu recommendation path stays structurally the same:

`intent_classifier -> menu_agent -> search_menu -> final_answer_menu -> frontend MenuCard`

The new image workflow is inserted only into the build path:

`official BBQ site scrape -> menu data enrichment -> menu index rebuild`

This keeps external-site dependence out of runtime request handling. Runtime remains local-data only.

## Components

### Official Menu Image Collection

A build-time step fetches official BBQ menu names and their image URLs from the official BBQ site.

Output:

- official menu name
- official image URL

### Menu Data Enrichment

The local menu dataset is enriched before indexing.

Rules:

- Match only by exact menu name equality.
- If exact match succeeds, store `image_url` on the local menu record.
- If exact match fails, leave the record unchanged.
- No fuzzy or heuristic matching in this phase.

### Index Build

`vectorstore/build_menu_index.py` continues to build menu documents and metadata. It also carries `image_url` forward as optional metadata for response generation.

Important constraint:

- `image_url` is response metadata, not a retrieval signal.

### Retrieval and Response Formatting

`tools/search_menu.py` returns `image_url` together with the existing fields such as `name`, `category`, `price`, and `description`.

`tools/final_answer.py` includes `image_url` in the `menu_cards` payload.

### Frontend Rendering

The frontend card model and `MenuCard` component accept an optional `image_url`.

Rendering rule:

- If `image_url` exists, render the menu image.
- If it does not exist, render the card without an image and preserve layout stability.

## Data Model

The local menu dataset gains one optional field:

- `image_url: string | null`

This field is populated only from official BBQ site data and only when menu names match exactly.

The frontend card type gains one optional field:

- `image_url?: string`

The search result JSON and final `menu_cards` payload also carry this optional field.

## Data Flow

1. Run the existing menu index rebuild command.
2. Fetch official menu image data from the official BBQ site.
3. For each local menu in `Data/bbq_menu.json`, compare local menu name with official menu name.
4. If names match exactly, attach `image_url`.
5. Build Chroma documents and metadata from the enriched dataset.
6. At runtime, `search_menu` retrieves menu entries as before.
7. Search results include `image_url` when present.
8. `final_answer_menu` emits `menu_cards` with optional `image_url`.
9. Frontend renders menu cards with image-if-present behavior.

## Matching Policy

The matching policy is intentionally strict for phase 1.

- Source of truth for images: official BBQ site
- Local join key: local menu name
- Match mode: exact match only
- Unmatched record behavior: leave `image_url` empty

Trade-off:

- This avoids wrong image assignments.
- Some valid menus may remain unmatched if names differ slightly.

This trade-off is acceptable for phase 1 because correctness matters more than image coverage.

## Error Handling

Image support must degrade gracefully and must not break menu recommendations.

- If official image collection fails entirely, the build must continue with menus that have no newly-enriched `image_url` values, and runtime must still serve text-only menu results.
- If a menu has no exact match, it remains image-less.
- If `image_url` is empty or missing, backend responses remain valid.
- If the frontend cannot load an image URL, the card must fall back to text-only presentation without layout breakage.
- Image-related failures must not affect retrieval scoring or query routing.

Core rule:

- `image_url` is optional metadata, never a hard dependency for answering menu questions.

## Testing

### Data Enrichment Tests

- Exact-match menus receive `image_url`.
- Non-matching menus remain unchanged.
- Missing official images do not corrupt existing menu records.

### Index Build Tests

- Menu index build succeeds with enriched data.
- `image_url` is carried into metadata safely when present.
- Empty `image_url` does not break document generation.

### Retrieval and Response Tests

- `search_menu` returns `image_url` when it exists.
- `search_menu` still returns valid results when it does not.
- `final_answer_menu` includes `image_url` in `menu_cards`.

### Frontend Tests

- Menu card renders correctly with an image.
- Menu card renders correctly without an image.
- Broken image loads do not collapse the card layout.

### Regression Tests

- Existing text recommendation behavior remains unchanged.
- Existing price/category/description-based usage still works.

## Rollout Notes

- This phase should be introduced without changing the public response type (`menu_cards` remains the same message type).
- Only the shape of each card item expands with an optional `image_url`.
- Because the project already rebuilds menu indices manually, image refresh naturally fits that workflow.

## Future Extensions

Possible later phases, explicitly out of scope now:

- fuzzy menu-name matching with review workflow
- separate image manifest management
- scheduled image refresh
- multimodal retrieval
- user-uploaded image search

## Final Decision

Phase 1 will implement:

- official BBQ site image collection
- exact-name menu matching
- optional `image_url` enrichment in menu data
- menu rebuild integration
- backend propagation of `image_url`
- frontend conditional image rendering

Phase 1 will not implement:

- multimodal RAG
- fuzzy matching
- build failure on unmatched menus
- runtime dependency on the official BBQ site
