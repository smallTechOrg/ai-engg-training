# syntax=docker/dockerfile:1
# ---- build stage: has uv, resolves and installs dependencies ----
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /srv
# Dependency files first: this layer is rebuilt only when dependencies change.
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev
# Application code last: a code edit only rebuilds from here.
COPY app ./app

# ---- runtime stage: no uv, no build tools, non-root ----
FROM python:3.12-slim AS runtime
RUN useradd --system --create-home --uid 10001 appuser
WORKDIR /srv
COPY --from=build --chown=appuser:appuser /srv /srv
ENV PATH="/srv/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=2)"
# Exec form: uvicorn is PID 1 and receives SIGTERM for a graceful shutdown.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
