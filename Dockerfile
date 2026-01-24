FROM python:3.11-slim-bookworm

# Install system dependencies including FFmpeg for video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    libcairo2-dev libpango1.0-dev libgdk-pixbuf-2.0-dev libffi-dev shared-mime-info \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
RUN mkdir -p backend/static && cp -r frontend/dist/* backend/static/

WORKDIR /app/backend

ENV PORT=8000

CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 30
