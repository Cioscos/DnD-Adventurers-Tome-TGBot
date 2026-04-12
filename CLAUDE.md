# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
# Uses uv (not pip). Install uv: https://docs.astral.sh/uv/
uv sync
# Create .env with BOT_TOKEN (required), DEV_CHAT_ID (optional), DB_PATH (optional), WEBAPP_URL (required for Mini App button)
uv run python -m bot.main
```

## Running the API

```bash
# From repo root (same venv as bot — all deps in pyproject.toml)
uv sync
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

## Running the Frontend (dev)

```bash
cd webapp
npm install
# Create webapp/.env.local with VITE_API_BASE_URL=http://localhost:8000
# (use printf to avoid UTF-16 encoding issues on Windows: printf 'VITE_API_BASE_URL=http://localhost:8000\n' > .env.local)
npm run dev
```

## Deploy (Raspberry Pi)

```bash
# One-shot deploy — stops 3 services, git pull, uv sync, restarts
./deploy/deploy.sh
```

Services managed: `dnd_bot.service`, `dnd-api.service`, `cloudflared.service`

Service files: `api/dnd-api.service`, `deploy/cloudflared.service`
Pi user: `cioscospi` | Project path: `/home/cioscospi/Programs/dnd_bot_revamped`

### Cloudflare Tunnel
Persistent named tunnel `dnd-api` → exposed at **`https://api.cischi.dev`**
One-time setup script: `deploy/setup-cloudflare-tunnel.sh`

No test suite or linter is configured.

## Architecture Overview

Three-component system:

1. **Telegram Bot** (`bot/`) — handles `/start`, `/wiki`, `/party`, `/party_stop`. Character management has moved to the Mini App. Entry point: `bot/main.py`.
2. **FastAPI Backend** (`api/`) — REST API for all character CRUD, shared SQLite DB with the bot. Runs on the same machine (Raspberry Pi), exposed via Cloudflare Tunnel.
3. **React Mini App** (`webapp/`) — Telegram Mini App (WebApp) for full character sheet management. Builds to `docs/app/`, served by GitHub Pages.

### Bot commands
- `/start` — private chat; shows persistent reply keyboard with Mini App button + wiki inline button
- `/wiki` — private chat; inline navigation over D&D 5e GraphQL API
- `/party`, `/party_stop` — group chat; live party status message
- `web_app_data` — receives `sendData()` payloads from Mini App (dice roll results → posted to chat)

### Mini App URL
`https://cioscos.github.io/DnD-Adventurers-Tome-TGBot/app/` (HashRouter, built to `docs/app/`)

## Navigation Model

Two frozen dataclasses drive callback state via PTB's `arbitrary_callback_data` (LRU cache):

| Dataclass | File | Used for |
|---|---|---|
| `NavAction` | `bot/models/state.py` | Wiki navigation callbacks |
| `PartyAction` | `bot/models/party_state.py` | Party session callbacks |

**Handler registration order in `main.py`**: Party `CallbackQueryHandler` first, then Wiki `CallbackQueryHandler`. Wiki handler pattern: `lambda d: not isinstance(d, PartyAction)`.

## Key Patterns

### Adding a New Wiki Category

1. Add a `MenuCategory(type_name, label, emoji)` to `MENU_CATEGORIES` in `bot/schema/registry.py`.
2. Optionally add a `_format_<type>()` function in `bot/handlers/navigation.py` and register it in `_FORMATTERS`. Without one, the generic formatter applies.

### Adding a New API Endpoint

1. Create/extend a router in `api/routers/`.
2. Add Pydantic schemas in `api/schemas/`.
3. Use `user_id: int = Depends(get_current_user)` for auth — every endpoint must verify ownership.
4. Register the router in `api/main.py` with the correct prefix.

### Adding a New Mini App Page

1. Create `webapp/src/pages/<PageName>.tsx`.
2. Add a route in `webapp/src/App.tsx`.
3. Add API calls via `api` object from `webapp/src/api/client.ts`.
4. Add i18n keys to `webapp/src/locales/it.json` and `en.json`.

## Coding Conventions

### Bot
- **Async only** — use the python-telegram-bot v20+ async API throughout.
- **GraphQL queries** — always generated dynamically via `bot/api/query_builder.py`; never hardcode query strings.
- **HTTP client** — use the `DnDClient` singleton from `bot/api/client.py` (`httpx.AsyncClient`).
- **Database sessions** — always `async with get_session() as session:` from `bot/db/engine.py`; never instantiate a session directly.
- **MarkdownV2 escaping** — use `_esc()` from `navigation.py` for wiki output. Condition description strings in YAML are **pre-escaped** — do not pass them through `_esc()` again.
- **Plain text surfaces** — inline keyboard button labels and `callback_query.answer()` toast messages are **plain text only**.
- **i18n** — call `lang = get_lang(update)` at the top of every handler. Use `translator.t("key", lang=lang)` for all strings; never hardcode text. Default language is `"it"`.
- **Logging** — use `logging` module; never `print()`.
- **Type hints** — required on all function signatures.
- **Chat-type guards** — `/start` is private-chat only; `/party`/`/party_stop` are group-only.

### API
- **Auth** — every endpoint uses `Depends(get_current_user)` from `api/auth.py`. Never trust user-supplied IDs; always filter by the authenticated `user_id`.
- **Ownership check** — `_get_owned(session, Model, id, user_id)` raises 404/403 appropriately.
- **Async SQLAlchemy** — use `AsyncSession` from `api/database.py`; never sync sessions.

### Frontend
- **Auth header** — every API call includes `X-Telegram-Init-Data` header (handled by `api/client.ts`).
- **Routing** — `HashRouter` only; GitHub Pages cannot serve server-side routes.
- **State** — TanStack Query for server data, Zustand for `activeCharId` and `locale`.
- **sendData** — only call `window.Telegram.WebApp.sendData()` for actions that should post to Telegram chat (e.g. dice results). The Mini App closes after `sendData`.

## Persistence

- **Character DB**: SQLite at `data/dnd_bot.db` (override via `DB_PATH`). Shared between bot and API. Schema migrations run idempotently via `ALTER TABLE` in `_migrate_schema()` in `bot/db/engine.py` on every startup. Always add new columns to `_MIGRATIONS` — never rely solely on `create_all`.
- **Bot state**: `data/persistence.pkl` — stores `user_data` and callback LRU cache across restarts.

## i18n

### Bot
- Locale files: `bot/locales/it.yaml` (default) and `bot/locales/en.yaml`.
- `Translator` singleton in `bot/utils/i18n.py` with a hot-reload watcher.
- Language detected from `update.effective_user.language_code`.

### Frontend
- Locale files: `webapp/src/locales/it.json` (default) and `en.json`.
- Language detected from `window.Telegram.WebApp.initDataUnsafe.user.language_code`.

## GitHub Pages

`docs/` contains a Jekyll site at `https://cioscos.github.io/DnD-Adventurers-Tome-TGBot`. The `docs/app/` directory is the React build output — **not** excluded from Jekyll (static files are copied as-is). Always use `{{ '/path' | relative_url }}` for Jekyll asset/internal links.

The GitHub Actions workflow `.github/workflows/deploy-webapp.yml` runs a build check on `webapp/**` changes (supports `workflow_dispatch` for manual trigger). The `docs/app/` build output must be committed manually to the branch before merging, as direct pushes to `main` are blocked by branch protection (free plan — no bypass available).

**To update the webapp:**
1. Update `webapp/.env.local` if needed (`VITE_API_BASE_URL=https://api.cischi.dev`)
2. `cd webapp && npm run build` → outputs to `docs/app/`
3. `git add docs/app/ && git commit -m "chore: update webapp build"`
4. Push branch → open PR → merge → Pages redeploys automatically

GitHub Secret `VITE_API_BASE_URL` must be kept in sync with the tunnel URL (`https://api.cischi.dev`) for CI builds.

# General rules

1. Always ask for clarification if the user's request is ambiguous or incomplete. Never make assumptions about what they want.
2. Always work on a feature branch, never directly on main.
3. Use Context7 MCP server when it makes sense.
