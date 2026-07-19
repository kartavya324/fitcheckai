#!/usr/bin/env bash
# Start the FastAPI backend API (uploads, jobs, serves avatars at /files).
# Listens on http://127.0.0.1:8001. Windows: use start_backend.bat instead.
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source venv/bin/activate
exec python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
