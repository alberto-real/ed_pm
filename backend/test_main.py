import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

# Use a temp DB for each test
os.environ["DB_PATH"] = ""

from db import ensure_user_board, get_board, init_db
from main import app, sessions


@pytest.fixture(autouse=True)
def _clean_state(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "test.db")
    import db
    db.DB_PATH = os.environ["DB_PATH"]
    init_db()
    sessions.clear()
    yield
    sessions.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def authed_client(client):
    """A client that is already logged in."""
    client.post("/api/login", json={"username": "user", "password": "password"})
    return client


# --- Health ---


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Auth ---


def test_login_success(client):
    resp = client.post("/api/login", json={"username": "user", "password": "password"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "user"}
    assert "session" in resp.cookies


def test_login_wrong_password(client):
    resp = client.post("/api/login", json={"username": "user", "password": "wrong"})
    assert resp.status_code == 401


def test_me_unauthenticated(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_me_authenticated(authed_client):
    resp = authed_client.get("/api/me")
    assert resp.status_code == 200
    assert resp.json() == {"username": "user"}


def test_logout(authed_client):
    resp = authed_client.post("/api/logout")
    assert resp.status_code == 200
    resp = authed_client.get("/api/me")
    assert resp.status_code == 401


def test_session_expiry(authed_client, monkeypatch):
    """Expired sessions should be rejected."""
    # Find the session token and set its created_at to the past
    for token, data in sessions.items():
        data["created_at"] = time.time() - 90000  # 25 hours ago
    resp = authed_client.get("/api/me")
    assert resp.status_code == 401


# --- Board ---


def test_get_board_unauthenticated(client):
    resp = client.get("/api/board")
    assert resp.status_code == 401


def test_get_board_returns_default_columns_with_seed_cards(authed_client):
    resp = authed_client.get("/api/board")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["columns"]) == 5
    titles = [c["title"] for c in data["columns"]]
    assert titles == ["Backlog", "Discovery", "In Progress", "Review", "Done"]
    assert len(data["columns"][0]["cardIds"]) == 2
    assert len(data["cards"]) == 8


# --- Cards ---


def test_add_card(authed_client):
    board = authed_client.get("/api/board").json()
    col_id = board["columns"][0]["id"]
    resp = authed_client.post("/api/cards", json={
        "columnId": col_id, "title": "Test card", "details": "Some details",
    })
    assert resp.status_code == 200
    card = resp.json()
    assert card["title"] == "Test card"
    assert card["details"] == "Some details"
    assert "id" in card

    # Verify card appears in board
    board = authed_client.get("/api/board").json()
    assert card["id"] in board["cards"]
    assert card["id"] in board["columns"][0]["cardIds"]


def test_update_card(authed_client):
    board = authed_client.get("/api/board").json()
    col_id = board["columns"][0]["id"]
    card = authed_client.post("/api/cards", json={
        "columnId": col_id, "title": "Original", "details": "v1",
    }).json()
    resp = authed_client.put(f"/api/cards/{card['id']}", json={
        "title": "Updated", "details": "v2",
    })
    assert resp.status_code == 200
    board = authed_client.get("/api/board").json()
    assert board["cards"][card["id"]]["title"] == "Updated"
    assert board["cards"][card["id"]]["details"] == "v2"


def test_update_nonexistent_card(authed_client):
    resp = authed_client.put("/api/cards/card-9999", json={"title": "X", "details": ""})
    assert resp.status_code == 404


def test_delete_card(authed_client):
    board = authed_client.get("/api/board").json()
    col_id = board["columns"][0]["id"]
    card = authed_client.post("/api/cards", json={
        "columnId": col_id, "title": "To delete", "details": "",
    }).json()
    resp = authed_client.delete(f"/api/cards/{card['id']}")
    assert resp.status_code == 200
    board = authed_client.get("/api/board").json()
    assert card["id"] not in board["cards"]


def test_delete_nonexistent_card(authed_client):
    resp = authed_client.delete("/api/cards/card-9999")
    assert resp.status_code == 404


# --- Move card ---


def test_move_card_between_columns(authed_client):
    board = authed_client.get("/api/board").json()
    col_a = board["columns"][0]["id"]
    col_b = board["columns"][1]["id"]
    card = authed_client.post("/api/cards", json={
        "columnId": col_a, "title": "Movable", "details": "",
    }).json()
    resp = authed_client.post(f"/api/cards/{card['id']}/move", json={
        "columnId": col_b, "position": 0,
    })
    assert resp.status_code == 200
    board = authed_client.get("/api/board").json()
    assert card["id"] not in board["columns"][0]["cardIds"]
    assert card["id"] in board["columns"][1]["cardIds"]


def test_move_card_within_column(authed_client):
    board = authed_client.get("/api/board").json()
    # Use a column with no seed cards (In Progress has 2, but Discovery has 1)
    # Use column index 3 (Review) which has 1 seed card
    col_id = board["columns"][3]["id"]
    c1 = authed_client.post("/api/cards", json={"columnId": col_id, "title": "A", "details": ""}).json()
    c2 = authed_client.post("/api/cards", json={"columnId": col_id, "title": "B", "details": ""}).json()
    # Move B to position 0 (top)
    authed_client.post(f"/api/cards/{c2['id']}/move", json={"columnId": col_id, "position": 0})
    board = authed_client.get("/api/board").json()
    review_ids = board["columns"][3]["cardIds"]
    # B should be first, then the seed card, then A
    assert review_ids[0] == c2["id"]
    assert review_ids[-1] == c1["id"]


# --- Columns ---


def test_rename_column(authed_client):
    board = authed_client.get("/api/board").json()
    col_id = board["columns"][0]["id"]
    resp = authed_client.put(f"/api/columns/{col_id}", json={"title": "New Name"})
    assert resp.status_code == 200
    board = authed_client.get("/api/board").json()
    assert board["columns"][0]["title"] == "New Name"


def test_rename_nonexistent_column(authed_client):
    resp = authed_client.put("/api/columns/col-9999", json={"title": "X"})
    assert resp.status_code == 404


# --- AI ---


def test_ai_test_unauthenticated(client):
    resp = client.post("/api/ai/test")
    assert resp.status_code == 401


def test_ai_test_mocked(authed_client, monkeypatch):
    async def mock_chat(messages):
        return "4"

    import main
    monkeypatch.setattr(main, "ai_chat", mock_chat)
    resp = authed_client.post("/api/ai/test")
    assert resp.status_code == 200
    assert resp.json()["answer"] == "4"


def test_ai_chat_no_actions(authed_client, monkeypatch):
    async def mock_chat_with_board(board, conversation):
        return {"message": "Your board looks great!", "actions": []}

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "How does my board look?"}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Your board looks great!"
    assert data["actions"] == []
    assert len(data["board"]["columns"]) == 5


def test_ai_chat_create_card(authed_client, monkeypatch):
    board_data = authed_client.get("/api/board").json()
    col_id = board_data["columns"][0]["id"]

    async def mock_chat_with_board(board, conversation):
        return {
            "message": "Done! I created a new card.",
            "actions": [{"type": "create_card", "columnId": col_id, "title": "AI card", "details": "Created by AI"}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "Add a card called AI card to Backlog"}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Done! I created a new card."
    # Board should have the new card
    card_titles = [c["title"] for c in data["board"]["cards"].values()]
    assert "AI card" in card_titles


def test_ai_chat_delete_card(authed_client, monkeypatch):
    board_data = authed_client.get("/api/board").json()
    card_id = board_data["columns"][0]["cardIds"][0]

    async def mock_chat_with_board(board, conversation):
        return {
            "message": "Deleted.",
            "actions": [{"type": "delete_card", "cardId": card_id}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "Delete the first card"}],
    })
    assert resp.status_code == 200
    assert card_id not in resp.json()["board"]["cards"]


def test_ai_chat_move_card(authed_client, monkeypatch):
    board_data = authed_client.get("/api/board").json()
    card_id = board_data["columns"][0]["cardIds"][0]
    target_col = board_data["columns"][1]["id"]

    async def mock_chat_with_board(board, conversation):
        return {
            "message": "Moved.",
            "actions": [{"type": "move_card", "cardId": card_id, "columnId": target_col, "position": 0}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "Move first card to Discovery"}],
    })
    assert resp.status_code == 200
    board = resp.json()["board"]
    assert card_id not in board["columns"][0]["cardIds"]
    assert card_id in board["columns"][1]["cardIds"]


# --- Proxy ---


def test_proxy_root_returns_error_when_nextjs_down(client):
    resp = client.get("/")
    assert resp.status_code == 502 or resp.status_code == 500


# --- Authorization (cross-user isolation) ---


def test_cannot_update_other_users_card(authed_client):
    """User cannot update a card belonging to another user's board."""
    _, board2_id = ensure_user_board("user2")
    board2 = get_board(board2_id)
    card_id = board2["columns"][0]["cardIds"][0]
    resp = authed_client.put(f"/api/cards/{card_id}", json={"title": "Hacked", "details": ""})
    assert resp.status_code == 404


def test_cannot_delete_other_users_card(authed_client):
    """User cannot delete a card belonging to another user's board."""
    _, board2_id = ensure_user_board("user2")
    board2 = get_board(board2_id)
    card_id = board2["columns"][0]["cardIds"][0]
    resp = authed_client.delete(f"/api/cards/{card_id}")
    assert resp.status_code == 404
    # Verify card still exists
    board2_after = get_board(board2_id)
    assert card_id in board2_after["columns"][0]["cardIds"]


def test_cannot_move_other_users_card(authed_client):
    """User cannot move a card belonging to another user's board."""
    _, board2_id = ensure_user_board("user2")
    board2 = get_board(board2_id)
    card_id = board2["columns"][0]["cardIds"][0]
    target_col = board2["columns"][1]["id"]
    resp = authed_client.post(f"/api/cards/{card_id}/move", json={
        "columnId": target_col, "position": 0,
    })
    assert resp.status_code == 404


def test_cannot_add_card_to_other_users_column(authed_client):
    """User cannot add a card to another user's column."""
    _, board2_id = ensure_user_board("user2")
    board2 = get_board(board2_id)
    col_id = board2["columns"][0]["id"]
    resp = authed_client.post("/api/cards", json={
        "columnId": col_id, "title": "Injected", "details": "",
    })
    assert resp.status_code == 404


def test_cannot_rename_other_users_column(authed_client):
    """User cannot rename a column belonging to another user's board."""
    _, board2_id = ensure_user_board("user2")
    board2 = get_board(board2_id)
    col_id = board2["columns"][0]["id"]
    resp = authed_client.put(f"/api/columns/{col_id}", json={"title": "Hacked"})
    assert resp.status_code == 404
    # Verify column name unchanged
    board2_after = get_board(board2_id)
    assert board2_after["columns"][0]["title"] == "Backlog"


# --- Malformed input ---


def test_add_card_missing_fields(authed_client):
    resp = authed_client.post("/api/cards", json={})
    assert resp.status_code == 422


def test_add_card_missing_title(authed_client):
    resp = authed_client.post("/api/cards", json={"columnId": "col-1"})
    assert resp.status_code == 422


def test_update_card_missing_title(authed_client):
    resp = authed_client.put("/api/cards/card-1", json={})
    assert resp.status_code == 422


def test_move_card_missing_fields(authed_client):
    resp = authed_client.post("/api/cards/card-1/move", json={})
    assert resp.status_code == 422


def test_rename_column_missing_title(authed_client):
    resp = authed_client.put("/api/columns/col-1", json={})
    assert resp.status_code == 422


def test_login_missing_fields(client):
    resp = client.post("/api/login", json={})
    assert resp.status_code == 422


def test_ai_chat_missing_messages(authed_client):
    resp = authed_client.post("/api/ai/chat", json={})
    assert resp.status_code == 422


def test_add_card_invalid_json(authed_client):
    resp = authed_client.post(
        "/api/cards",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


# --- AI action validation ---


def test_ai_chat_skips_malformed_actions(authed_client, monkeypatch):
    """Actions with missing required fields should be skipped without crashing."""
    async def mock_chat_with_board(board, conversation):
        return {
            "message": "Tried to do things.",
            "actions": [
                {"type": "create_card"},  # missing columnId and title
                {"type": "unknown_action"},  # unknown type
                {"type": "delete_card"},  # missing cardId
            ],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "Do stuff"}],
    })
    assert resp.status_code == 200
    # Board should be unchanged (8 seed cards)
    assert len(resp.json()["board"]["cards"]) == 8


def test_ai_chat_skips_invalid_id_in_action(authed_client, monkeypatch):
    """Actions with non-numeric IDs should be skipped without crashing."""
    async def mock_chat_with_board(board, conversation):
        return {
            "message": "Tried.",
            "actions": [
                {"type": "delete_card", "cardId": "card-abc"},  # non-numeric
            ],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post("/api/ai/chat", json={
        "messages": [{"role": "user", "content": "Do stuff"}],
    })
    assert resp.status_code == 200
    assert len(resp.json()["board"]["cards"]) == 8
