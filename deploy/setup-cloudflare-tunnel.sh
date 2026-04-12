#!/usr/bin/env bash
# One-time setup for a persistent Cloudflare Tunnel on Raspberry Pi.
#
# Prerequisites:
#   - A free Cloudflare account (cloudflare.com)
#   - cloudflared installed (see step 1 below)
#
# This creates a NAMED tunnel (not the temporary trycloudflare.com one).
# The tunnel URL is stable across restarts.
#
# Two options:
#   A) Zero Trust (recommended, no domain needed) → stable *.cfargotunnel.com URL
#   B) Named tunnel with custom domain
#
# ============================================================
# OPTION A — Zero Trust (no domain, free)
# ============================================================
# 1. Go to https://one.dash.cloudflare.com → Networks → Tunnels → Create a tunnel
# 2. Choose "Cloudflared" as connector
# 3. Name the tunnel (e.g., "dnd-api")
# 4. Under "Install and run a connector" → Linux → copy the token shown
# 5. Run:
#      sudo cloudflared service install <YOUR_TOKEN_HERE>
#      sudo systemctl enable cloudflared
#      sudo systemctl start cloudflared
# 6. Back in the dashboard, under "Public Hostname", add:
#      Subdomain: (leave empty or pick one)   Domain: <your-uuid>.cfargotunnel.com
#      Service: http://localhost:8000
# 7. Copy the public URL → set VITE_API_BASE_URL in webapp/.env.local
#    and CLOUDFLARE_TUNNEL_URL in .env on the Pi.
#
# ============================================================
# OPTION B — Named tunnel with custom domain
# ============================================================
# 1. Install cloudflared:
set -euo pipefail

TUNNEL_NAME="dnd-api"
API_PORT="8000"

echo ""
echo "==> Step 1: Installing cloudflared"
echo "    Detecting architecture..."
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv6l" ]; then
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm"
else
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
fi

if command -v cloudflared &>/dev/null; then
    echo "    cloudflared already installed: $(cloudflared --version)"
else
    echo "    Downloading cloudflared for $ARCH..."
    curl -L --output /tmp/cloudflared "$CLOUDFLARED_URL"
    sudo install -o root -g root -m 0755 /tmp/cloudflared /usr/local/bin/cloudflared
    echo "    Installed: $(cloudflared --version)"
fi

echo ""
echo "==> Step 2: Logging in to Cloudflare"
echo "    This will open a browser. Authorize the domain you want to use."
echo "    (Press Enter to continue, then follow the browser prompt)"
read -r
cloudflared login

echo ""
echo "==> Step 3: Creating named tunnel: $TUNNEL_NAME"
if cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    echo "    Tunnel '$TUNNEL_NAME' already exists, skipping creation."
else
    cloudflared tunnel create "$TUNNEL_NAME"
fi

echo ""
echo "==> Step 4: Creating tunnel config at ~/.cloudflared/config.yml"
TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
if [ -z "$TUNNEL_ID" ]; then
    echo "ERROR: Could not find tunnel ID for '$TUNNEL_NAME'."
    exit 1
fi

mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: /home/$(whoami)/.cloudflared/${TUNNEL_ID}.json

ingress:
  - service: http://localhost:${API_PORT}
EOF

echo "    Config written to ~/.cloudflared/config.yml"
echo "    Tunnel ID: $TUNNEL_ID"

echo ""
echo "==> Step 5: Route DNS (only needed if you have a custom domain on Cloudflare)"
echo "    To add a custom hostname, run:"
echo "      cloudflared tunnel route dns $TUNNEL_NAME api.yourdomain.com"
echo "    Or use a free cfargotunnel.com URL (already stable without DNS routing)."

echo ""
echo "==> Step 6: Install cloudflared as systemd service"
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

echo ""
echo "==> Step 7: Get your tunnel URL"
echo "    Your stable tunnel URL is:"
echo "      https://${TUNNEL_ID}.cfargotunnel.com"
echo ""
echo "    Update your .env on the Pi:"
echo "      CLOUDFLARE_TUNNEL_URL=https://${TUNNEL_ID}.cfargotunnel.com"
echo ""
echo "    And add the GitHub secret for the webapp build:"
echo "      VITE_API_BASE_URL=https://${TUNNEL_ID}.cfargotunnel.com"
echo ""
echo "==> Cloudflare Tunnel setup complete."
