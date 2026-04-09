import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import Cookie, FastAPI, Request
from fastapi.responses import JSONResponse, Response

from ai import chat as ai_chat, chat_with_board
from db import (
    add_card,
    delete_card,
    ensure_user_board,
    get_board,
    init_db,
    move_card,
    rename_column,
    update_card,
)

NEXTJS_URL = "http://127.0.0.1:3000"
VALID_USERNAME = "user"
VALID_PASSWORD = "password"

# In-memory session store (maps token -> {username, user_id, board_id})
sessions: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


def _get_session(session: str) -> dict | None:
    return sessions.get(session)


def _parse_id(prefixed_id: str) -> int:
    """Strip 'col-' or 'card-' prefix and return the integer ID."""
    return int(prefixed_id.split("-", 1)[-1])


# --- Health ---


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Auth ---


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    if username != VALID_USERNAME or password != VALID_PASSWORD:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    user_id, board_id = ensure_user_board(username)
    token = secrets.token_hex(16)
    sessions[token] = {"username": username, "user_id": user_id, "board_id": board_id}
    resp = JSONResponse({"username": username})
    resp.set_cookie("session", token, httponly=True, samesite="lax")
    return resp


@app.post("/api/logout")
def logout(session: str = Cookie(default="")):
    sessions.pop(session, None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp


@app.get("/api/me")
def me(session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return {"username": s["username"]}


# --- Board ---


@app.get("/api/board")
def api_get_board(session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return get_board(s["board_id"])


# --- Cards ---


@app.post("/api/cards")
async def api_add_card(request: Request, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    column_id = _parse_id(body["columnId"])
    card = add_card(column_id, body["title"], body.get("details", ""))
    return card


@app.put("/api/cards/{card_id}")
async def api_update_card(card_id: str, request: Request, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    if not update_card(_parse_id(card_id), body["title"], body.get("details", "")):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


@app.delete("/api/cards/{card_id}")
def api_delete_card(card_id: str, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if not delete_card(_parse_id(card_id)):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/cards/{card_id}/move")
async def api_move_card(card_id: str, request: Request, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    target_column_id = _parse_id(body["columnId"])
    position = int(body["position"])
    if not move_card(_parse_id(card_id), target_column_id, position):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


# --- Columns ---


@app.put("/api/columns/{column_id}")
async def api_rename_column(column_id: str, request: Request, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    if not rename_column(_parse_id(column_id), body["title"]):
        return JSONResponse({"error": "Column not found"}, status_code=404)
    return {"ok": True}


# --- AI ---


@app.post("/api/ai/test")
async def api_ai_test(session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    answer = await ai_chat([{"role": "user", "content": "What is 2+2? Reply with just the number."}])
    return {"answer": answer}


def _apply_actions(actions: list[dict]):
    """Apply AI-generated actions to the database."""
    for action in actions:
        action_type = action.get("type")
        if action_type == "create_card":
            add_card(
                _parse_id(action["columnId"]),
                action["title"],
                action.get("details", ""),
            )
        elif action_type == "update_card":
            update_card(
                _parse_id(action["cardId"]),
                action["title"],
                action.get("details", ""),
            )
        elif action_type == "delete_card":
            delete_card(_parse_id(action["cardId"]))
        elif action_type == "move_card":
            move_card(
                _parse_id(action["cardId"]),
                _parse_id(action["columnId"]),
                action.get("position", 0),
            )


@app.post("/api/ai/chat")
async def api_ai_chat(request: Request, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    conversation = body.get("messages", [])
    board = get_board(s["board_id"])
    result = await chat_with_board(board, conversation)
    if result["actions"]:
        _apply_actions(result["actions"])
        board = get_board(s["board_id"])
    return {"message": result["message"], "actions": result["actions"], "board": board}


# --- Proxy to Next.js ---


async def _proxy(request: Request, path: str = ""):
    try:
        async with httpx.AsyncClient(base_url=NEXTJS_URL) as client:
            headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
            resp = await client.request(
                method=request.method,
                url=f"/{path}",
                headers=headers,
                content=await request.body(),
                params=request.query_params,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type"),
            )
    except httpx.ConnectError:
        return Response(content="Frontend unavailable", status_code=502)


@app.get("/")
async def proxy_root(request: Request):
    return await _proxy(request)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_catchall(request: Request, path: str):
    return await _proxy(request, path)
