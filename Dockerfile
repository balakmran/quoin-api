# Stage 1: Builder
FROM python:3.14-slim-bookworm AS builder

# Pin the uv build tool to a released version AND its manifest digest
# for byte-for-byte reproducible builds. The tag is kept alongside the
# digest so Dependabot's docker ecosystem still bumps both together.
COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /bin/uv

WORKDIR /app

# Install dependencies
# --no-dev: Production dependencies only
# --frozen: Sync with uv.lock (if available), otherwise pyproject.toml
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --no-dev --frozen

# Stage 2: Final
FROM python:3.14-slim-bookworm

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app/ app/

# Copy alembic for database migrations
COPY alembic/ alembic/
COPY alembic.ini .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Create a non-root user
RUN addgroup --system --gid 1001 quoin && \
    adduser --system --uid 1001 --ingroup quoin quoin

# Set ownership of the application directory
RUN chown -R quoin:quoin /app

# Switch to non-root user
USER quoin

# Liveness check hitting the /health endpoint. Uses the stdlib
# (curl/wget are not in the slim image) and the venv's Python on PATH.
# start-period covers app boot; a non-200 or exception exits non-zero.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status == 200 else 1)"]

# Run the application
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
