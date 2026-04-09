## Backend

Python FastAPI application serving as the backend for the Project Management App.

- Entry point: `main.py` defines the FastAPI app
- Package management: uv with `pyproject.toml`
- In production, FastAPI will reverse-proxy to the Next.js frontend and expose `/api/` routes
- `static/` contains temporary hello world HTML (will be removed once Next.js is integrated)
