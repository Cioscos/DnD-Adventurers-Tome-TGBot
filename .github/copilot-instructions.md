# Copilot Instructions

## Repository

- Remote: `https://github.com/Cioscos/dnd_bot_revamped.git` — branch `main`.
- Always commit and push changes to this repository.

## MCP Servers

- **Context7**: ALWAYS use it to retrieve up-to-date documentation for every library before writing code.
- **dnd-mcp**: ALWAYS use it to understand D&D domain data and relationships before designing GraphQL queries.

## Project Overview

An async Telegram bot that lets users interactively browse the D&D 5e compendium (spells, monsters, classes, races, equipment, etc.) via inline keyboards, fetching data from the public GraphQL API.

### Tech Stack

| Dependency | Version | Purpose |
|---|---|---|
| `python-telegram-bot` | ≥ 22.0 | Telegram Bot API wrapper (async) |
| `httpx` | ≥ 0.27.0 | Async HTTP client for GraphQL |
| `python-dotenv` | ≥ 1.0.0 | `.env` file loading |

### Architecture

```
bot/
├── main.py                  # Entry point — Application builder, handler registration, run_polling
├── api/
│   ├── client.py            # DnDClient: async GraphQL client (httpx.AsyncClient, singleton)
│   └── queries.py           # 22 GraphQL query constants (11 list + 11 detail)
├── handlers/
│   ├── start.py             # /start command → welcome message + category keyboard
│   └── navigation.py        # CallbackQueryHandler dispatcher + 11 MarkdownV2 detail formatters
├── keyboards/
│   └── builder.py           # InlineKeyboardMarkup builders (categories grid, paginated list, detail back)
└── models/
    └── state.py             # Category registry (11 categories) + callback_data encode/decode
```

### D&D API

- **Endpoint**: `https://www.dnd5eapi.co/graphql/2014`
- **Timeout**: 15 seconds
- **11 categories**: `spells`, `monsters`, `classes`, `races`, `equipment`, `conditions`, `magicitems`, `feats`, `rules`, `backgrounds`, `weaponprops`
- Non-paginated categories (small sets): classes, races, conditions, feats, rules, backgrounds, weaponprops
- Paginated categories (large sets, `skip`/`limit`): spells, monsters, equipment, magicitems

### Navigation Model

3-level inline keyboard flow: **Categories → Paginated List → Item Detail**

All state is encoded in `callback_data` (stateless per-message, no ConversationHandler needed):

| Pattern | Action |
|---|---|
| `cat:<key>:<page>` | Show paginated item list |
| `itm:<key>:<index>` | Show item detail |
| `back:main` | Return to top-level categories |
| `noop` | No-op (informational buttons) |

### Key Constants

- `PAGE_SIZE = 10` — items per keyboard page
- `COLUMNS = 2` — buttons per row in category grid
- Max `callback_data` observed: 46 bytes (limit: 64)

### Detail Formatters

`navigation.py` uses a `_FORMATTERS` dispatch dict mapping each category key to a dedicated formatter function (e.g. `_format_spell`, `_format_monster`). Fallback: `_format_generic`. All output uses MarkdownV2 with `_esc()` for special character escaping.

## Coding Conventions

### Must Follow

- **Async only**: use `python-telegram-bot` v20+ async API. Never use the synchronous API.
- **Bot init**: `Application.builder().token(...).build()` pattern.
- **Token**: never hardcode — always read from env via `python-dotenv`.
- **GraphQL queries**: define as constants in `bot/api/queries.py`. Never inline query strings.
- **HTTP client**: `httpx.AsyncClient` for all API calls. Use `DnDClient` singleton from `bot/api/client.py`.
- **Handler registration**: all handlers registered in `main.py` via `application.add_handler()`.
- **Formatting**: Telegram MarkdownV2 — escape special chars (`_*[]()~`>#+\-=|{}.!\\`) with `_esc()` from `navigation.py`.
- **Error handling**: catch `telegram.error.BadRequest` and `bot.api.client.APIError` in every handler. Show user-friendly message with 🏠 Menu button.
- **Logging**: use `logging` module, not `print()`.
- **Type hints**: required on all function signatures.
- **Docstrings**: every module must have a module-level docstring explaining its purpose.
- **Navigation**: use `InlineKeyboardMarkup` + `InlineKeyboardButton` only. Never use `ReplyKeyboardMarkup` for navigation.
- **Pagination**: lists with > 10 items use "Next ➡️" / "⬅️ Prev" buttons. Detect next page by fetching `PAGE_SIZE + 1` items.
- **callback_data**: keep under 64 bytes. Use the encode/decode helpers in `bot/models/state.py`.

### Adding a New Category

1. Add list + detail GraphQL queries in `bot/api/queries.py`.
2. Add a `Category` entry in the `CATEGORIES` dict in `bot/models/state.py` (set `paginated=False` for small sets).
3. Add a `_format_<name>()` function in `bot/handlers/navigation.py` and register it in the `_FORMATTERS` dict.

### Thin Handlers Principle

Handlers in `handlers/` should only orchestrate: parse callback → call API client → format → send response. Business logic and API interaction belong in `bot/api/` and `bot/models/`.
