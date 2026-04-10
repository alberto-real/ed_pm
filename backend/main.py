import secrets
import time
from contextlib import asynccontextmanager

import bcrypt
import httpx
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator

from ai import chat_with_board
from db import (
    add_card,
    add_label_to_card,
    create_board,
    create_label,
    create_user,
    delete_board,
    delete_card,
    delete_label,
    ensure_user_board,
    get_board,
    get_labels,
    get_user_boards,
    get_user_by_username,
    init_db,
    migrate_db,
    move_card,
    remove_label_from_card,
    rename_board,
    rename_column,
    update_card,
    update_label,
)
from db import _owns_board

NEXTJS_URL = "http://127.0.0.1:3000"
SESSION_TTL = 86400  # 24 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# In-memory session store (maps token -> {username, user_id, created_at})
sessions: dict[str, dict] = {}

_proxy_client: httpx.AsyncClient | None = None


# --- Request models ---


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 30:
            raise ValueError("Username must be 3-30 characters")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateBoardRequest(BaseModel):
    title: str


class RenameBoardRequest(BaseModel):
    title: str


class AddCardRequest(BaseModel):
    columnId: str
    title: str
    details: str = ""
    description: str = ""
    due_date: str | None = None
    priority: str = "medium"


class UpdateCardRequest(BaseModel):
    title: str
    details: str = ""
    description: str = ""
    due_date: str | None = None
    priority: str = "medium"


class CreateLabelRequest(BaseModel):
    name: str
    color: str = "#888888"


class UpdateLabelRequest(BaseModel):
    name: str
    color: str


class MoveCardRequest(BaseModel):
    columnId: str
    position: int


class RenameColumnRequest(BaseModel):
    title: str


class AiChatRequest(BaseModel):
    messages: list[dict]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _proxy_client
    init_db()
    migrate_db()
    _proxy_client = httpx.AsyncClient(base_url=NEXTJS_URL)
    yield
    await _proxy_client.aclose()
    _proxy_client = None


app = FastAPI(lifespan=lifespan)


# --- Auth dependency ---


def _get_session(token: str) -> dict | None:
    s = sessions.get(token)
    if not s:
        return None
    if time.time() - s["created_at"] > SESSION_TTL:
        sessions.pop(token, None)
        return None
    return s


def _create_session(username: str, user_id: int) -> str:
    token = secrets.token_hex(16)
    sessions[token] = {
        "username": username,
        "user_id": user_id,
        "created_at": time.time(),
    }
    return token


def require_session(session: str = Cookie(default="")) -> dict:
    s = _get_session(session)
    if not s:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return s


def _parse_id(prefixed_id: str) -> int:
    """Strip prefix (e.g. 'col-', 'card-', 'board-') and return the integer ID."""
    return int(prefixed_id.split("-", 1)[-1])


def _require_board_ownership(s: dict, board_id: str) -> int:
    """Verify user owns the board. Returns the integer board_id or raises 404."""
    from db import get_db
    bid = _parse_id(board_id)
    with get_db() as conn:
        if not _owns_board(conn, s["user_id"], bid):
            raise HTTPException(status_code=404, detail="Board not found")
    return bid


# --- Health ---


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Auth ---


@app.post("/api/register")
def register(body: RegisterRequest):
    password_hash = hash_password(body.password)
    user_id = create_user(body.username, password_hash)
    if user_id is None:
        return JSONResponse({"error": "Username already taken"}, status_code=409)
    ensure_user_board(user_id)
    token = _create_session(body.username, user_id)
    resp = JSONResponse({"username": body.username})
    resp.set_cookie("session", token, httponly=True, samesite="lax")
    return resp


@app.post("/api/login")
def login(body: LoginRequest):
    user = get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    ensure_user_board(user["id"])
    token = _create_session(user["username"], user["id"])
    resp = JSONResponse({"username": user["username"]})
    resp.set_cookie("session", token, httponly=True, samesite="lax")
    return resp


@app.post("/api/logout")
def logout(session: str = Cookie(default="")):
    sessions.pop(session, None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp


@app.get("/api/me")
def me(s: dict = Depends(require_session)):
    return {"username": s["username"]}


# --- Boards ---


@app.get("/api/boards")
def api_list_boards(s: dict = Depends(require_session)):
    return get_user_boards(s["user_id"])


@app.post("/api/boards")
def api_create_board(body: CreateBoardRequest, s: dict = Depends(require_session)):
    return create_board(s["user_id"], body.title)


@app.get("/api/boards/{board_id}")
def api_get_board(board_id: str, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    return get_board(bid)


@app.put("/api/boards/{board_id}")
def api_rename_board(board_id: str, body: RenameBoardRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    rename_board(s["user_id"], bid, body.title)
    return {"ok": True}


@app.delete("/api/boards/{board_id}")
def api_delete_board(board_id: str, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    delete_board(s["user_id"], bid)
    return {"ok": True}


# --- Cards (board-scoped) ---


@app.post("/api/boards/{board_id}/cards")
def api_add_card(board_id: str, body: AddCardRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    card = add_card(
        bid, _parse_id(body.columnId), body.title, body.details,
        description=body.description, due_date=body.due_date, priority=body.priority,
    )
    if not card:
        return JSONResponse({"error": "Column not found"}, status_code=404)
    return card


@app.put("/api/boards/{board_id}/cards/{card_id}")
def api_update_card(board_id: str, card_id: str, body: UpdateCardRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not update_card(
        bid, _parse_id(card_id), body.title, body.details,
        description=body.description, due_date=body.due_date, priority=body.priority,
    ):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


@app.delete("/api/boards/{board_id}/cards/{card_id}")
def api_delete_card(board_id: str, card_id: str, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not delete_card(bid, _parse_id(card_id)):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/boards/{board_id}/cards/{card_id}/move")
def api_move_card(board_id: str, card_id: str, body: MoveCardRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not move_card(bid, _parse_id(card_id), _parse_id(body.columnId), body.position):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


# --- Columns (board-scoped) ---


@app.put("/api/boards/{board_id}/columns/{column_id}")
def api_rename_column(board_id: str, column_id: str, body: RenameColumnRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not rename_column(bid, _parse_id(column_id), body.title):
        return JSONResponse({"error": "Column not found"}, status_code=404)
    return {"ok": True}


# --- Labels (board-scoped) ---


@app.get("/api/boards/{board_id}/labels")
def api_get_labels(board_id: str, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    return get_labels(bid)


@app.post("/api/boards/{board_id}/labels")
def api_create_label(board_id: str, body: CreateLabelRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    return create_label(bid, body.name, body.color)


@app.put("/api/boards/{board_id}/labels/{label_id}")
def api_update_label(board_id: str, label_id: str, body: UpdateLabelRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not update_label(bid, _parse_id(label_id), body.name, body.color):
        return JSONResponse({"error": "Label not found"}, status_code=404)
    return {"ok": True}


@app.delete("/api/boards/{board_id}/labels/{label_id}")
def api_delete_label(board_id: str, label_id: str, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not delete_label(bid, _parse_id(label_id)):
        return JSONResponse({"error": "Label not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/boards/{board_id}/cards/{card_id}/labels/{label_id}")
def api_add_label_to_card(board_id: str, card_id: str, label_id: str, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not add_label_to_card(bid, _parse_id(card_id), _parse_id(label_id)):
        return JSONResponse({"error": "Card or label not found"}, status_code=404)
    return {"ok": True}


@app.delete("/api/boards/{board_id}/cards/{card_id}/labels/{label_id}")
def api_remove_label_from_card(board_id: str, card_id: str, label_id: str, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    if not remove_label_from_card(bid, _parse_id(card_id), _parse_id(label_id)):
        return JSONResponse({"error": "Card not found"}, status_code=404)
    return {"ok": True}


# --- AI (board-scoped) ---


REQUIRED_ACTION_FIELDS = {
    "create_card": ("columnId", "title"),
    "update_card": ("cardId", "title"),
    "delete_card": ("cardId",),
    "move_card": ("cardId", "columnId"),
    "add_label_to_card": ("cardId", "labelId"),
    "remove_label_from_card": ("cardId", "labelId"),
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
                add_card(
                    board_id, _parse_id(action["columnId"]), action["title"],
                    action.get("details", ""),
                    description=action.get("description", ""),
                    due_date=action.get("due_date"),
                    priority=action.get("priority", "medium"),
                )
            elif action_type == "update_card":
                update_card(
                    board_id, _parse_id(action["cardId"]), action["title"],
                    action.get("details", ""),
                    description=action.get("description", ""),
                    due_date=action.get("due_date"),
                    priority=action.get("priority", "medium"),
                )
            elif action_type == "delete_card":
                delete_card(board_id, _parse_id(action["cardId"]))
            elif action_type == "move_card":
                move_card(
                    board_id,
                    _parse_id(action["cardId"]),
                    _parse_id(action["columnId"]),
                    action.get("position", 0),
                )
            elif action_type == "add_label_to_card":
                add_label_to_card(board_id, _parse_id(action["cardId"]), _parse_id(action["labelId"]))
            elif action_type == "remove_label_from_card":
                remove_label_from_card(board_id, _parse_id(action["cardId"]), _parse_id(action["labelId"]))
        except (ValueError, KeyError) as e:
            warnings.append(f"Skipped {action_type}: {e}")
    return warnings


@app.post("/api/boards/{board_id}/ai/chat")
async def api_ai_chat(board_id: str, body: AiChatRequest, s: dict = Depends(require_session)):
    bid = _require_board_ownership(s, board_id)
    board = get_board(bid)
    board_labels = get_labels(bid)
    result = await chat_with_board(board, body.messages, labels=board_labels)
    if result["actions"]:
        _apply_actions(result["actions"], bid)
        board = get_board(bid)
    return {"message": result["message"], "actions": result["actions"], "board": board}


# --- Proxy to Next.js ---


async def _proxy(request: Request, path: str = ""):
    client = _proxy_client or httpx.AsyncClient(base_url=NEXTJS_URL)
    try:
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
