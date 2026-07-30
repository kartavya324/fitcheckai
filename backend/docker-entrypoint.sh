#!/usr/bin/env bash
# Prod entrypoint: apply DB migrations, then serve.
set -euo pipefail

# Bring the database schema up to date (no-op if already current). Safe to run
# on every boot; this is the source of truth for Postgres in prod.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running database migrations (alembic upgrade head)..."
  alembic upgrade head
fi

# gunicorn with uvicorn workers — real prod server (replaces `uvicorn --reload`,
# which caused the dev stale-process issues). Tune workers via WEB_CONCURRENCY.
exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_CONCURRENCY:-2}" \
  --bind "0.0.0.0:${PORT:-8001}" \
  --timeout "${WEB_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
