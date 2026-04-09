# Database

SQLite, stored at `/app/data/kanban.db` inside the Docker container (mounted as a volume for persistence).

## Schema

Four tables: `users`, `boards`, `columns`, `cards`. See [schema.json](schema.json) for the full definition.

```
users 1--* boards 1--* columns 1--* cards
```

- **users** -- one row per user. MVP has only one ("user"), but schema supports multiple.
- **boards** -- one board per user for MVP. Has a title.
- **columns** -- ordered by `position`. Supports any number of columns (MVP starts with 5).
- **cards** -- ordered by `position` within their column. Cascade-deleted when a column is removed.

## ID strategy

Integer auto-increment IDs in the database. The frontend currently uses string IDs (e.g. "card-1", "col-backlog") -- these will be replaced with the integer IDs from the API, converted to strings for React keys.

## Initialization

The database and tables are created automatically on first startup if they don't exist. On first login for a user, if they have no board, a default board is created with 5 columns and no cards.
