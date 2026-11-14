#!/usr/bin/env bash
# Docker Compose compatibility wrapper for Debian/Ubuntu VPS and SSHX shells.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if docker compose version >/dev/null 2>&1; then
  exec docker compose -f docker-compose.yml "$@"
elif command -v docker-compose >/dev/null 2>&1; then
  exec docker-compose -f docker-compose.yml "$@"
else
  echo "ERROR: Docker Compose not found (need 'docker compose' plugin or 'docker-compose')." >&2
  exit 1
fi
