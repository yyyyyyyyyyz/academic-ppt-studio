#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only origin main
docker compose up -d --build --remove-orphans
docker image prune -f
echo "Academic PPT Studio updated and running on port 80."
