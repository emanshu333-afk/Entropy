# Bunkloop production Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for Pillow and Postgres
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static (will also run via entrypoint, but bake for image)
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Healthcheck hits the Django health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health/').read().find(b'ok')!=-1 else 1)" || exit 1

# Use Daphne for ASGI (Channels/WebSocket) per plan §28; binds 0.0.0.0 for Docker
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "entropy.asgi:application"]
