---
name: Frontend Architecture — BBQ Agent Chat UI
description: Component structure, API layer design, and rendering conventions for the BBQ Agent frontend chat interface
type: project
---

The frontend is a full-screen chat UI built with Next.js 16.2.1 (App Router), React 19, TypeScript, and Tailwind CSS v4.

**Component tree:**
- `page.tsx` (Server Component) renders `ChatContainer` (Client Component boundary)
- `ChatContainer` owns all message state and error handling; passes down to `MessageList` and `InputBar`
- `MessageList` auto-scrolls on new messages; renders `MessageBubble` for text/clarification, `MenuCardList` for menu_cards
- `MenuCardList` renders a responsive grid of `MenuCard` components

**API layer:**
- `src/lib/api.ts` — `sendMessage(query)` is the single entry point; currently delegates to mockApi
- `src/lib/mockApi.ts` — keyword-based mock with 500ms delay; menu/CS/clarification branches
- To switch to real backend: edit only `api.ts`, replace mock call with `fetch("POST /api/chat")`

**Type system:**
- `src/types/chat.ts` — `Message` union: `TextMessage | MenuCardsMessage | ClarificationMessage`
- Backend must return responses matching this shape

**Design tokens:**
- Brand colors: `orange-500` to `red-500` gradient for user messages and accents
- User messages: right-aligned, gradient background
- Assistant messages: left-aligned, white/gray background
- Clarification: orange-tinted bubble with label

**Why:** Backend API (FastAPI/LangGraph) is not yet connected; mock layer isolates frontend dev from backend readiness.
**How to apply:** When integrating real API, only `src/lib/api.ts` needs editing. Response shape must match `Message` union type in `src/types/chat.ts`.
