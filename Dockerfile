# Stage 1: Builder
# Images are pinned by tag AND digest for reproducible builds. The tag is
# kept so Dependabot's docker ecosystem still bumps both together.
FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS builder

# The workflows install this same uv version (see test_tool_pins.py).
COPY --from=ghcr.io/astral-sh/uv:0.12.17@sha256:10787c682e4184e4f290de1171fd4703dc63de99221f10fe1c99002ce7fa9acc /uv /bin/uv

WORKDIR /app

# Install dependencies
# --no-dev: Production dependencies only
# --frozen: Sync with uv.lock (if available), otherwise pyproject.toml
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --no-dev --frozen

# Stage 2: Final
FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f

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
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --ingroup appuser appuser

# Set ownership of the application directory
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Liveness check hitting the /health endpoint. Uses the stdlib
# (curl/wget are not in the slim image) and the venv's Python on PATH.
# start-period covers app boot; a non-200 or exception exits non-zero.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status == 200 else 1)"]

# Run the application
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
