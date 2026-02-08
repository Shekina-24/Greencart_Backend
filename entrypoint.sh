#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting app..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:${PORT:-8000} \
  --workers 2
