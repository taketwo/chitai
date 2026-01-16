#!/bin/sh

set -e

CERT_DIR="${CHITAI_CERT_DIR:-/app/data/certs}"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"

mkdir -p "$CERT_DIR"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "Certificate already exists at $CERT_FILE"
  echo "To regenerate, delete the existing certificate files"
  exit 0
fi

CERT_HOSTS="${CERT_HOSTS:-localhost}"

echo "Generating self-signed certificate for: $CERT_HOSTS"

openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -days 3650 \
  -subj "/CN=chitai/O=Chitai" \
  -addext "subjectAltName=$(echo "$CERT_HOSTS" | sed 's/,/,DNS:/g' | sed 's/\([0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+\)/IP:\1/g' | sed 's/^/DNS:/')"

echo "Certificate generated successfully!"
echo "Certificate: $CERT_FILE"
echo "Private key: $KEY_FILE"
