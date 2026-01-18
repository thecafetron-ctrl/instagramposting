FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY frontend/ ./frontend/
RUN cd frontend && npm install && npm run build

COPY backend/ ./backend/

RUN pip install --no-cache-dir -r backend/requirements.txt

RUN mkdir -p backend/static && cp -r frontend/dist/* backend/static/

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
