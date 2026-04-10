import os
import sqlite3
from contextlib import contextmanager
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


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL DEFAULT ''
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
                description TEXT NOT NULL DEFAULT '',
                due_date TEXT DEFAULT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                position INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#888888'
            );
            CREATE TABLE IF NOT EXISTS card_labels (
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                label_id INTEGER NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
                PRIMARY KEY (card_id, label_id)
            );
        """)
        conn.commit()


def migrate_db():
    """Apply incremental schema changes. Safe to call repeatedly."""
    with get_db() as conn:
        user_cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "password_hash" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")

        card_cols = [row["name"] for row in conn.execute("PRAGMA table_info(cards)").fetchall()]
        if "description" not in card_cols:
            conn.execute("ALTER TABLE cards ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        if "due_date" not in card_cols:
            conn.execute("ALTER TABLE cards ADD COLUMN due_date TEXT DEFAULT NULL")
        if "priority" not in card_cols:
            conn.execute("ALTER TABLE cards ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium'")

        conn.commit()


# --- User management ---


def create_user(username: str, password_hash: str) -> int | None:
    with get_db() as conn:
        with conn:
            try:
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                return None


def get_user_by_username(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"], "password_hash": row["password_hash"]}
        return None


# --- Board management ---


def _owns_board(conn: sqlite3.Connection, user_id: int, board_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM boards WHERE id = ? AND user_id = ?",
        (board_id, user_id),
    ).fetchone()
    return row is not None


def get_user_boards(user_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title FROM boards WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [{"id": f"board-{row['id']}", "title": row["title"]} for row in rows]


def create_board(user_id: int, title: str) -> dict:
    with get_db() as conn:
        with conn:
            cur = conn.execute(
                "INSERT INTO boards (user_id, title) VALUES (?, ?)",
                (user_id, title),
            )
            board_id = cur.lastrowid
            for i, col_title in enumerate(DEFAULT_COLUMNS):
                conn.execute(
                    "INSERT INTO columns (board_id, title, position) VALUES (?, ?, ?)",
                    (board_id, col_title, i),
                )
    return {"id": f"board-{board_id}", "title": title}


def rename_board(user_id: int, board_id: int, title: str) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_board(conn, user_id, board_id):
                return False
            conn.execute("UPDATE boards SET title = ? WHERE id = ?", (title, board_id))
    return True


def delete_board(user_id: int, board_id: int) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_board(conn, user_id, board_id):
                return False
            conn.execute("DELETE FROM boards WHERE id = ?", (board_id,))
    return True


def ensure_user_board(user_id: int) -> int:
    with get_db() as conn:
        with conn:
            board = conn.execute("SELECT id FROM boards WHERE user_id = ?", (user_id,)).fetchone()
            if board:
                return board["id"]
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
    return board_id


# --- Board data retrieval ---


def get_board(board_id: int) -> dict:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT col.id AS col_id, col.title AS col_title, col.position AS col_position,
                   c.id AS card_id, c.title AS card_title, c.details, c.description,
                   c.due_date, c.priority, c.position AS card_position
            FROM columns col
            LEFT JOIN cards c ON c.column_id = col.id
            WHERE col.board_id = ?
            ORDER BY col.position, c.position
            """,
            (board_id,),
        ).fetchall()

        # Fetch all card-label associations for this board in one query
        label_rows = conn.execute(
            """
            SELECT cl.card_id, l.id AS label_id, l.name, l.color
            FROM card_labels cl
            JOIN labels l ON cl.label_id = l.id
            JOIN cards c ON cl.card_id = c.id
            JOIN columns col ON c.column_id = col.id
            WHERE col.board_id = ?
            ORDER BY l.id
            """,
            (board_id,),
        ).fetchall()

    # Build card_id -> labels mapping
    card_labels: dict[int, list[dict]] = {}
    for lr in label_rows:
        card_labels.setdefault(lr["card_id"], []).append({
            "id": f"label-{lr['label_id']}",
            "name": lr["name"],
            "color": lr["color"],
        })

    columns = []
    cards = {}
    current_col_id = None
    current_col = None
    for row in rows:
        if row["col_id"] != current_col_id:
            current_col_id = row["col_id"]
            current_col = {"id": f"col-{row['col_id']}", "title": row["col_title"], "cardIds": []}
            columns.append(current_col)
        if row["card_id"] is not None:
            card_id_str = f"card-{row['card_id']}"
            current_col["cardIds"].append(card_id_str)
            cards[card_id_str] = {
                "id": card_id_str,
                "title": row["card_title"],
                "details": row["details"],
                "description": row["description"],
                "due_date": row["due_date"],
                "priority": row["priority"],
                "labels": card_labels.get(row["card_id"], []),
            }

    return {"columns": columns, "cards": cards}


# --- Ownership checks ---


def _owns_column(conn: sqlite3.Connection, board_id: int, column_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM columns WHERE id = ? AND board_id = ?",
        (column_id, board_id),
    ).fetchone()
    return row is not None


def _owns_card(conn: sqlite3.Connection, board_id: int, card_id: int) -> bool:
    row = conn.execute(
        "SELECT c.id FROM cards c JOIN columns col ON c.column_id = col.id "
        "WHERE c.id = ? AND col.board_id = ?",
        (card_id, board_id),
    ).fetchone()
    return row is not None


def _owns_label(conn: sqlite3.Connection, board_id: int, label_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM labels WHERE id = ? AND board_id = ?",
        (label_id, board_id),
    ).fetchone()
    return row is not None


# --- Card CRUD ---


def add_card(
    board_id: int,
    column_id: int,
    title: str,
    details: str,
    description: str = "",
    due_date: str | None = None,
    priority: str = "medium",
) -> dict | None:
    with get_db() as conn:
        with conn:
            if not _owns_column(conn, board_id, column_id):
                return None
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) as m FROM cards WHERE column_id = ?",
                (column_id,),
            ).fetchone()["m"]
            cur = conn.execute(
                "INSERT INTO cards (column_id, title, details, description, due_date, priority, position) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (column_id, title, details, description, due_date, priority, max_pos + 1),
            )
            card_id = cur.lastrowid
    return {
        "id": f"card-{card_id}",
        "title": title,
        "details": details,
        "description": description,
        "due_date": due_date,
        "priority": priority,
        "labels": [],
    }


def update_card(
    board_id: int,
    card_id: int,
    title: str,
    details: str,
    description: str = "",
    due_date: str | None = None,
    priority: str = "medium",
) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_card(conn, board_id, card_id):
                return False
            conn.execute(
                "UPDATE cards SET title = ?, details = ?, description = ?, due_date = ?, priority = ? WHERE id = ?",
                (title, details, description, due_date, priority, card_id),
            )
    return True


def delete_card(board_id: int, card_id: int) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_card(conn, board_id, card_id):
                return False
            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    return True


def move_card(board_id: int, card_id: int, target_column_id: int, position: int) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_card(conn, board_id, card_id):
                return False
            if not _owns_column(conn, board_id, target_column_id):
                return False
            row = conn.execute(
                "SELECT column_id, position FROM cards WHERE id = ?", (card_id,)
            ).fetchone()
            old_column_id = row["column_id"]
            old_pos = row["position"]

            if old_column_id == target_column_id:
                if position == old_pos:
                    return True
                if position > old_pos:
                    conn.execute(
                        "UPDATE cards SET position = position - 1 "
                        "WHERE column_id = ? AND position > ? AND position <= ?",
                        (old_column_id, old_pos, position),
                    )
                else:
                    conn.execute(
                        "UPDATE cards SET position = position + 1 "
                        "WHERE column_id = ? AND position >= ? AND position < ?",
                        (old_column_id, position, old_pos),
                    )
                conn.execute(
                    "UPDATE cards SET position = ? WHERE id = ?",
                    (position, card_id),
                )
            else:
                conn.execute(
                    "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
                    (old_column_id, old_pos),
                )
                conn.execute(
                    "UPDATE cards SET position = position + 1 WHERE column_id = ? AND position >= ?",
                    (target_column_id, position),
                )
                conn.execute(
                    "UPDATE cards SET column_id = ?, position = ? WHERE id = ?",
                    (target_column_id, position, card_id),
                )
    return True


def rename_column(board_id: int, column_id: int, title: str) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_column(conn, board_id, column_id):
                return False
            conn.execute("UPDATE columns SET title = ? WHERE id = ?", (title, column_id))
    return True


# --- Labels ---


def get_labels(board_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, color FROM labels WHERE board_id = ? ORDER BY id",
            (board_id,),
        ).fetchall()
    return [{"id": f"label-{r['id']}", "name": r["name"], "color": r["color"]} for r in rows]


def create_label(board_id: int, name: str, color: str) -> dict:
    with get_db() as conn:
        with conn:
            cur = conn.execute(
                "INSERT INTO labels (board_id, name, color) VALUES (?, ?, ?)",
                (board_id, name, color),
            )
            label_id = cur.lastrowid
    return {"id": f"label-{label_id}", "name": name, "color": color}


def update_label(board_id: int, label_id: int, name: str, color: str) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_label(conn, board_id, label_id):
                return False
            conn.execute(
                "UPDATE labels SET name = ?, color = ? WHERE id = ?",
                (name, color, label_id),
            )
    return True


def delete_label(board_id: int, label_id: int) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_label(conn, board_id, label_id):
                return False
            conn.execute("DELETE FROM labels WHERE id = ?", (label_id,))
    return True


def add_label_to_card(board_id: int, card_id: int, label_id: int) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_card(conn, board_id, card_id):
                return False
            if not _owns_label(conn, board_id, label_id):
                return False
            try:
                conn.execute(
                    "INSERT INTO card_labels (card_id, label_id) VALUES (?, ?)",
                    (card_id, label_id),
                )
            except sqlite3.IntegrityError:
                pass  # Already assigned
    return True


def remove_label_from_card(board_id: int, card_id: int, label_id: int) -> bool:
    with get_db() as conn:
        with conn:
            if not _owns_card(conn, board_id, card_id):
                return False
            conn.execute(
                "DELETE FROM card_labels WHERE card_id = ? AND label_id = ?",
                (card_id, label_id),
            )
    return True
