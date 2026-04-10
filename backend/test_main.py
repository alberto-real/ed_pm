import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ["DB_PATH"] = ""

from db import create_user, ensure_user_board, get_board, get_user_by_username, init_db, migrate_db
from main import app, hash_password, verify_password, sessions


@pytest.fixture(autouse=True)
def _clean_state(tmp_path):
    os.environ["DB_PATH"] = str(tmp_path / "test.db")
    import db
    db.DB_PATH = os.environ["DB_PATH"]
    init_db()
    migrate_db()
    sessions.clear()
    yield
    sessions.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def authed_client(client):
    """A client that is registered and logged in."""
    client.post("/api/register", json={"username": "user", "password": "password"})
    return client


def _get_first_board_id(client) -> str:
    boards = client.get("/api/boards").json()
    return boards[0]["id"]


# --- Health ---


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Registration ---


def test_register_success(client):
    resp = client.post("/api/register", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "alice"}
    assert "session" in resp.cookies


def test_register_creates_default_board(client):
    client.post("/api/register", json={"username": "alice", "password": "secret123"})
    boards = client.get("/api/boards").json()
    assert len(boards) == 1
    assert boards[0]["title"] == "My Board"
    board_data = client.get(f"/api/boards/{boards[0]['id']}").json()
    assert len(board_data["columns"]) == 5
    assert len(board_data["cards"]) == 8


def test_register_duplicate_username(client):
    client.post("/api/register", json={"username": "alice", "password": "secret123"})
    resp = client.post("/api/register", json={"username": "alice", "password": "other456"})
    assert resp.status_code == 409
    assert "already taken" in resp.json()["error"]


def test_register_short_username(client):
    resp = client.post("/api/register", json={"username": "ab", "password": "secret123"})
    assert resp.status_code == 422


def test_register_long_username(client):
    resp = client.post("/api/register", json={"username": "a" * 31, "password": "secret123"})
    assert resp.status_code == 422


def test_register_short_password(client):
    resp = client.post("/api/register", json={"username": "alice", "password": "12345"})
    assert resp.status_code == 422


def test_register_hashes_password(client):
    client.post("/api/register", json={"username": "alice", "password": "secret123"})
    user = get_user_by_username("alice")
    assert user is not None
    assert user["password_hash"] != "secret123"
    assert verify_password("secret123", user["password_hash"])


# --- Login ---


def test_login_success(client):
    client.post("/api/register", json={"username": "alice", "password": "secret123"})
    client.cookies.clear()
    resp = client.post("/api/login", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "alice"}
    assert "session" in resp.cookies


def test_login_wrong_password(client):
    client.post("/api/register", json={"username": "alice", "password": "secret123"})
    client.cookies.clear()
    resp = client.post("/api/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/login", json={"username": "nobody", "password": "secret123"})
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


def test_session_expiry(authed_client):
    for token, data in sessions.items():
        data["created_at"] = time.time() - 90000
    resp = authed_client.get("/api/me")
    assert resp.status_code == 401


# --- Boards ---


def test_list_boards(authed_client):
    boards = authed_client.get("/api/boards").json()
    assert len(boards) == 1
    assert boards[0]["title"] == "My Board"
    assert boards[0]["id"].startswith("board-")


def test_create_board(authed_client):
    resp = authed_client.post("/api/boards", json={"title": "Sprint Board"})
    assert resp.status_code == 200
    new_board = resp.json()
    assert new_board["title"] == "Sprint Board"

    boards = authed_client.get("/api/boards").json()
    assert len(boards) == 2

    # New board has default columns but no seed cards
    board_data = authed_client.get(f"/api/boards/{new_board['id']}").json()
    assert len(board_data["columns"]) == 5
    assert len(board_data["cards"]) == 0


def test_rename_board(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.put(f"/api/boards/{board_id}", json={"title": "Renamed Board"})
    assert resp.status_code == 200

    boards = authed_client.get("/api/boards").json()
    assert boards[0]["title"] == "Renamed Board"


def test_delete_board(authed_client):
    # Create a second board to delete
    new_board = authed_client.post("/api/boards", json={"title": "To Delete"}).json()
    resp = authed_client.delete(f"/api/boards/{new_board['id']}")
    assert resp.status_code == 200

    boards = authed_client.get("/api/boards").json()
    assert len(boards) == 1
    assert boards[0]["title"] == "My Board"


def test_get_board_data(authed_client):
    board_id = _get_first_board_id(authed_client)
    data = authed_client.get(f"/api/boards/{board_id}").json()
    assert len(data["columns"]) == 5
    titles = [c["title"] for c in data["columns"]]
    assert titles == ["Backlog", "Discovery", "In Progress", "Review", "Done"]
    assert len(data["columns"][0]["cardIds"]) == 2
    assert len(data["cards"]) == 8


def test_boards_unauthenticated(client):
    resp = client.get("/api/boards")
    assert resp.status_code == 401


def test_cannot_access_other_users_board(authed_client):
    # Create user2's board via db functions
    board2_id = _register_user2()

    # authed_client (user) tries to access user2's board
    resp = authed_client.get(f"/api/boards/board-{board2_id}")
    assert resp.status_code == 404


# --- Cards (board-scoped) ---


def test_add_card(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board["columns"][0]["id"]
    resp = authed_client.post(f"/api/boards/{board_id}/cards", json={
        "columnId": col_id, "title": "Test card", "details": "Some details",
    })
    assert resp.status_code == 200
    card = resp.json()
    assert card["title"] == "Test card"
    assert card["details"] == "Some details"

    board = authed_client.get(f"/api/boards/{board_id}").json()
    assert card["id"] in board["cards"]
    assert card["id"] in board["columns"][0]["cardIds"]


def test_update_card(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board["columns"][0]["id"]
    card = authed_client.post(f"/api/boards/{board_id}/cards", json={
        "columnId": col_id, "title": "Original", "details": "v1",
    }).json()
    resp = authed_client.put(f"/api/boards/{board_id}/cards/{card['id']}", json={
        "title": "Updated", "details": "v2",
    })
    assert resp.status_code == 200
    board = authed_client.get(f"/api/boards/{board_id}").json()
    assert board["cards"][card["id"]]["title"] == "Updated"


def test_update_nonexistent_card(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.put(f"/api/boards/{board_id}/cards/card-9999", json={"title": "X", "details": ""})
    assert resp.status_code == 404


def test_delete_card(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board["columns"][0]["id"]
    card = authed_client.post(f"/api/boards/{board_id}/cards", json={
        "columnId": col_id, "title": "To delete", "details": "",
    }).json()
    resp = authed_client.delete(f"/api/boards/{board_id}/cards/{card['id']}")
    assert resp.status_code == 200
    board = authed_client.get(f"/api/boards/{board_id}").json()
    assert card["id"] not in board["cards"]


def test_delete_nonexistent_card(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.delete(f"/api/boards/{board_id}/cards/card-9999")
    assert resp.status_code == 404


# --- Move card ---


def test_move_card_between_columns(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_a = board["columns"][0]["id"]
    col_b = board["columns"][1]["id"]
    card = authed_client.post(f"/api/boards/{board_id}/cards", json={
        "columnId": col_a, "title": "Movable", "details": "",
    }).json()
    resp = authed_client.post(f"/api/boards/{board_id}/cards/{card['id']}/move", json={
        "columnId": col_b, "position": 0,
    })
    assert resp.status_code == 200
    board = authed_client.get(f"/api/boards/{board_id}").json()
    assert card["id"] not in board["columns"][0]["cardIds"]
    assert card["id"] in board["columns"][1]["cardIds"]


def test_move_card_within_column(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board["columns"][3]["id"]
    c1 = authed_client.post(f"/api/boards/{board_id}/cards", json={"columnId": col_id, "title": "A", "details": ""}).json()
    c2 = authed_client.post(f"/api/boards/{board_id}/cards", json={"columnId": col_id, "title": "B", "details": ""}).json()
    authed_client.post(f"/api/boards/{board_id}/cards/{c2['id']}/move", json={"columnId": col_id, "position": 0})
    board = authed_client.get(f"/api/boards/{board_id}").json()
    review_ids = board["columns"][3]["cardIds"]
    assert review_ids[0] == c2["id"]
    assert review_ids[-1] == c1["id"]


# --- Columns ---


def test_rename_column(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board["columns"][0]["id"]
    resp = authed_client.put(f"/api/boards/{board_id}/columns/{col_id}", json={"title": "New Name"})
    assert resp.status_code == 200
    board = authed_client.get(f"/api/boards/{board_id}").json()
    assert board["columns"][0]["title"] == "New Name"


def test_rename_nonexistent_column(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.put(f"/api/boards/{board_id}/columns/col-9999", json={"title": "X"})
    assert resp.status_code == 404


# --- AI ---


def test_ai_chat_no_actions(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)

    async def mock_chat_with_board(board, conversation, labels=None):
        return {"message": "Your board looks great!", "actions": []}

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "How does my board look?"}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Your board looks great!"
    assert data["actions"] == []
    assert len(data["board"]["columns"]) == 5


def test_ai_chat_create_card(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)
    board_data = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board_data["columns"][0]["id"]

    async def mock_chat_with_board(board, conversation, labels=None):
        return {
            "message": "Done! I created a new card.",
            "actions": [{"type": "create_card", "columnId": col_id, "title": "AI card", "details": "Created by AI"}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "Add a card called AI card to Backlog"}],
    })
    assert resp.status_code == 200
    card_titles = [c["title"] for c in resp.json()["board"]["cards"].values()]
    assert "AI card" in card_titles


def test_ai_chat_delete_card(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)
    board_data = authed_client.get(f"/api/boards/{board_id}").json()
    card_id = board_data["columns"][0]["cardIds"][0]

    async def mock_chat_with_board(board, conversation, labels=None):
        return {
            "message": "Deleted.",
            "actions": [{"type": "delete_card", "cardId": card_id}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "Delete the first card"}],
    })
    assert resp.status_code == 200
    assert card_id not in resp.json()["board"]["cards"]


def test_ai_chat_move_card(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)
    board_data = authed_client.get(f"/api/boards/{board_id}").json()
    card_id = board_data["columns"][0]["cardIds"][0]
    target_col = board_data["columns"][1]["id"]

    async def mock_chat_with_board(board, conversation, labels=None):
        return {
            "message": "Moved.",
            "actions": [{"type": "move_card", "cardId": card_id, "columnId": target_col, "position": 0}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
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


# --- Cross-user isolation ---


def _register_user2():
    password_hash = hash_password("password2")
    user_id = create_user("user2", password_hash)
    board_id = ensure_user_board(user_id)
    return board_id


def test_cannot_update_other_users_card(authed_client):
    board2_id = _register_user2()
    board2 = get_board(board2_id)
    card_id = board2["columns"][0]["cardIds"][0]
    # Use a board_id the user owns, but the card belongs to user2
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.put(f"/api/boards/{board_id}/cards/{card_id}", json={"title": "Hacked", "details": ""})
    assert resp.status_code == 404


def test_cannot_delete_other_users_card(authed_client):
    board2_id = _register_user2()
    board2 = get_board(board2_id)
    card_id = board2["columns"][0]["cardIds"][0]
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.delete(f"/api/boards/{board_id}/cards/{card_id}")
    assert resp.status_code == 404
    board2_after = get_board(board2_id)
    assert card_id in board2_after["columns"][0]["cardIds"]


def test_cannot_access_other_users_board_for_cards(authed_client):
    board2_id = _register_user2()
    resp = authed_client.post(f"/api/boards/board-{board2_id}/cards", json={
        "columnId": "col-999", "title": "Injected", "details": "",
    })
    assert resp.status_code == 404


def test_cannot_rename_other_users_column(authed_client):
    board2_id = _register_user2()
    board2 = get_board(board2_id)
    col_id = board2["columns"][0]["id"]
    resp = authed_client.put(f"/api/boards/board-{board2_id}/columns/{col_id}", json={"title": "Hacked"})
    assert resp.status_code == 404
    board2_after = get_board(board2_id)
    assert board2_after["columns"][0]["title"] == "Backlog"


# --- Malformed input ---


def test_add_card_missing_fields(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.post(f"/api/boards/{board_id}/cards", json={})
    assert resp.status_code == 422


def test_add_card_missing_title(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.post(f"/api/boards/{board_id}/cards", json={"columnId": "col-1"})
    assert resp.status_code == 422


def test_update_card_missing_title(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.put(f"/api/boards/{board_id}/cards/card-1", json={})
    assert resp.status_code == 422


def test_move_card_missing_fields(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.post(f"/api/boards/{board_id}/cards/card-1/move", json={})
    assert resp.status_code == 422


def test_rename_column_missing_title(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.put(f"/api/boards/{board_id}/columns/col-1", json={})
    assert resp.status_code == 422


def test_login_missing_fields(client):
    resp = client.post("/api/login", json={})
    assert resp.status_code == 422


def test_ai_chat_missing_messages(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={})
    assert resp.status_code == 422


def test_add_card_invalid_json(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.post(
        f"/api/boards/{board_id}/cards",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


# --- AI action validation ---


def test_ai_chat_skips_malformed_actions(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)

    async def mock_chat_with_board(board, conversation, labels=None):
        return {
            "message": "Tried to do things.",
            "actions": [
                {"type": "create_card"},
                {"type": "unknown_action"},
                {"type": "delete_card"},
            ],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "Do stuff"}],
    })
    assert resp.status_code == 200
    assert len(resp.json()["board"]["cards"]) == 8


def test_ai_chat_skips_invalid_id_in_action(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)

    async def mock_chat_with_board(board, conversation, labels=None):
        return {
            "message": "Tried.",
            "actions": [{"type": "delete_card", "cardId": "card-abc"}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "Do stuff"}],
    })
    assert resp.status_code == 200
    assert len(resp.json()["board"]["cards"]) == 8


# --- Multi-user ---


def test_two_users_get_independent_boards(client):
    client.post("/api/register", json={"username": "alice", "password": "secret123"})
    alice_boards = client.get("/api/boards").json()
    alice_board = client.get(f"/api/boards/{alice_boards[0]['id']}").json()
    client.post("/api/logout")

    client.post("/api/register", json={"username": "bob", "password": "secret456"})
    bob_boards = client.get("/api/boards").json()
    bob_board = client.get(f"/api/boards/{bob_boards[0]['id']}").json()

    assert len(alice_board["columns"]) == 5
    assert len(bob_board["columns"]) == 5
    assert set(alice_board["cards"].keys()) != set(bob_board["cards"].keys())


# --- Card enhanced fields ---


def test_add_card_with_priority_and_due_date(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board["columns"][0]["id"]
    resp = authed_client.post(f"/api/boards/{board_id}/cards", json={
        "columnId": col_id, "title": "Urgent task", "details": "Do now",
        "description": "This is a longer description.", "due_date": "2026-04-15", "priority": "high",
    })
    assert resp.status_code == 200
    card = resp.json()
    assert card["priority"] == "high"
    assert card["due_date"] == "2026-04-15"
    assert card["description"] == "This is a longer description."


def test_update_card_with_new_fields(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board["columns"][0]["id"]
    card = authed_client.post(f"/api/boards/{board_id}/cards", json={
        "columnId": col_id, "title": "Test", "details": "",
    }).json()
    resp = authed_client.put(f"/api/boards/{board_id}/cards/{card['id']}", json={
        "title": "Updated", "details": "v2",
        "description": "Full desc", "due_date": "2026-05-01", "priority": "low",
    })
    assert resp.status_code == 200

    board = authed_client.get(f"/api/boards/{board_id}").json()
    updated = board["cards"][card["id"]]
    assert updated["priority"] == "low"
    assert updated["due_date"] == "2026-05-01"
    assert updated["description"] == "Full desc"


def test_board_cards_include_new_fields(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    first_card = list(board["cards"].values())[0]
    assert "priority" in first_card
    assert "due_date" in first_card
    assert "description" in first_card
    assert "labels" in first_card
    assert first_card["priority"] == "medium"  # default


# --- Labels ---


def test_create_label(authed_client):
    board_id = _get_first_board_id(authed_client)
    resp = authed_client.post(f"/api/boards/{board_id}/labels", json={
        "name": "Bug", "color": "#e74c3c",
    })
    assert resp.status_code == 200
    label = resp.json()
    assert label["name"] == "Bug"
    assert label["color"] == "#e74c3c"
    assert label["id"].startswith("label-")


def test_list_labels(authed_client):
    board_id = _get_first_board_id(authed_client)
    authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Bug", "color": "#e74c3c"})
    authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Feature", "color": "#2ecc71"})
    resp = authed_client.get(f"/api/boards/{board_id}/labels")
    assert resp.status_code == 200
    labels = resp.json()
    assert len(labels) == 2
    assert labels[0]["name"] == "Bug"
    assert labels[1]["name"] == "Feature"


def test_update_label(authed_client):
    board_id = _get_first_board_id(authed_client)
    label = authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Bug", "color": "#e74c3c"}).json()
    resp = authed_client.put(f"/api/boards/{board_id}/labels/{label['id']}", json={
        "name": "Critical Bug", "color": "#ff0000",
    })
    assert resp.status_code == 200
    labels = authed_client.get(f"/api/boards/{board_id}/labels").json()
    assert labels[0]["name"] == "Critical Bug"
    assert labels[0]["color"] == "#ff0000"


def test_delete_label(authed_client):
    board_id = _get_first_board_id(authed_client)
    label = authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Temp", "color": "#888"}).json()
    resp = authed_client.delete(f"/api/boards/{board_id}/labels/{label['id']}")
    assert resp.status_code == 200
    labels = authed_client.get(f"/api/boards/{board_id}/labels").json()
    assert len(labels) == 0


def test_add_label_to_card(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    label = authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Bug", "color": "#e74c3c"}).json()

    resp = authed_client.post(f"/api/boards/{board_id}/cards/{card_id}/labels/{label['id']}")
    assert resp.status_code == 200

    board = authed_client.get(f"/api/boards/{board_id}").json()
    card_labels = board["cards"][card_id]["labels"]
    assert len(card_labels) == 1
    assert card_labels[0]["name"] == "Bug"


def test_remove_label_from_card(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    label = authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Bug", "color": "#e74c3c"}).json()
    authed_client.post(f"/api/boards/{board_id}/cards/{card_id}/labels/{label['id']}")

    resp = authed_client.delete(f"/api/boards/{board_id}/cards/{card_id}/labels/{label['id']}")
    assert resp.status_code == 200

    board = authed_client.get(f"/api/boards/{board_id}").json()
    assert len(board["cards"][card_id]["labels"]) == 0


def test_delete_label_removes_from_cards(authed_client):
    board_id = _get_first_board_id(authed_client)
    board = authed_client.get(f"/api/boards/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    label = authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Bug", "color": "#e74c3c"}).json()
    authed_client.post(f"/api/boards/{board_id}/cards/{card_id}/labels/{label['id']}")

    # Delete the label itself
    authed_client.delete(f"/api/boards/{board_id}/labels/{label['id']}")

    board = authed_client.get(f"/api/boards/{board_id}").json()
    assert len(board["cards"][card_id]["labels"]) == 0


def test_cannot_use_other_users_labels(authed_client):
    board_id = _get_first_board_id(authed_client)
    board2_id = _register_user2()
    # Create label on user2's board directly via db
    from db import create_label as db_create_label
    label = db_create_label(board2_id, "Stolen", "#000")

    # Try to add user2's label to user1's card
    board = authed_client.get(f"/api/boards/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    resp = authed_client.post(f"/api/boards/{board_id}/cards/{card_id}/labels/{label['id']}")
    assert resp.status_code == 404


# --- AI with enhanced actions ---


def test_ai_chat_create_card_with_priority(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)
    board_data = authed_client.get(f"/api/boards/{board_id}").json()
    col_id = board_data["columns"][0]["id"]

    async def mock_chat_with_board(board, conversation, labels=None):
        return {
            "message": "Created a high priority card.",
            "actions": [{
                "type": "create_card", "columnId": col_id, "title": "Urgent",
                "details": "Fix ASAP", "priority": "high", "due_date": "2026-04-20",
            }],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "Add an urgent card"}],
    })
    assert resp.status_code == 200
    cards = resp.json()["board"]["cards"]
    urgent = [c for c in cards.values() if c["title"] == "Urgent"]
    assert len(urgent) == 1
    assert urgent[0]["priority"] == "high"
    assert urgent[0]["due_date"] == "2026-04-20"


def test_ai_chat_add_label_to_card(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)
    board_data = authed_client.get(f"/api/boards/{board_id}").json()
    card_id = board_data["columns"][0]["cardIds"][0]
    label = authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Bug", "color": "#e74c3c"}).json()

    async def mock_chat_with_board(board, conversation, labels=None):
        return {
            "message": "Labeled it as a bug.",
            "actions": [{"type": "add_label_to_card", "cardId": card_id, "labelId": label["id"]}],
        }

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    resp = authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "Mark first card as bug"}],
    })
    assert resp.status_code == 200
    card_labels = resp.json()["board"]["cards"][card_id]["labels"]
    assert any(l["name"] == "Bug" for l in card_labels)


def test_ai_chat_passes_labels_context(authed_client, monkeypatch):
    board_id = _get_first_board_id(authed_client)
    authed_client.post(f"/api/boards/{board_id}/labels", json={"name": "Feature", "color": "#2ecc71"})

    received_labels = []

    async def mock_chat_with_board(board, conversation, labels=None):
        received_labels.extend(labels or [])
        return {"message": "Got it.", "actions": []}

    import main
    monkeypatch.setattr(main, "chat_with_board", mock_chat_with_board)
    authed_client.post(f"/api/boards/{board_id}/ai/chat", json={
        "messages": [{"role": "user", "content": "What labels exist?"}],
    })
    assert len(received_labels) == 1
    assert received_labels[0]["name"] == "Feature"
