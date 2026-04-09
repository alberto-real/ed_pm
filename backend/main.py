import secrets
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import Cookie, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

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
SESSION_TTL = 86400  # 24 hours

# In-memory session store (maps token -> {username, user_id, board_id, created_at})
sessions: dict[str, dict] = {}


# --- Request models ---


class LoginRequest(BaseModel):
    username: str
    password: str


class AddCardRequest(BaseModel):
    columnId: str
    title: str
    details: str = ""


class UpdateCardRequest(BaseModel):
    title: str
    details: str = ""


class MoveCardRequest(BaseModel):
    columnId: str
    position: int


class RenameColumnRequest(BaseModel):
    title: str


class AiChatRequest(BaseModel):
    messages: list[dict]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


def _get_session(session: str) -> dict | None:
    s = sessions.get(session)
    if not s:
        return None
    if time.time() - s["created_at"] > SESSION_TTL:
        sessions.pop(session, None)
        return None
    return s


def _parse_id(prefixed_id: str) -> int:
    """Strip 'col-' or 'card-' prefix and return the integer ID."""
    return int(prefixed_id.split("-", 1)[-1])


# --- Health ---


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Auth ---


@app.post("/api/login")
def login(body: LoginRequest):
    if body.username != VALID_USERNAME or body.password != VALID_PASSWORD:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    user_id, board_id = ensure_user_board(body.username)
    token = secrets.token_hex(16)
    sessions[token] = {
        "username": body.username,
        "user_id": user_id,
        "board_id": board_id,
        "created_at": time.time(),
    }
    resp = JSONResponse({"username": body.username})
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
def api_add_card(body: AddCardRequest, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    card = add_card(s["board_id"], _parse_id(body.columnId), body.title, body.details)
    if not card:
        return JSONResponse({"error": "Column not found"}, status_code=404)
    return card


@app.put("/api/cards/{card_id}")
def api_update_card(card_id: str, body: UpdateCardRequest, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if not update_card(s["board_id"], _parse_id(card_id), body.title, body.details):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


@app.delete("/api/cards/{card_id}")
def api_delete_card(card_id: str, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if not delete_card(s["board_id"], _parse_id(card_id)):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/cards/{card_id}/move")
def api_move_card(card_id: str, body: MoveCardRequest, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if not move_card(s["board_id"], _parse_id(card_id), _parse_id(body.columnId), body.position):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


# --- Columns ---


@app.put("/api/columns/{column_id}")
def api_rename_column(column_id: str, body: RenameColumnRequest, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if not rename_column(s["board_id"], _parse_id(column_id), body.title):
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


REQUIRED_ACTION_FIELDS = {
    "create_card": ("columnId", "title"),
    "update_card": ("cardId", "title"),
    "delete_card": ("cardId",),
    "move_card": ("cardId", "columnId"),
}


def _apply_actions(actions: list[dict], board_id: int) -> list[str]:
    """Apply AI-generated actions to the database. Returns list of warnings."""
    warnings: list[str] = []
    for action in actions:
        action_type = action.get("type")
        required = REQUIRED_ACTION_FIELDS.get(action_type)
        if required is None:
            warnings.append(f"Skipped unknown action type: {action_type}")
            continue
        missing = [f for f in required if f not in action]
        if missing:
            warnings.append(f"Skipped {action_type}: missing {', '.join(missing)}")
            continue
        try:
            if action_type == "create_card":
                add_card(board_id, _parse_id(action["columnId"]), action["title"], action.get("details", ""))
            elif action_type == "update_card":
                update_card(board_id, _parse_id(action["cardId"]), action["title"], action.get("details", ""))
            elif action_type == "delete_card":
                delete_card(board_id, _parse_id(action["cardId"]))
            elif action_type == "move_card":
                move_card(
                    board_id,
                    _parse_id(action["cardId"]),
                    _parse_id(action["columnId"]),
                    action.get("position", 0),
                )
        except (ValueError, KeyError) as e:
            warnings.append(f"Skipped {action_type}: {e}")
    return warnings


@app.post("/api/ai/chat")
async def api_ai_chat(body: AiChatRequest, session: str = Cookie(default="")):
    s = _get_session(session)
    if not s:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    board = get_board(s["board_id"])
    result = await chat_with_board(board, body.messages)
    if result["actions"]:
        _apply_actions(result["actions"], s["board_id"])
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
