FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY . .

RUN uv sync --frozen --no-dev

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
