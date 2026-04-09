#!/usr/bin/env bash
set -e

# Start Next.js on port 3000 (internal only)
cd /app/frontend
HOSTNAME=127.0.0.1 PORT=3000 node server.js &

# Wait for Next.js to be ready
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:3000/ > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Start FastAPI on port 8000 (exposed)
cd /app
exec uv run --project backend uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir backend
