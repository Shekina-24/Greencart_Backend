#!/usr/bin/env sh
set -e

exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:${PORT:-8000} \
  --workers 3
