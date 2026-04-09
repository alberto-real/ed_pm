FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv

WORKDIR /app

COPY backend/pyproject.toml backend/
RUN cd backend && uv sync --no-dev

COPY backend/ backend/

COPY --from=frontend-build /app/frontend/.next/standalone/. frontend/
COPY --from=frontend-build /app/frontend/.next/static frontend/.next/static
COPY --from=frontend-build /app/frontend/public frontend/public

COPY scripts/entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
