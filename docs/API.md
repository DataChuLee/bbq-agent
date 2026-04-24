# BBQ API Design

## Status

- Scope: API design only
- Storage: in-memory sessions for now
- Future expansion: persistent sessions/messages plus personalization
- Primary portfolio goal: show that the BBQ project models an AI workflow as a backend service, not just as a prompt demo

## Goals

1. Expose the BBQ chatbot through a clean session-based API.
2. Separate resource-oriented endpoints from AI action endpoints.
3. Keep the current in-memory implementation simple while preserving a migration path to a database.
4. Make Menu and CS knowledge retrieval visible in the design without letting internal data management dominate the public API.
5. Preserve streaming as the primary user experience for the web client.

## Non-Goals

- Full CRUD administration for every menu or CS record
- Authentication and authorization
- Persistent storage in the current milestone
- Personalization logic in the current milestone

## System Layers

### Knowledge Layer

- BBQ Menu data
- BBQ CS data
- Vector indexes and retrieval utilities
- Internal knowledge management endpoints

This layer answers: what can the system know?

### Interaction Layer

- Sessions
- Messages
- Response generation
- Streaming events

This layer answers: how does the user interact with the system?

### Personalization Layer

- Stored user conversation history
- Preference extraction
- Personalized ranking or recommendation logic

This layer is intentionally out of scope for the current implementation, but the Interaction Layer is designed so it can be added later without changing the public API shape.

## API Design Principles

### 1. Resources vs actions

- `sessions` and `messages` are resources because they are identifiable records.
- `responses` are action endpoints because generating an answer is a workflow, not simple CRUD.

### 2. Streaming-first UX

- The web application should use streaming as the default path.
- Synchronous response generation is retained as a secondary path for testing, debugging, and simple clients.

### 3. Thin routes

- Route handlers validate requests, call services, and format responses.
- Business logic lives in dedicated services.

### 4. Stable contracts

- API contracts should stay stable even when storage moves from memory to a database.
- Sync and stream endpoints should share the same final assistant message shape.

## Public Runtime API

These endpoints are consumed by the web client.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/sessions` | Create a new chat session |
| `GET` | `/sessions/{id}` | Get session metadata |
| `GET` | `/sessions/{id}/messages` | Get message history |
| `POST` | `/sessions/{id}/messages` | Add a user message |
| `DELETE` | `/sessions/{id}` | Clear or delete a session |
| `POST` | `/sessions/{id}/responses` | Generate a full assistant response |
| `POST` | `/sessions/{id}/responses/stream` | Generate a streaming assistant response over SSE |
| `GET` | `/health` | Health check |

## Internal Knowledge API

These endpoints support knowledge inspection and operations. They are internal-facing and exist to make the RAG system observable and testable.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/knowledge/status` | Inspect knowledge/index readiness |
| `GET` | `/knowledge/documents` | List known knowledge documents or logical records |
| `GET` | `/knowledge/documents/{id}` | Inspect a single knowledge document |
| `POST` | `/knowledge/indexes/rebuild` | Rebuild indexes after data changes |
| `POST` | `/knowledge/retrieval/search-preview` | Preview retrieval results without full answer generation |

## Core Data Models

### Session

```json
{
  "id": "sess_123",
  "status": "active",
  "storage": "memory",
  "created_at": "2026-04-24T10:00:00Z",
  "message_count": 2
}
```

### Message

```json
{
  "id": "msg_123",
  "role": "user",
  "type": "text",
  "content": "Recommend a spicy chicken menu",
  "created_at": "2026-04-24T10:00:05Z"
}
```

Message types for the current design:

- `text`
- `menu_cards`
- `clarification`

The client creates only user messages. Assistant messages are created by the server after response generation.
In the current milestone, `POST /sessions/{id}/messages` accepts only `type: "text"` from the client.

### Assistant response result

```json
{
  "response_id": "resp_123",
  "intent": "menu",
  "message": {
    "id": "msg_124",
    "role": "assistant",
    "type": "menu_cards",
    "content": null,
    "items": [],
    "created_at": "2026-04-24T10:00:08Z"
  },
  "sources": [
    {
      "source_type": "menu",
      "source_id": "menu_17"
    }
  ]
}
```

## Response Contract

### Success shape

```json
{
  "data": {}
}
```

### Error shape

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session not found",
    "details": null,
    "trace_id": "req_123"
  }
}
```

## Endpoint Details

### `POST /sessions`

Create a new session.

Example response:

```json
{
  "data": {
    "id": "sess_123",
    "status": "active",
    "storage": "memory",
    "created_at": "2026-04-24T10:00:00Z",
    "message_count": 0
  }
}
```

### `GET /sessions/{id}`

Return session metadata only, not the full history.

### `GET /sessions/{id}/messages`

Return the message history for the session.

Example response:

```json
{
  "data": [
    {
      "id": "msg_1",
      "role": "user",
      "type": "text",
      "content": "Recommend a spicy chicken menu",
      "created_at": "2026-04-24T10:00:00Z"
    },
    {
      "id": "msg_2",
      "role": "assistant",
      "type": "menu_cards",
      "content": null,
      "items": [],
      "created_at": "2026-04-24T10:00:03Z"
    }
  ]
}
```

### `POST /sessions/{id}/messages`

Append a user message to an existing session.

Validation rule for the current milestone:

- only `type: "text"` is accepted from the client
- `role` is not client-controlled
- empty `content` is rejected

Example request:

```json
{
  "type": "text",
  "content": "Recommend a spicy chicken menu"
}
```

Example response:

```json
{
  "data": {
    "id": "msg_3",
    "role": "user",
    "type": "text",
    "content": "Recommend a spicy chicken menu",
    "created_at": "2026-04-24T10:02:00Z"
  }
}
```

### `DELETE /sessions/{id}`

Remove the session from the current storage backend. In the current milestone this means removing it from memory.

### `POST /sessions/{id}/responses`

Generate a non-streaming assistant response from the current session state.

This endpoint is secondary. It exists for:

- integration tests
- Postman/manual checks
- environments that do not support SSE

Source message resolution rule:

- if `source_message_id` is provided, it must belong to the session
- if `source_message_id` is omitted, the service uses the latest user message in the session
- the endpoint does not create a user message by itself

Example request:

```json
{
  "source_message_id": "msg_3"
}
```

Example response:

```json
{
  "data": {
    "response_id": "resp_1",
    "intent": "menu",
    "message": {
      "id": "msg_4",
      "role": "assistant",
      "type": "menu_cards",
      "content": null,
      "items": [],
      "created_at": "2026-04-24T10:02:03Z"
    },
    "sources": [
      {
        "source_type": "menu",
        "source_id": "menu_17"
      }
    ]
  }
}
```

### `POST /sessions/{id}/responses/stream`

Generate a streaming assistant response over SSE.

This is the primary UX endpoint for the web client.

Recommended event sequence:

1. `start`
2. `token`
3. repeated `token`
4. `message`
5. `done`

Example final `message` event:

```json
{
  "message": {
    "id": "msg_4",
    "role": "assistant",
    "type": "text",
    "content": "The recommended menu is ...",
    "created_at": "2026-04-24T10:02:03Z"
  }
}
```

The final assistant message schema should match the synchronous endpoint.

### `GET /health`

Return service health.

Example response:

```json
{
  "data": {
    "status": "ok"
  }
}
```

## Knowledge API Details

### `GET /knowledge/status`

Return a small operational summary of the knowledge layer.

```json
{
  "data": {
    "menu_documents": 120,
    "cs_documents": 85,
    "vector_index_status": "ready",
    "last_rebuilt_at": "2026-04-24T09:30:00Z"
  }
}
```

### `GET /knowledge/documents`

List logical knowledge records. This is intentionally read-oriented for the current scope because the current milestone imports Menu and CS knowledge from local source data rather than managing those records through public CRUD endpoints.

### `GET /knowledge/documents/{id}`

Inspect one logical record used by the knowledge layer.

### `POST /knowledge/indexes/rebuild`

Trigger re-indexing after source data changes.

### `POST /knowledge/retrieval/search-preview`

Run retrieval only and return retrieved chunks or records without performing answer generation. This is useful for debugging RAG quality.

## Service Boundaries

### API Layer

- Request validation
- Response formatting
- HTTP status handling

### Session Service

- Create session
- Get session metadata
- Delete session

### Message Service

- Add user message
- Read message history
- Persist assistant message into the session store

### Response Service

- Load current session state
- Resolve source message
- Call retrieval and generation
- Return a normalized assistant message result

### Knowledge Service

- Expose knowledge status
- Preview retrieval behavior
- Trigger index rebuilds

### Agent/Graph Layer

- Intent routing
- Tool orchestration
- Final answer generation

This layer contains LangGraph-specific logic. The public API should not depend on LangGraph concepts directly.

### Streaming Adapter

- Convert response generation output to SSE events
- Ensure the final message is persisted after stream completion

## Request Flow

### User message flow

1. Client calls `POST /sessions/{id}/messages`.
2. API Layer validates the request.
3. Session Service confirms the session exists.
4. Message Service stores the user message.
5. API returns the created user message.

### Streaming response flow

1. Client calls `POST /sessions/{id}/responses/stream`.
2. API Layer validates the request.
3. Response Service loads session context.
4. Knowledge Service and Agent/Graph Layer perform retrieval and generation.
5. Streaming Adapter emits SSE events.
6. Message Service stores the final assistant message.
7. Stream closes with a final `done` event.

## Error Handling Strategy

### Request errors

Use `4xx` for client-side issues:

- session not found
- empty content
- unsupported message type
- malformed request body

### System errors

Use `5xx` for system failures:

- LLM call failure
- vector index loading failure
- unexpected stream exception

### Business fallbacks are not server errors

The following should return normal assistant responses, not `500` errors:

- no retrieval results
- ambiguous intent
- overly restrictive user filters

In those cases the assistant should produce either:

- a clarification message
- a fallback text response
- a suggestion to relax search conditions

### Traceability

Every error response should include a `trace_id` so logs and debugging artifacts can be correlated.

## Testing Strategy

### API contract tests

Verify:

- status codes
- response shapes
- error payload shapes
- SSE event ordering

### Service unit tests

Test:

- Session Service
- Message Service
- Response Service

These tests should not rely on HTTP.

### RAG smoke tests

Verify:

- menu questions retrieve menu knowledge
- CS questions retrieve CS knowledge
- empty retrieval results trigger a fallback path instead of a server crash

### Streaming tests

Verify:

- event ordering is stable
- stream completion persists the assistant message
- sync and stream produce the same final message shape

## Future Expansion Plan

### Persistence

Replace in-memory repositories with database-backed repositories while keeping the API shape stable.

### Personalization

Add:

- stored conversation history
- preference extraction
- recommendation ranking based on prior interactions

### Operations

Add:

- authentication
- usage logging
- evaluation logging
- retry and rate-limit policies

## Why This Design Fits the Portfolio Goal

This design intentionally demonstrates that the BBQ project is more than a simple prompt wrapper.

It shows:

- a resource model for sessions and messages
- action endpoints for AI generation
- separation between knowledge retrieval and interaction state
- streaming-first AI UX
- service boundaries that support future persistence and personalization

The result is a backend design that fits an AI Engineering portfolio: practical, explainable, and extensible.
