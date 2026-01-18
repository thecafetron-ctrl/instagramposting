FROM python:3.11-slim-bookworm

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm libcairo2-dev libpango1.0-dev libgdk-pixbuf-2.0-dev libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build frontend
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Install Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy frontend build to backend static
RUN mkdir -p backend/static && cp -r frontend/dist/* backend/static/

# Copy assets
RUN mkdir -p backend/assets
COPY backend/assets/ ./backend/assets/

WORKDIR /app/backend

# Railway sets PORT env var
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
