# Code Review Report

Comprehensive review of the ed_pm repository. Findings are grouped by area, ordered by severity within each section. Each item includes an action.

---

## 1. Backend Security

### 1.1 No resource ownership checks (HIGH)

Card and column endpoints verify authentication but not that the resource belongs to the user's board. Any authenticated user can modify any card/column if they know the ID.

**Files:** `backend/main.py:102-158`, `backend/db.py:124-197`

**Example:** `api_delete_card` checks session but passes `card_id` straight to `delete_card()` without verifying the card belongs to `s["board_id"]`.

**Action:** Add a `board_id` parameter to `add_card`, `update_card`, `delete_card`, `move_card`, and `rename_column` in `db.py`. Each function should JOIN against columns/boards to verify ownership before mutating. Update `main.py` endpoints to pass `s["board_id"]`.

### 1.2 Sessions never expire (MEDIUM)

`sessions` dict in `main.py:25` grows unbounded. Tokens persist until server restart.

**Action:** Store a `created_at` timestamp per session. Add a check in `_get_session` that rejects tokens older than a threshold (e.g. 24h). Optionally sweep expired entries periodically.

### 1.3 No request body validation (MEDIUM)

Endpoints use `await request.json()` and directly index keys like `body["columnId"]` (`main.py:108`). Malformed JSON or missing keys cause unhandled 500 errors.

**Action:** Define Pydantic `BaseModel` classes for each request body. FastAPI will return 422 with a clear message on invalid input.

### 1.4 AI action schema not validated (MEDIUM)

`_apply_actions` (`main.py:173-196`) trusts the AI response structure. A malformed action (missing `columnId`, wrong `type`) will crash.

**Action:** Validate each action dict against expected keys before applying. Skip or log invalid actions and include a warning in the response message.

### 1.5 API key not validated at startup (LOW)

`ai.py:60,82` reads `OPENROUTER_API_KEY` per request and silently uses an empty string if unset.

**Action:** Check for the key in the `lifespan` function. Log a warning at startup if missing. Return 503 from AI endpoints if not configured.

---

## 2. Backend Bugs and Logic

### 2.1 move_card position race with same-column moves (MEDIUM)

`db.py:161-187` decrements positions in the source column, then increments in the target column. When source and target are the same column, both UPDATEs hit the same rows and can produce duplicate or gapped positions.

**Action:** Handle same-column reorder as a distinct code path: remove from old position, shift affected cards, insert at new position, all within one transaction.

### 2.2 No explicit transactions in db.py (MEDIUM)

Each `db.py` function opens its own connection and relies on implicit autocommit between statements. Multi-statement operations like `move_card` and `ensure_user_board` can leave partial state if an error occurs mid-way.

**Action:** Wrap multi-statement functions in explicit `with conn:` context manager blocks (SQLite transaction).

### 2.3 New connection per call (LOW)

`get_conn()` opens a fresh SQLite connection on every function call. This works for an MVP but creates unnecessary overhead.

**Action:** Consider a module-level connection with thread-local storage, or pass connections from the caller.

### 2.4 Proxy creates a new httpx client per request (LOW)

`main.py:219` instantiates `httpx.AsyncClient` inside every proxy call.

**Action:** Create a single `AsyncClient` instance during `lifespan` startup and reuse it. Close it on shutdown.

---

## 3. Frontend Bugs and Logic

### 3.1 Potential undefined cards in KanbanColumn (MEDIUM)

`KanbanBoard.tsx:202` maps `column.cardIds` through `board.cards`:

```tsx
cards={column.cardIds.map((cardId) => board.cards[cardId])}
```

If a card ID exists in `cardIds` but is missing from `board.cards` (stale data, AI action deleted a card mid-render), `undefined` is passed to `KanbanCard`, which will crash when accessing `card.id`.

**Action:** Filter out undefined entries: `column.cardIds.map(id => board.cards[id]).filter(Boolean)`.

### 3.2 Stale closure in ChatSidebar concurrent sends (MEDIUM)

`ChatSidebar.tsx:28-37` captures `messages` via `updatedMessages` in a closure. If the user sends a second message before the first API call resolves, the second `setMessages` overwrites the first response.

**Action:** Use the callback form of `setMessages` when appending the assistant response: `setMessages(prev => [...prev, assistantMsg])`. Gate the send button on `loading` (already done) or use a ref for the latest messages.

### 3.3 addCard has no error handling (MEDIUM)

`KanbanBoard.tsx:96-111` awaits `api.addCard` but has no try/catch. A failed API call throws an unhandled promise rejection.

**Action:** Wrap in try/catch. On failure, call `reload()` to resync state, matching the pattern used by `moveCard` and `deleteCard`.

### 3.4 No rollback on failed optimistic updates (LOW)

`handleDeleteCard` and `handleDragEnd` optimistically update the board, then call the API with `.catch(reload)`. If the network is slow, the user sees stale state until `reload` completes. This is acceptable for the MVP but worth noting.

**Action:** No immediate change needed. Document as a known limitation. For a future improvement, snapshot previous state and restore on error before reloading.

### 3.5 Chat messages keyed by array index (LOW)

`ChatSidebar.tsx:95` uses `key={i}`. Since messages are append-only and never reordered this works, but it is fragile.

**Action:** Generate a stable ID per message (e.g. `crypto.randomUUID()` or a counter) and use that as the key.

### 3.6 Ineffective useMemo (LOW)

`KanbanBoard.tsx:54`:

```tsx
const cardsById = useMemo(() => board.cards, [board.cards]);
```

`board.cards` is a new object reference on every state update, so this memo never caches. It is also only used once (`activeCard` lookup on line 129).

**Action:** Remove the `useMemo`. Use `board.cards[activeCardId]` directly.

---

## 4. Frontend Error Handling

### 4.1 page.tsx treats all /api/me failures as "not logged in" (LOW)

`page.tsx:12-14` converts any non-ok response (including 500) to `null` user, sending the user to the login form instead of showing an error.

**Action:** Distinguish 401 (show login) from 5xx (show "server unavailable" message).

### 4.2 ChatSidebar generic error message (LOW)

`ChatSidebar.tsx:41-43` shows "Sorry, something went wrong" for all errors. No distinction between network failure and AI error.

**Action:** Inspect the error. Show "Network error" vs "AI service unavailable" as appropriate.

---

## 5. Type Safety

### 5.1 AI actions typed as `Record<string, unknown>[]` (MEDIUM)

`api.ts:10`:

```tsx
actions: Array<Record<string, unknown>>;
```

This loses all type information about action shapes, pushing validation to runtime.

**Action:** Define a discriminated union type for actions:

```tsx
type CreateCardAction = { type: "create_card"; columnId: string; title: string; details?: string };
type UpdateCardAction = { type: "update_card"; cardId: string; title: string; details?: string };
type DeleteCardAction = { type: "delete_card"; cardId: string };
type MoveCardAction   = { type: "move_card"; cardId: string; columnId: string; position: number };
type BoardAction = CreateCardAction | UpdateCardAction | DeleteCardAction | MoveCardAction;
```

### 5.2 _parse_id has no error handling (LOW)

`main.py:41-43` calls `int()` on user-supplied input. A malformed ID like `card-abc` will raise `ValueError` and return a 500.

**Action:** Wrap in try/except and return 400 on invalid IDs.

---

## 6. Docker and Infrastructure

### 6.1 uv image tag is `latest` (MEDIUM)

`Dockerfile:14`:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
```

Builds are non-reproducible. A breaking uv update will silently break the image.

**Action:** Pin to a specific version, e.g. `ghcr.io/astral-sh/uv:0.6.14`.

### 6.2 entrypoint.sh does not fail if frontend never starts (MEDIUM)

`scripts/entrypoint.sh:9-14` loops 30 times but always falls through to start FastAPI, even if Next.js never became ready. The proxy will return 502 on every page load with no log explaining why.

**Action:** After the loop, check if curl succeeded. If not, log an error and exit 1.

### 6.3 Container runs as root (LOW)

The Dockerfile does not create or switch to a non-root user.

**Action:** Add before CMD:

```dockerfile
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
```

### 6.4 No .dockerignore (LOW)

Build context includes `.git`, `node_modules`, `__pycache__`, `.venv`, and test files.

**Action:** Create `.dockerignore` excluding `.git`, `**/__pycache__`, `**/.pytest_cache`, `backend/.venv`, `frontend/node_modules`, `frontend/.next`.

### 6.5 No process monitoring in entrypoint (LOW)

Next.js runs in the background (`&`) with no supervision. If it crashes, FastAPI keeps running but the proxy returns 502.

**Action:** For a future improvement, use a process manager or add a background health check loop that exits the container if the frontend process dies.

---

## 7. Test Coverage Gaps

### 7.1 No authorization/ownership tests (HIGH)

Backend tests verify auth (logged in vs not) but never test that user A cannot access user B's resources. This is the counterpart to finding 1.1.

**Action:** Add tests with two users. Verify that user A cannot read, update, delete, or move user B's cards.

### 7.2 No malformed input tests (MEDIUM)

No tests for: missing required fields, invalid JSON, non-numeric card IDs, empty strings.

**Action:** Add negative-path tests for each endpoint with bad input.

### 7.3 No error-state tests in frontend (MEDIUM)

Frontend tests mock all API calls to succeed. No tests verify behavior when API returns errors or network fails.

**Action:** Add tests where mocked API calls reject. Verify error messages are displayed and state remains consistent.

### 7.4 No AI action validation tests (LOW)

Backend tests mock `chat_with_board` so AI response parsing and action validation are never exercised.

**Action:** Add tests that call `/api/ai/chat` with mocked responses containing malformed actions. Verify graceful handling.

---

## 8. Accessibility

### 8.1 No keyboard alternative for drag-and-drop (MEDIUM)

Cards can only be reordered via pointer drag. Keyboard-only users cannot move cards between columns.

**Action:** Add @dnd-kit `KeyboardSensor` alongside `PointerSensor`, or provide button-based move controls as an alternative.

### 8.2 Chat sidebar does not trap or move focus on open (LOW)

When the sidebar opens, focus stays wherever it was. Users must tab through the page to reach the chat input.

**Action:** Auto-focus the chat input when the sidebar opens using a ref with `useEffect`.

---

## Summary

| Area | High | Medium | Low | Total |
|------|------|--------|-----|-------|
| Backend Security | 1 | 3 | 1 | 5 |
| Backend Bugs/Logic | 0 | 2 | 2 | 4 |
| Frontend Bugs/Logic | 0 | 3 | 3 | 6 |
| Frontend Error Handling | 0 | 0 | 2 | 2 |
| Type Safety | 0 | 1 | 1 | 2 |
| Docker/Infra | 0 | 2 | 3 | 5 |
| Test Coverage | 1 | 2 | 1 | 4 |
| Accessibility | 0 | 1 | 1 | 2 |
| **Total** | **2** | **14** | **14** | **30** |

### Suggested priority order

1. **1.1** Resource ownership checks -- security prerequisite for multi-user
2. **7.1** Authorization tests -- validates the fix for 1.1
3. **1.3** Pydantic request validation -- prevents 500s from bad input
4. **1.4** AI action validation -- prevents crashes from malformed AI responses
5. **3.1** Filter undefined cards -- prevents runtime crashes
6. **3.3** addCard error handling -- prevents unhandled rejections
7. **2.1** move_card same-column fix -- data integrity
8. **2.2** Explicit transactions -- data integrity
9. **6.1** Pin uv Docker image -- build reproducibility
10. **6.2** Entrypoint failure handling -- deployment reliability
