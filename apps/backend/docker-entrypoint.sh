#!/bin/sh
set -e
cd /app

if [ "${SKIP_ALEMBIC_UPGRADE:-0}" != "1" ]; then
  echo "[docker-entrypoint] Running Alembic migrations..."
  alembic -c migrations/alembic.ini upgrade head
fi

exec "$@"
