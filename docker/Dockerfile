FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

WORKDIR /app

COPY . .

RUN uv sync --frozen --no-dev

EXPOSE 8000

HEALTHCHECK --start-period=10s --interval=1m --timeout=3s \
  CMD uv run /app/docker/healthcheck.py

ENTRYPOINT ["/app/docker/entrypoint.sh"]
