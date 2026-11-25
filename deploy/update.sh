#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only origin main
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  COMPOSE_CMD="docker-compose"
fi
$COMPOSE_CMD up -d --build --remove-orphans
docker image prune -f
echo "Academic PPT Studio updated and running on port 80."
