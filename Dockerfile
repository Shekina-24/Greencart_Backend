# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /code

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Railway fournit PORT
ENV PORT=8000

# Start with gunicorn + uvicorn worker
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT} --workers 3"]
