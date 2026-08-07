# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies for PDF parsing, psycopg builds, and the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# sentence-transformers drags in torch. The default PyPI wheel is the CUDA
# build (~2.5GB) — useless here since embedding runs on CPU. Install the
# CPU-only wheel first so the resolver treats torch as already satisfied.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/data/files

EXPOSE 8000

# Schema bootstrap + server. Overridden by docker-compose `command`.
CMD ["sh", "-c", "python -m scripts.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
