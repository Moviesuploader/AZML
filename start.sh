#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
export PORT="${PORT:-85}"

# Compose injects .env values through env_file. Keep local/Procfile support too.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source ./.env
  set +a
fi

# Never delete Telegram session files during startup. Session state belongs to
# the bot owner and must survive restarts and container recreation.
python3 update.py
exec python3 -m bot
