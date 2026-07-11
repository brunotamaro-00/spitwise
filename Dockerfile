# --- Stage 1: frontend (Vite build) ---
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend (runtime) ---
FROM python:3.12-slim
WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend
COPY --from=frontend /fe/dist ./frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
# Migraciones en el arranque + UN solo worker (locks por chat en proceso).
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
