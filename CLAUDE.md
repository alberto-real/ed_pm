# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack Kanban board PM app: Next.js 16 (React 19) frontend + Python FastAPI backend, packaged in Docker. AI chat sidebar uses OpenRouter to create/edit/move cards via structured JSON outputs.

## Commands

### Frontend (run from `frontend/`)
- `npm run dev` — dev server on :3000
- `npm run build` — production build
- `npm run lint` — ESLint
- `npm run test:unit` — Vitest unit tests
- `npm run test:unit:watch` — Vitest watch mode
- `npm run test:e2e` — Playwright E2E tests (needs dev server running)
- `npm run test:all` — unit + E2E

### Backend (run from `backend/`)
- `uv run uvicorn main:app --reload --port 8000` — dev server
- `uv run pytest` — 24 backend tests
- `uv run pytest test_main.py::test_name -v` — single test

### Docker
- `./scripts/start.sh` / `./scripts/stop.sh` — start/stop (Linux/Mac)
- `scripts/start.bat` / `scripts/stop.bat` — Windows

## Architecture

**Backend** (FastAPI, 3 files in `backend/`):
- `main.py` — API routes, auth (HTTPOnly cookie sessions), proxies unknown routes to Next.js frontend
- `db.py` — Raw SQLite (no ORM), schema init, CRUD, seed data on first login
- `ai.py` — OpenRouter httpx client, structured JSON output with board context

**Frontend** (Next.js App Router, `frontend/src/`):
- `app/page.tsx` — auth gate: LoginForm or KanbanBoard
- `components/KanbanBoard.tsx` — main board with @dnd-kit drag-and-drop
- `components/ChatSidebar.tsx` — AI chat that returns structured actions (create/edit/move/delete cards)
- `lib/api.ts` — fetch-based API client for all backend endpoints
- `lib/kanban.ts` — board state utilities (apply AI actions, reorder)

**Database** (SQLite): users → boards → columns → cards (1:many chain). Integer IDs internally, string-prefixed in API (`col-1`, `card-42`).

**AI flow**: ChatSidebar → POST /api/ai/chat (sends message + full board JSON) → OpenRouter returns `{message, actions[]}` → frontend applies actions to board state.

## Key Conventions

- Color scheme: Yellow `#ecad0a`, Blue `#209dd7`, Purple `#753991`, Navy `#032147`, Gray `#888888`
- Auth: hardcoded user/password for MVP, session tokens stored in-memory dict
- OpenRouter model: `openai/gpt-oss-120b:free`, API key in `.env` (OPENROUTER_API_KEY)
- Python package manager: uv (not pip)
- Planning docs in `docs/` — review `docs/PLAN.md` before major work
- No emojis in code or docs
- Keep it simple: no over-engineering, no unnecessary defensive programming
