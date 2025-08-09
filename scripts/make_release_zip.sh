#!/usr/bin/env bash
set -euo pipefail
ZIP_NAME="${1:-marketplace-dockerized.zip}"
cd "$(dirname "$0")/.."
zip -r "$ZIP_NAME" . \
  -x ".git/*" \
  -x ".env" \
  -x ".env.*" \
  -x "**/__pycache__/*" \
  -x "**/*.pyc" \
  -x "**/.pytest_cache/*" \
  -x "**/.mypy_cache/*" \
  -x "**/node_modules/*" \
  -x "logs/*" \
  -x "volumes/*" \
  -x "**/*.sqlite3" \
  -x "**/.DS_Store"
sha256sum "$ZIP_NAME" || shasum -a 256 "$ZIP_NAME" || true
