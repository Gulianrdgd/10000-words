FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /srv

# dependencies first, so app edits don't invalidate the layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

# writable state (SQLite DB + VAPID key) lives on a volume; words.json ships
# inside app/data and is read from there
ENV DATA_DIR=/data
ENV PATH="/srv/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
