#!/bin/bash
# WanderGuard — Hetzner deployment script
# Run on the server after: git pull origin main
set -e

echo "==> Pulling latest images / rebuilding..."
docker compose build --pull

echo "==> Stopping old containers..."
docker compose down --remove-orphans

echo "==> Starting services..."
docker compose up -d

echo "==> Waiting for web container to be healthy..."
sleep 5
docker compose ps

echo "==> Tailing logs (Ctrl+C to exit)..."
docker compose logs -f web celery
