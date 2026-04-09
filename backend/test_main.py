import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Use a temp DB for each test
os.environ["DB_PATH"] = ""

from db import init_db
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
    resp = authed_client.put("/api/cards/9999", json={"title": "X", "details": ""})
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
    resp = authed_client.delete("/api/cards/9999")
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
    resp = authed_client.put("/api/columns/9999", json={"title": "X"})
    assert resp.status_code == 404


# --- Proxy ---


def test_proxy_root_returns_error_when_nextjs_down(client):
    resp = client.get("/")
    assert resp.status_code == 502 or resp.status_code == 500
