#!/usr/bin/env bash
# One-command bring-up: checks prerequisites, configures, builds, starts,
# waits for health, and prints the console URL.
set -euo pipefail

cd "$(dirname "$0")/.."

say()  { printf '\033[1;33m▸\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Prerequisites
command -v docker >/dev/null 2>&1 || fail "Docker is required: https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required (ships with Docker Desktop)"
docker info >/dev/null 2>&1 || fail "Docker daemon is not running - start Docker and retry"

# 2. Configuration (defaults need no API keys)
if [ ! -f .env ]; then
  cp .env.example .env
  say "Created .env from .env.example (zero-key defaults: local embeddings)"
else
  say "Using existing .env"
fi

GATEWAY_PORT=$(grep -E '^GATEWAY_HOST_PORT=' .env | tail -1 | cut -d= -f2)
GATEWAY_PORT=${GATEWAY_PORT:-8000}

# 3. Build and start
say "Building and starting the stack (first build takes a few minutes)..."
docker compose up --build -d

# 4. Wait for every service to report healthy through the gateway
say "Waiting for all services to become healthy..."
for _ in $(seq 1 60); do
  status=$(curl -fs "http://localhost:${GATEWAY_PORT}/healthz" 2>/dev/null \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])' 2>/dev/null || echo starting)
  if [ "$status" = "ok" ]; then
    echo
    say "All services healthy."
    say "Web console:  http://localhost:${GATEWAY_PORT}"
    say "API docs:     http://localhost:${GATEWAY_PORT}/docs"
    say "Stop with:    make down"
    exit 0
  fi
  sleep 2
done

printf '\n'
fail "Stack did not become healthy in 120s. Inspect with: docker compose ps && docker compose logs --tail=50"
