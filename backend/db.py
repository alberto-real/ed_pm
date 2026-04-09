import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "data" / "kanban.db"))

DEFAULT_COLUMNS = ["Backlog", "Discovery", "In Progress", "Review", "Done"]

SEED_CARDS = {
    "Backlog": [
        ("Align roadmap themes", "Draft quarterly themes with impact statements and metrics."),
        ("Gather customer signals", "Review support tags, sales notes, and churn feedback."),
    ],
    "Discovery": [
        ("Prototype analytics view", "Sketch initial dashboard layout and key drill-downs."),
    ],
    "In Progress": [
        ("Refine status language", "Standardize column labels and tone across the board."),
        ("Design card layout", "Add hierarchy and spacing for scanning dense lists."),
    ],
    "Review": [
        ("QA micro-interactions", "Verify hover, focus, and loading states."),
    ],
    "Done": [
        ("Ship marketing page", "Final copy approved and asset pack delivered."),
        ("Close onboarding sprint", "Document release notes and share internally."),
    ],
}


def get_conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL DEFAULT 'My Board'
        );
        CREATE TABLE IF NOT EXISTS columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            position INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_id INTEGER NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def ensure_user_board(username: str) -> tuple[int, int]:
    """Return (user_id, board_id), creating them if needed."""
    conn = get_conn()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row:
        user_id = row["id"]
    else:
        cur = conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
        user_id = cur.lastrowid
    board = conn.execute("SELECT id FROM boards WHERE user_id = ?", (user_id,)).fetchone()
    if board:
        board_id = board["id"]
    else:
        cur = conn.execute("INSERT INTO boards (user_id) VALUES (?)", (user_id,))
        board_id = cur.lastrowid
        for i, title in enumerate(DEFAULT_COLUMNS):
            cur = conn.execute(
                "INSERT INTO columns (board_id, title, position) VALUES (?, ?, ?)",
                (board_id, title, i),
            )
            col_id = cur.lastrowid
            for j, (card_title, card_details) in enumerate(SEED_CARDS.get(title, [])):
                conn.execute(
                    "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
                    (col_id, card_title, card_details, j),
                )
    conn.commit()
    conn.close()
    return user_id, board_id


def get_board(board_id: int) -> dict:
    conn = get_conn()
    cols = conn.execute(
        "SELECT id, title, position FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    columns = []
    cards = {}
    for col in cols:
        col_cards = conn.execute(
            "SELECT id, title, details, position FROM cards WHERE column_id = ? ORDER BY position",
            (col["id"],),
        ).fetchall()
        card_ids = []
        for c in col_cards:
            card_id = f"card-{c['id']}"
            card_ids.append(card_id)
            cards[card_id] = {"id": card_id, "title": c["title"], "details": c["details"]}
        columns.append({"id": f"col-{col['id']}", "title": col["title"], "cardIds": card_ids})
    conn.close()
    return {"columns": columns, "cards": cards}


def add_card(column_id: int, title: str, details: str) -> dict:
    conn = get_conn()
    max_pos = conn.execute(
        "SELECT COALESCE(MAX(position), -1) as m FROM cards WHERE column_id = ?",
        (column_id,),
    ).fetchone()["m"]
    cur = conn.execute(
        "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
        (column_id, title, details, max_pos + 1),
    )
    card_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": f"card-{card_id}", "title": title, "details": details}


def update_card(card_id: int, title: str, details: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE cards SET title = ?, details = ? WHERE id = ?",
        (title, details, card_id),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def delete_card(card_id: int) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def move_card(card_id: int, target_column_id: int, position: int):
    conn = get_conn()
    # Get current column
    row = conn.execute("SELECT column_id FROM cards WHERE id = ?", (card_id,)).fetchone()
    if not row:
        conn.close()
        return False
    old_column_id = row["column_id"]
    # Remove from old position
    old_pos = conn.execute("SELECT position FROM cards WHERE id = ?", (card_id,)).fetchone()["position"]
    conn.execute(
        "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
        (old_column_id, old_pos),
    )
    # Make room in target column
    conn.execute(
        "UPDATE cards SET position = position + 1 WHERE column_id = ? AND position >= ?",
        (target_column_id, position),
    )
    # Move the card
    conn.execute(
        "UPDATE cards SET column_id = ?, position = ? WHERE id = ?",
        (target_column_id, position, card_id),
    )
    conn.commit()
    conn.close()
    return True


def rename_column(column_id: int, title: str) -> bool:
    conn = get_conn()
    cur = conn.execute("UPDATE columns SET title = ? WHERE id = ?", (title, column_id))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed
