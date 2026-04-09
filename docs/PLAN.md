# High level steps for project

Part 1: Plan [DONE]

Enrich this document to plan out each of these parts in detail, with substeps listed out as a checklist to be checked off by the agent, and with tests and success critieria for each. Also create an AGENTS.md file inside the frontend directory that describes the existing code there. Ensure the user checks and approves the plan.

Part 2: Scaffolding [DONE]

Set up the Docker infrastructure, the backend in backend/ with FastAPI, and write the start and stop scripts in the scripts/ directory. This should serve example static HTML to confirm that a 'hello world' example works running locally and also make an API call.

- FastAPI backend with /health and /api/hello endpoints
- Dockerfile (python:3.13-slim + uv)
- docker-compose.yml with SQLite volume and healthcheck
- start/stop scripts for Mac/Linux (.sh) and Windows (.bat)

Part 3: Add in Frontend [DONE]

Now update so that the frontend is statically built and served, so that the app has the demo Kanban board displayed at /. Comprehensive unit and integration tests.

- Next.js standalone build, proxied by FastAPI via httpx
- Multi-stage Dockerfile (Node build stage + Python runtime)
- entrypoint.sh runs Next.js then FastAPI
- 9 tests passing (3 backend pytest + 6 frontend Vitest)

Part 4: Add in a fake user sign in experience [DONE]

Now update so that on first hitting /, you need to log in with dummy credentials ("user", "password") in order to see the Kanban, and you can log out. Comprehensive tests.

- Backend: /api/login, /api/logout, /api/me with in-memory session tokens
- Frontend: LoginForm component, auth state in page.tsx, sign out button in KanbanBoard header
- 19 tests passing (8 backend pytest + 11 frontend Vitest)

Part 5: Database modeling [DONE]

Now propose a database schema for the Kanban, saving it as JSON. Document the database approach in docs/ and get user sign off.

- 4 tables: users, boards, columns, cards with integer auto-increment IDs
- Schema in docs/schema.json, approach documented in docs/DATABASE.md
- User approved

Part 6: Backend [DONE]

Now add API routes to allow the backend to read and change the Kanban for a given user; test this thoroughly with backend unit tests. The database should be created if it doesn't exist.

- db.py: SQLite init, seed, CRUD operations
- API routes: GET /api/board, POST/PUT/DELETE /api/cards, POST /api/cards/:id/move, PUT /api/columns/:id
- Auth now creates DB user + default board on first login
- 18 backend tests passing

Part 7: Frontend + Backend [DONE]

Now have the frontend actually use the backend API, so that the app is a proper persistent Kanban board. Test very throughly.

- API client module (lib/api.ts) for all backend calls
- KanbanBoard fetches board from /api/board on mount
- Add/delete/move cards and rename columns call the API with optimistic local updates
- Data persists across container restarts (verified)
- 29 tests passing (18 backend pytest + 11 frontend Vitest)

Part 8: AI connectivity [DONE]

Now allow the backend to make an AI call via OpenRouter. Test connectivity with a simple "2+2" test and ensure the AI call is working.

- ai.py: OpenRouter client using httpx, model openai/gpt-oss-120b:free
- POST /api/ai/test endpoint sends "What is 2+2?" and returns the answer
- Verified in Docker: AI returned "4"
- 20 backend tests passing (AI tests use mock)

Part 9: AI chat with structured outputs [DONE]

Now extend the backend call so that it always calls the AI with the JSON of the Kanban board, plus the user's question (and conversation history). The AI should respond with Structured Outputs that includes the response to the user and optionaly an update to the Kanban. Test thoroughly.

- ai.py: chat_with_board() sends system prompt with board JSON + conversation history
- Structured output: {"message": str, "actions": [{type, ...}]} with JSON response_format
- Actions supported: create_card, update_card, delete_card, move_card
- POST /api/ai/chat applies actions to DB and returns updated board
- Verified in Docker: AI correctly created a card via structured output
- 24 backend tests passing (4 AI chat tests use mocks)

Part 10: AI chat sidebar [DONE]

Now add a beautiful sidebar widget to the UI supporting full AI chat, and allowing the LLM (as it determines) to update the Kanban based on its Structured Outputs. If the AI updates the Kanban, then the UI should refresh automatically.

- ChatSidebar component: slide-out panel with message bubbles, input, loading state
- Purple floating button in bottom-right to toggle open/closed
- Sends full conversation history to /api/ai/chat
- When AI returns actions, board state refreshes automatically via onBoardUpdate callback
- 39 tests passing (24 backend pytest + 15 frontend Vitest)