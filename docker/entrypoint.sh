#!/bin/sh

set -e

CERT_DIR="${CHITAI_CERT_DIR:-/app/data/certs}"

if [ ! -f "$CERT_DIR/cert.pem" ] || [ ! -f "$CERT_DIR/key.pem" ]; then
  echo "Generating self-signed SSL certificate..."
  /app/docker/generate-cert.sh
fi

echo "Running database migrations..."
uv run alembic upgrade head

exec uv run main.py
