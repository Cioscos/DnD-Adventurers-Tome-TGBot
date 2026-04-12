# Deploy Checklist — D&D Bot Mini App Migration

## Prerequisites

- [ ] Raspberry Pi running the existing Telegram bot
- [ ] Cloudflare account (free tier is fine)
- [ ] Domain name OR use `trycloudflare.com` free subdomain

---

## Step 1 — Cloudflare Tunnel (HTTPS for FastAPI)

On the Raspberry Pi:

```bash
# Install cloudflared
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb

# Authenticate (opens a browser link — paste it on your desktop)
cloudflared login

# Create tunnel
cloudflared tunnel create dnd-api
# This prints a UUID. Note it — you'll need it in the config below.

# Create config file
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: dnd-api
credentials-file: /home/<YOUR_USER>/.cloudflared/<TUNNEL_UUID>.json
ingress:
  - hostname: api.yourdomain.com      # change to your domain
    service: http://localhost:8000
  - service: http_status:404
EOF

# Route DNS (creates a CNAME in Cloudflare DNS automatically)
cloudflared tunnel route dns dnd-api api.yourdomain.com

# Install as systemd service (auto-starts on boot)
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

**No domain?** Use a free temporary tunnel (does NOT persist across restarts):
```bash
cloudflared tunnel --url http://localhost:8000
# Prints a random *.trycloudflare.com URL — use that as VITE_API_BASE_URL for testing
```

---

## Step 2 — FastAPI systemd service

```bash
# Copy service file (already created at api/dnd-api.service)
sudo cp api/dnd-api.service /etc/systemd/system/dnd-api.service

# Edit it to set the correct WorkingDirectory and user
sudo nano /etc/systemd/system/dnd-api.service

# Install dependencies (same venv as bot, or a separate one)
pip install -r api/requirements.txt

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable dnd-api
sudo systemctl start dnd-api

# Check status
sudo systemctl status dnd-api
journalctl -u dnd-api -f
```

---

## Step 3 — Environment variables

Update `.env` on the Raspberry Pi:

```dotenv
BOT_TOKEN=<your bot token>
DEV_CHAT_ID=<your chat id>
WEBAPP_URL=https://cioscos.github.io/dnd_bot_revamped/app/
```

---

## Step 4 — Register Mini App with BotFather

In Telegram, message `@BotFather`:

1. `/newapp`
2. Select your bot
3. Title: `D&D Character Sheet` (or any name)
4. Description: short description
5. Photo: 640×360 PNG (optional)
6. Demo GIF: skip
7. Web App URL: `https://cioscos.github.io/dnd_bot_revamped/app/`

After registration the Mini App can be opened via the reply keyboard button `/start` sends.

---

## Step 5 — GitHub Actions secret

In the GitHub repo settings → **Secrets and variables → Actions**, add:

| Secret name | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://api.yourdomain.com` |

This is used by `.github/workflows/deploy-webapp.yml` when building the React app.

---

## Step 6 — Initial React build

```bash
# On your development machine
cd webapp
npm install
echo "VITE_API_BASE_URL=https://api.yourdomain.com" > .env.local
npm run build        # outputs to docs/app/
```

Then commit and push `docs/app/` to trigger GitHub Pages deployment:

```bash
git add docs/app
git commit -m "chore: initial React Mini App build"
git push origin main
```

After this, GitHub Actions will rebuild automatically on every push to `main` that touches `webapp/`.

---

## Step 7 — GitHub Pages settings

In the GitHub repo settings → **Pages**:
- Source: **Deploy from a branch**
- Branch: `main` / `docs`

The Mini App will be live at `https://cioscos.github.io/dnd_bot_revamped/app/`.

---

## Step 8 — End-to-end verification

1. Open Telegram → `/start` → confirm the reply keyboard shows the character sheet button
2. Tap the button → Mini App opens in Telegram's built-in browser
3. Create a character → it appears in the list
4. Modify HP → check the value persists after closing and reopening
5. Roll a die → tap "Send to chat" → result appears as a Telegram message
6. `/wiki` → navigation still works
7. In a group: `/party` → party message still works
8. Verify FastAPI health: `curl https://api.yourdomain.com/health`

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Mini App button missing | `WEBAPP_URL` not set in `.env` | Set it and restart bot |
| Mini App opens blank | Vite `base` path wrong | Check `vite.config.ts`: `base: '/dnd_bot_revamped/app/'` |
| API 403 errors | `initData` expired or wrong | Ensure system clock on Pi is accurate (`timedatectl`) |
| API CORS error | Origin not allowed | Check `allow_origins` in `api/main.py` |
| `sendData` not working | Mini App opened via inline button | Must be opened via `KeyboardButton.web_app` (reply keyboard) |
| Maps not loading | Telegram file_id expired | file_ids don't expire but the temp download URL does; proxy re-fetches it each time |
