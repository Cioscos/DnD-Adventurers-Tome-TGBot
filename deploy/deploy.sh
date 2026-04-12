#!/usr/bin/env bash
# Deploy script for dnd_bot_revamped on Raspberry Pi.
# Stops all 3 services, pulls latest code, syncs deps, restarts.
#
# Usage:
#   chmod +x deploy/deploy.sh
#   ./deploy/deploy.sh
set -euo pipefail

PROJECT_DIR="/home/cioscospi/Programs/dnd_bot_revamped"
SERVICES=("dnd_bot.service" "dnd-api.service" "cloudflared.service")

cd "$PROJECT_DIR"

echo "==> Stopping services"
for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc"; then
        sudo systemctl stop "$svc"
        echo "  stopped: $svc"
    else
        echo "  (already stopped: $svc)"
    fi
done

echo "==> Pulling latest code"
git pull

echo "==> Syncing dependencies"
uv sync

echo "==> Starting services"
for svc in "${SERVICES[@]}"; do
    sudo systemctl start "$svc"
done

echo "==> Waiting for services to settle..."
sleep 3

echo "==> Service status"
ALL_OK=true
for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc"; then
        echo "  ✓ $svc"
    else
        echo "  ✗ $svc FAILED"
        ALL_OK=false
    fi
done

if $ALL_OK; then
    echo ""
    echo "==> Deploy complete."
else
    echo ""
    echo "==> Deploy finished with errors. Check logs:"
    for svc in "${SERVICES[@]}"; do
        echo "  journalctl -u $svc -n 20 --no-pager"
    done
    exit 1
fi
