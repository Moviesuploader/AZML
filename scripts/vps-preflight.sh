#!/usr/bin/env bash
# Read-only deployment preflight. Does not start, stop, or modify containers.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

fail() { echo "PREFLIGHT FAIL: $*" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || fail "Docker CLI is missing"
docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable to this user"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f docker-compose.yml)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose -f docker-compose.yml)
else
  fail "Install Docker Compose plugin or docker-compose v1"
fi

[[ -f .env ]] || fail "Missing private .env file. Copy .env.example to .env and fill it locally."
chmod 600 .env 2>/dev/null || true

for key in BOT_TOKEN OWNER_ID TELEGRAM_API TELEGRAM_HASH; do
  grep -Eq "^[[:space:]]*${key}[[:space:]]*=[[:space:]]*[^#[:space:]]" .env || fail "Required .env key is empty or missing: ${key}"
done

"${COMPOSE[@]}" config >/dev/null || fail "docker-compose.yml or .env validation failed"
command -v git >/dev/null 2>&1 || fail "Git is missing"
command -v curl >/dev/null 2>&1 || fail "curl is missing"

echo "PREFLIGHT PASS"
docker --version
"${COMPOSE[@]}" version 2>/dev/null || true
df -h .
echo "No containers were started or stopped."
