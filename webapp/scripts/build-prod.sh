#!/usr/bin/env bash
# build-prod.sh
# Builds the webapp for production and stages docs/app/ ready to commit.
# Usage: npm run build:prod   (from the webapp/ directory)
#        bash scripts/build-prod.sh

set -euo pipefail

WEBAPP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$WEBAPP_DIR/.." && pwd)"
ENV_FILE="$WEBAPP_DIR/.env.local"
PROD_URL="https://api.cischi.dev"
DEV_URL="http://localhost:8000"

# --- restore local URL on exit (even on error) ---
restore_env() {
  printf 'VITE_API_BASE_URL=%s\n' "$DEV_URL" > "$ENV_FILE"
  echo "↩ Restored .env.local → $DEV_URL"
}
trap restore_env EXIT

# 1. Switch to production URL
echo "→ Switching .env.local to production URL ($PROD_URL)..."
printf 'VITE_API_BASE_URL=%s\n' "$PROD_URL" > "$ENV_FILE"

# 2. Build
echo "→ Building webapp..."
cd "$WEBAPP_DIR"
npm run build

# 3. Stage docs/app/ from repo root
echo "→ Staging docs/app/ ..."
cd "$REPO_ROOT"
git add docs/app/

echo ""
echo "✅  Build complete and docs/app/ staged."
echo "    Run:  git commit -m 'chore: update webapp build'"
