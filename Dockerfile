FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# Dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY gitgoblin ./gitgoblin
RUN uv sync --frozen --no-dev

# Drop root: files stay root-owned and read-only to the app user.
RUN useradd --system --no-create-home --uid 10001 gitgoblin
USER gitgoblin

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn gitgoblin.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
