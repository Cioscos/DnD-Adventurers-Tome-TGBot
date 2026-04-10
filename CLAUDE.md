# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Create .env with BOT_TOKEN (required), DEV_CHAT_ID (optional), DB_PATH (optional)
python -m bot.main
```

No test suite or linter is configured.

## Architecture Overview

Async Telegram bot for D&D 5e with three integrated sections:

1. **Wiki D&D 5e** — N-level inline keyboard navigation over the public GraphQL API (`https://www.dnd5eapi.co/graphql/2014`), with full schema introspected at startup.
2. **Character Management** — full D&D character CRUD (HP, AC, spells, inventory, skills, etc.) persisted in SQLite via SQLAlchemy async.
3. **Party** — group Telegram feature with live-updated party status message.

Entry point: `bot/main.py` — builds the `Application`, initialises `SchemaRegistry` + DB in `post_init`, and registers all handlers.

## Navigation Model (Critical)

Three frozen dataclasses drive all callback state via PTB's `arbitrary_callback_data` (LRU cache):

| Dataclass | File | Used for |
|---|---|---|
| `NavAction` | `bot/models/state.py` | Wiki navigation callbacks |
| `CharAction` | `bot/models/character_state.py` | Character management callbacks |
| `PartyAction` | `bot/models/party_state.py` | Party session callbacks |

**Handler registration order in `main.py` is mandatory**: Character `ConversationHandler` first, then Party `CallbackQueryHandler`, then Wiki `CallbackQueryHandler`. The wiki handler pattern must exclude both `CharAction` and `PartyAction` instances.

## Key Patterns

### Adding a New Character Feature

1. Add state constant(s) to `bot/handlers/character/__init__.py` (update the `range()` count).
2. Create `bot/handlers/character/<feature>.py`.
3. Add keyboard builder(s) to `bot/keyboards/character.py` — each must accept `lang: str = "it"`.
4. Add formatter(s) to `bot/utils/formatting.py` — each must accept `lang: str = "it"` and use `translator.t()`.
5. Add all user-facing strings to **both** `bot/locales/it.yaml` and `bot/locales/en.yaml`.
6. Wire the new action into `character_callback_handler()` in `conversation.py`.
7. Add the new state(s) to the `states` dict in `build_character_conversation_handler()`.
8. Every state awaiting text input must include `build_cancel_keyboard(char_id, back_action, lang=lang)` in its prompt.

### Adding a New Wiki Category

1. Add a `MenuCategory(type_name, label, emoji)` to `MENU_CATEGORIES` in `bot/schema/registry.py`.
2. Optionally add a `_format_<type>()` function in `bot/handlers/navigation.py` and register it in `_FORMATTERS`. Without one, the generic formatter applies.

## Coding Conventions

- **Async only** — use the python-telegram-bot v20+ async API throughout.
- **GraphQL queries** — always generated dynamically via `bot/api/query_builder.py`; never hardcode query strings.
- **HTTP client** — use the `DnDClient` singleton from `bot/api/client.py` (`httpx.AsyncClient`).
- **Database sessions** — always `async with get_session() as session:` from `bot/db/engine.py`; never instantiate a session directly.
- **MarkdownV2 escaping** — use `_esc()` from `navigation.py` for wiki output, and `_esc()` from `utils/formatting.py` for character screens. Condition description strings in YAML are **pre-escaped** — do not pass them through `_esc()` again.
- **Plain text surfaces** — inline keyboard button labels and `callback_query.answer()` toast messages are **plain text only**; never apply MarkdownV2 escaping or special characters there. Locale strings used exclusively in these surfaces must not contain backslash escapes (e.g. write `(XP)` not `\(XP\)`).
- **i18n** — call `lang = get_lang(update)` at the top of every handler, pass `lang=lang` everywhere. Use `translator.t("key", lang=lang)` for all strings; never hardcode Italian or English text. Default language is `"it"`.
- **Logging** — use `logging` module; never `print()`.
- **Type hints** — required on all function signatures.
- **Chat-type guards** — `/start` and character features are private-chat only; `/party`/`/party_stop` are group-only. Never remove these guards.
- **Cancel keyboard** — every multi-step text-input flow must offer `build_cancel_keyboard(char_id, back_action)` so users can abort without `/stop`.

## Persistence

- **Character DB**: SQLite at `data/dnd_bot.db` (override via `DB_PATH`). Schema migrations run idempotently via `ALTER TABLE` in `_migrate_schema()` on every startup.
- **Bot state**: `data/persistence.pkl` — stores `user_data`, callback LRU cache, and conversation state across restarts.

## i18n

- Locale files: `bot/locales/it.yaml` (default) and `bot/locales/en.yaml` (~570 keys, hierarchical).
- `Translator` singleton in `bot/utils/i18n.py` with a hot-reload watcher.
- Language detected from `update.effective_user.language_code`.

## GitHub Pages

`docs/` contains a Jekyll site at `https://cioscos.github.io/dnd_bot_revamped`. Always use `{{ '/path' | relative_url }}` for asset/internal links — never hardcode paths.

# General rules

1. Always ask for clarification if the user's request is ambiguous or incomplete. Never make assumptions about what they want.
2. Always work on a feature branch, never directly on main.
3. Use Context7 MCP server when it makes sense.
