FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm libcairo2-dev libpango1.0-dev libgdk-pixbuf-2.0-dev libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY backend/ ./backend/
RUN mkdir -p backend/static && cp -r frontend/dist/* backend/static/

WORKDIR /app/backend

CMD ["sh", "-c", "exec gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT"]
