# Menu Image URL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `imageURL` from menu source data through retrieval into `menu_cards`, then render menu images in the chat card UI without changing LLM prompting behavior.

**Architecture:** Keep `imageURL` as metadata only. The backend stores it in menu vector metadata and returns it in structured menu card items; the frontend extends the existing `MenuCard` contract to render an optional image region with graceful fallback behavior.

**Tech Stack:** Python, LangChain/Chroma, FastAPI session/message pipeline, Next.js 16, React 19, TypeScript, ESLint

---

## File Map

- Modify: `vectorstore/build_menu_index.py`
  Add `imageURL` to menu metadata while keeping embedding text unchanged.
- Modify: `tools/search_menu.py`
  Include `imageURL` in retrieval results returned to the agent flow.
- Modify: `tools/final_answer.py`
  Preserve `imageURL` when formatting `menu_cards` payload items.
- Modify: `frontend/src/types/chat.ts`
  Extend `MenuCard` with optional `imageURL`.
- Modify: `frontend/src/lib/api.ts`
  Map backend `imageURL` into frontend card objects.
- Modify: `frontend/src/lib/mockApi.ts`
  Keep mock card data aligned with the new type shape.
- Modify: `frontend/src/components/chat/MenuCard.tsx`
  Render the optional image and handle image load failures safely.
- Modify: `frontend/next.config.ts`
  Allow remote images from the BBQ asset host if `next/image` is used.
- Modify: `docs/API.md`
  Document `imageURL` on `menu_cards.items[]`.
- Create: `tests/test_menu_image_url.py`
  Regression tests for backend metadata propagation and response formatting.

### Task 1: Backend Metadata Contract

**Files:**
- Create: `tests/test_menu_image_url.py`
- Modify: `vectorstore/build_menu_index.py`
- Modify: `tools/search_menu.py`
- Modify: `tools/final_answer.py`

- [ ] **Step 1: Write the failing backend tests**

```python
import json

from tools.final_answer import final_answer_menu
from vectorstore.build_menu_index import build_metadata


def test_build_metadata_includes_image_url():
    metadata = build_metadata({"메뉴명": "뿜치킹", "imageURL": "https://example.com/menu.png"})
    assert metadata["imageURL"] == "https://example.com/menu.png"


def test_final_answer_menu_preserves_image_url():
    payload = json.loads(
        final_answer_menu.invoke(
            {
                "items": [
                    {
                        "name": "뿜치킹",
                        "category": "신메뉴",
                        "price": 25000,
                        "description": "치즈 풍미",
                        "imageURL": "https://example.com/menu.png",
                    }
                ]
            }
        )
    )
    assert payload["items"][0]["imageURL"] == "https://example.com/menu.png"
```

- [ ] **Step 2: Run the backend test file and verify it fails**

Run: `venv\Scripts\python.exe -m unittest tests.test_menu_image_url -v`

Expected: FAIL because `imageURL` is not yet present in metadata and menu card formatting.

- [ ] **Step 3: Implement the minimal backend changes**

```python
# vectorstore/build_menu_index.py
return {
    "price": int(item.get("가격", 0)),
    "category": str(item.get("구분", "")),
    "allergy": str(item.get("알레르기 정보", "")),
    "texture": str(item.get("texture", "")),
    "spiciness": str(item.get("spiciness", "")),
    "origin": str(item.get("원산지", "")),
    "nutrition": str(item.get("영양 정보", "")),
    "options": str(item.get("구매 옵션", "")),
    "name": str(item.get("메뉴명", "")),
    "imageURL": str(item.get("imageURL", "")),
}

# tools/search_menu.py
item = {
    "name": meta.get("name", ""),
    "category": meta.get("category", ""),
    "price": meta.get("price", 0),
    "allergy": meta.get("allergy", ""),
    "texture": meta.get("texture", ""),
    "spiciness": meta.get("spiciness", ""),
    "nutrition": meta.get("nutrition", ""),
    "options": meta.get("options", ""),
    "description": doc.page_content,
    "imageURL": meta.get("imageURL", ""),
}

# tools/final_answer.py
"imageURL": item.get("imageURL", ""),
```

- [ ] **Step 4: Re-run backend tests and verify they pass**

Run: `venv\Scripts\python.exe -m unittest tests.test_menu_image_url -v`

Expected: PASS

- [ ] **Step 5: Rebuild the menu index**

Run: `venv\Scripts\python.exe -m vectorstore.build_menu_index`

Expected: menu documents rebuild successfully with the updated metadata contract.

### Task 2: Frontend Card Contract and Rendering

**Files:**
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/mockApi.ts`
- Modify: `frontend/src/components/chat/MenuCard.tsx`
- Modify: `frontend/next.config.ts`

- [ ] **Step 1: Extend the frontend card type and payload mapping**

```ts
// frontend/src/types/chat.ts
export type MenuCard = {
  name: string;
  price: number;
  description: string;
  category: string;
  allergy?: string;
  nutrition?: string;
  options?: string;
  imageURL?: string;
};

// frontend/src/lib/api.ts
interface BackendMenuItem {
  name: string;
  category: string;
  price: number;
  description: string;
  allergy?: string;
  nutrition?: string;
  options?: string;
  imageURL?: string;
}
```

- [ ] **Step 2: Run lint or build to verify the new type requirement fails before UI changes are complete**

Run: `npm.cmd run build`

Working directory: `frontend`

Expected: FAIL or type-check pressure until the card renderer and mock data are updated to the expanded contract.

- [ ] **Step 3: Implement the image rendering path**

```tsx
const [imageHidden, setImageHidden] = useState(false);
const showImage = Boolean(card.imageURL) && !imageHidden;

{showImage ? (
  <Image
    src={card.imageURL!}
    alt={card.name}
    fill
    className="object-cover"
    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
    onError={() => setImageHidden(true)}
  />
) : (
  <div className="flex h-full items-center justify-center bg-neutral-100 text-xs font-semibold text-neutral-500">
    IMAGE UNAVAILABLE
  </div>
)}
```

- [ ] **Step 4: Allow the BBQ remote asset host and keep mock data aligned**

```ts
// frontend/next.config.ts
images: {
  remotePatterns: [
    {
      protocol: "https",
      hostname: "static.bbqorder.co.kr",
      pathname: "/**",
    },
  ],
},
```

```ts
// frontend/src/lib/mockApi.ts
{
  name: "황금올리브치킨",
  price: 20000,
  description: "...",
  category: "후라이드",
  imageURL: "https://static.bbqorder.co.kr/menu/example.png",
}
```

- [ ] **Step 5: Run lint and build**

Run: `npm.cmd run lint`

Run: `npm.cmd run build`

Working directory: `frontend`

Expected: both commands PASS

### Task 3: Contract Documentation and Final Verification

**Files:**
- Modify: `docs/API.md`

- [ ] **Step 1: Update API examples to show `imageURL` on menu card items**

```json
{
  "type": "menu_cards",
  "items": [
    {
      "name": "뿜치킹",
      "category": "신메뉴",
      "price": 25000,
      "description": "한입 가득 뿜뿜!! ...",
      "imageURL": "https://static.bbqorder.co.kr/menu/..."
    }
  ]
}
```

- [ ] **Step 2: Run the backend test file again**

Run: `venv\Scripts\python.exe -m unittest tests.test_menu_image_url -v`

Expected: PASS

- [ ] **Step 3: Run frontend verification again**

Run: `npm.cmd run lint`

Run: `npm.cmd run build`

Working directory: `frontend`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/API.md docs/superpowers/plans/2026-04-25-menu-image-url.md frontend/next.config.ts frontend/src/components/chat/MenuCard.tsx frontend/src/lib/api.ts frontend/src/lib/mockApi.ts frontend/src/types/chat.ts tests/test_menu_image_url.py tools/final_answer.py tools/search_menu.py vectorstore/build_menu_index.py
git commit -m "feat: deliver menu image URLs to recommendation cards"
```

## Self-Review

- Spec coverage: source metadata, retrieval payload, menu card response, frontend rendering, failure handling, and docs are all covered by tasks above.
- Placeholder scan: no TBD/TODO markers remain; each task includes exact files and commands.
- Type consistency: all tasks use the same property name, `imageURL`, across data, retrieval, API, and frontend layers.
