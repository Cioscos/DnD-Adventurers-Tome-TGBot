# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment rule — NEVER run `uv sync` from WSL

The repository lives on a Windows drive (`C:\Users\Claudio\PycharmProjects\dnd_bot_revamped`). The user runs Python commands from **Windows** (PowerShell / native `uv`), so the `.venv` must be created by the Windows `uv`. If you run `uv sync` from inside WSL, the resulting `.venv` contains Linux-only symlinks (e.g. `lib64`) that Windows `uv` cannot remove or reuse — the next `uv run` from Windows fails with:

```
error: failed to remove file `...\.venv\lib64`: Accesso negato. (os error 5)
```

**Rules for Claude Code running inside WSL:**

- Do **NOT** run `uv sync`, `uv run`, `uv venv`, or any command that creates/modifies `.venv` (includes `uv run python ...`, `uv run pytest`, `uv run uvicorn ...`).
- For Python verification, ask the user to run the command in their Windows shell instead — or use an ephemeral throwaway path (e.g. `UV_PROJECT_ENVIRONMENT=/tmp/venv uv sync`) that never touches the repo's `.venv`.
- If `.venv` already got corrupted from a WSL sync, tell the user to clean it with `wsl rm -rf .venv` (or `Remove-Item -Recurse -Force .venv` in PowerShell) and re-run `uv sync` from Windows.

## Running the Bot

```bash
# Uses uv (not pip). Install uv: https://docs.astral.sh/uv/
uv sync
# Create .env with BOT_TOKEN (required), DEV_CHAT_ID (optional), DB_PATH (optional)
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

## Local Development (no Raspberry Pi)

### First-time setup
Make sure `.env` contains `DEV_USER_ID=<your_telegram_id>` and `webapp/.env.local` points to localhost:

```
# .env
DEV_USER_ID=<userID>   # bypasses Telegram auth — your Telegram user ID

# webapp/.env.local
VITE_API_BASE_URL=http://localhost:8000
```

Both files are already configured this way if you cloned the repo and haven't changed them.

### Starting the stack
```bash
# Terminal 1 — FastAPI (port 8000, auto-reload)
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — React dev server (port 5173, HMR)
cd webapp && npm run dev
```

Then open **http://localhost:5173/** in any browser. No Telegram required.

The API creates `data/dnd_bot.db` automatically on first startup (tables are created via `Base.metadata.create_all` **and** schema migrations run via `_migrate_schema`). The bot is optional — you only need it if you're working on bot commands.

---

## Before Committing webapp Changes

When you edit files under `webapp/src/` you must rebuild `docs/app/` before committing, otherwise GitHub Pages will serve a broken or stale build.

**Use the helper script — it handles everything automatically:**

```bash
cd webapp && npm run build:prod
# then:
git add webapp/src/          # (and any other changed source files)
git commit -m "feat: ..."
```

`npm run build:prod` (`webapp/scripts/build-prod.sh`) does in one shot:
1. Switches `.env.local` to the production API URL (`https://api.cischi.dev`)
2. Runs `tsc && vite build` (fails fast on TypeScript errors)
3. Restores `.env.local` to `http://localhost:8000` (even on error, via `trap`)
4. Runs `git add docs/app/` so the build output is staged and ready

Do **not** commit `.env.local` — it is gitignored.

Open a PR from your feature branch → merge → Pages redeploys automatically.

---

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

Four-package system:

1. **Telegram Bot** (`bot/`) — pure D&D 5e wiki navigator over the public GraphQL API. Handles `/start`, `/about`, `/stop`. Does not touch the SQLite DB. Entry point: `bot/main.py`.
2. **FastAPI Backend** (`api/`) — REST API for all character CRUD and game sessions. Owns the SQLite DB lifecycle (create + migrate in `lifespan`). Runs on the Raspberry Pi, exposed via Cloudflare Tunnel.
3. **React Mini App** (`webapp/`) — Telegram Mini App (WebApp) for full character sheet management. Builds to `docs/app/`, served by GitHub Pages.
4. **Shared core** (`core/`) — SQLAlchemy models/engine, static D&D data tables, and helpers used by both `api/` and the bot's deploy scripts. No Telegram- or FastAPI-specific code here.

### Bot commands
- `/start` — private chat; welcome message with an inline button into the wiki (Mini App is opened via the BotFather menu button)
- `/about` — private chat; bot info + website link
- `/stop` — no-op response (kept for UX symmetry when users type it mid-interaction)
- Wiki navigation — inline `CallbackQueryHandler` over `NavAction` payloads; no `/wiki` command, the user enters via the `/start` button

### Mini App URL
`https://cioscos.github.io/DnD-Adventurers-Tome-TGBot/app/` (HashRouter, built to `docs/app/`)

## Navigation Model

Wiki navigation uses PTB's `arbitrary_callback_data` with a single frozen dataclass `NavAction` (`bot/models/state.py`). The whole object is kept in an in-process LRU cache; Telegram only sees the UUID.

The only callback handler is `bot.handlers.wiki.navigation_callback` — see `bot/main.py`.

## Key Patterns

### Adding a New Wiki Category

1. Add a `MenuCategory(type_name, label, emoji)` to `MENU_CATEGORIES` in `bot/schema/registry.py`.
2. Optionally add a `_format_<type>()` function in `bot/handlers/wiki_formatters.py` and register it in `_FORMATTERS`. Without one, the generic formatter applies.

### Adding a New API Endpoint

1. Create/extend a router in `api/routers/`.
2. Add Pydantic schemas in `api/schemas/`.
3. Use `user_id: int = Depends(get_current_user)` for auth — every endpoint must verify ownership.
4. Register the router in `api/main.py` with the correct prefix.
5. For endpoints that return a `Response` subclass (`FileResponse`, `StreamingResponse`), use `response_model=None` and omit the return type annotation — FastAPI cannot introspect these types.
6. For multipart file uploads, use `Form(...)` and `File(...)` parameters — requires `python-multipart` (already in `pyproject.toml`).

### Adding a New Mini App Page

1. Create `webapp/src/pages/<PageName>.tsx`.
2. Add a route in `webapp/src/App.tsx`.
3. Add API calls via `api` object from `webapp/src/api/client.ts`.
4. Add i18n keys to `webapp/src/locales/it.json` and `en.json`.

## Coding Conventions

### Bot
- **Async only** — use the python-telegram-bot v20+ async API throughout.
- **GraphQL queries** — always generated dynamically via `bot/dnd5e/query_builder.py`; never hardcode query strings.
- **HTTP client** — use the `DnDClient` singleton from `bot/dnd5e/client.py` (`httpx.AsyncClient`).
- **No direct DB access** — the bot does not open SQLite sessions. If you need character data in a future bot feature, go through the API rather than importing from `core/db/`.
- **MarkdownV2 escaping** — use `_esc()` from `bot/handlers/wiki_formatters.py` for wiki output.
- **Plain text surfaces** — inline keyboard button labels and `callback_query.answer()` toast messages are **plain text only**.
- **i18n** — call `lang = get_lang(update)` at the top of every handler. Use `translator.t("key", lang=lang)` for all strings; never hardcode text. Default language is `"it"`.
- **Logging** — use `logging` module; never `print()`.
- **Type hints** — required on all function signatures.
- **Chat-type guards** — `/start` is private-chat only.

### API
- **Auth** — every endpoint uses `Depends(get_current_user)` from `api/auth.py`. Never trust user-supplied IDs; always filter by the authenticated `user_id`.
- **Ownership check** — `_get_owned(session, Model, id, user_id)` raises 404/403 appropriately.
- **Async SQLAlchemy** — use `AsyncSession` from `api/database.py`; never sync sessions.

### Frontend
- **Auth header** — every API call includes `X-Telegram-Init-Data` header (handled by `api/client.ts`).
- **Routing** — `HashRouter` only; GitHub Pages cannot serve server-side routes.
- **State** — TanStack Query for server data, Zustand for `activeCharId` and `locale`.
- **sendData** — do **not** use `window.Telegram.WebApp.sendData()`. It only works when the Mini App is opened via a reply keyboard button, which on Telegram Android does not provide `initData` (confirmed: `tgWebAppData` absent from hash, no native bridge events). Use the authenticated API endpoint `POST /characters/{id}/dice/post-to-chat` instead — the bot sends the message directly to the user's private chat via the Telegram Bot API.
- **Multipart uploads** — use the `requestFormData<T>()` helper in `api/client.ts` (does not set `Content-Type`; browser sets it automatically with the correct boundary). Never use the regular `request()` helper for `FormData` payloads.

## Persistence

- **Character DB**: SQLite at `data/dnd_bot.db` (override via `DB_PATH`). Owned by the API. Schema migrations run idempotently via `ALTER TABLE` in `_migrate_schema()` in `core/db/engine.py` and are triggered from the API's `lifespan` hook (`api/main.py`). Always add new columns to `_MIGRATIONS` in `core/db/engine.py` — never rely solely on `create_all`. The Telegram bot does not open a DB connection.
- **Map files**: Uploaded via the webapp are stored locally at `data/maps/{char_id}/{uuid}.{ext}` (up to 10 MB, image/PDF formats). The `Map` model stores the path in `local_file_path`; Telegram-sourced maps use `file_id` instead. The `data/maps/` directory is created automatically on first upload.
- **Bot state**: `data/persistence.pkl` — stores `user_data` and the `arbitrary_callback_data` LRU cache across restarts.

## Notable API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/characters/{id}/death_saves/roll` | Roll 1d20 for death save (D&D 5e rules: nat 20 = revive, nat 1 = 2 failures) |
| `POST` | `/characters/{id}/dice/post-to-chat` | Send a dice result to the user's private Telegram chat via the Bot API (replaces `sendData()`) |
| `DELETE` | `/characters/{id}/dice/history` | Clear the character's dice roll history |
| `POST` | `/characters/{id}/maps/upload` | Upload a map image from the webapp (multipart/form-data: `zone_name` + `file`) |
| `GET` | `/characters/{id}/maps/{map_id}/file` | Serve map file — local disk if `local_file_path` set, else Telegram proxy |

### D&D 5e Rule Compliance Notes
- **Death save roll**: nat 20 → revive with 1 HP + reset saves; nat 1 → 2 failures; 10+ → 1 success; 2-9 → 1 failure
- **Rests break concentration**: both short and long rest clear `concentrating_spell_id`
- **HP above 0 resets death saves**: HEAL/SET_CURRENT automatically clears death saves when HP crosses from 0 to positive
- **Long rest includes short-rest resources**: long rest restores abilities/resources with `restoration_type` of `long_rest` OR `short_rest`

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
