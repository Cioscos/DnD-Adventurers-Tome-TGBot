# Copilot Instructions

## Repository

- Remote: `https://github.com/Cioscos/dnd_bot_revamped.git` — branch `main`.
- Always commit and push changes to this repository.

## MCP Servers

- **Context7**: ALWAYS use it to retrieve up-to-date documentation for every library before writing code.
- **dnd-mcp**: ALWAYS use it to understand D&D domain data and relationships before designing GraphQL queries.

## Project Overview

An async Telegram bot that lets users interactively browse the D&D 5e compendium (spells, monsters, classes, races, equipment, etc.) via inline keyboards, fetching data from the public GraphQL API. The bot **dynamically discovers** the API schema at startup via GraphQL introspection, so navigable relationships (e.g. Class → Subclasses, Spells) are detected automatically.

### Tech Stack

| Dependency | Version | Purpose |
|---|---|---|
| `python-telegram-bot[callback-data]` | ≥ 22.0 | Telegram Bot API wrapper (async) + arbitrary callback data (LRU cache) |
| `httpx` | ≥ 0.27.0 | Async HTTP client for GraphQL |
| `python-dotenv` | ≥ 1.0.0 | `.env` file loading |
| `cachetools` | (auto) | Installed by the `[callback-data]` extra for the callback LRU cache |

### Architecture

```
bot/
├── main.py                  # Entry point — Application builder, schema init (post_init), handler registration
├── api/
│   ├── client.py            # DnDClient: async GraphQL client (httpx.AsyncClient, singleton)
│   ├── introspection.py     # __schema query constant + parser → TypeInfo objects
│   └── query_builder.py     # Dynamic GraphQL query generation from TypeInfo (list, detail, sub-list)
├── schema/
│   ├── types.py             # FieldInfo, TypeInfo, MenuCategory dataclasses
│   └── registry.py          # SchemaRegistry singleton — introspects API, maps root queries, computes navigable fields
├── handlers/
│   ├── start.py             # /start command → welcome message + category keyboard
│   └── navigation.py        # N-level CallbackQueryHandler dispatcher + custom & generic MarkdownV2 formatters
├── keyboards/
│   └── builder.py           # Dynamic InlineKeyboardMarkup builders (categories, paginated list, detail with 📂 buttons, sub-list)
└── models/
    └── state.py             # NavAction frozen dataclass (arbitrary callback data) + make_back() helper
```

### D&D API

- **Endpoint**: `https://www.dnd5eapi.co/graphql/2014`
- **Timeout**: 15 seconds
- **Schema discovery**: at startup `SchemaRegistry.initialize()` runs a single `__schema` introspection query that discovers all 203 types, their fields, root query mappings, and pagination support.
- **11 menu categories**: Spells, Monsters, Classes, Races, Equipment, Conditions, Magic Items, Feats, Rules, Backgrounds, Weapon Props — configured in `MENU_CATEGORIES` list in `registry.py`.
- **Pagination**: detected from introspection (root list fields with `skip`/`limit` args). Sub-lists use client-side pagination.
- **Partial errors**: the client returns partial `data` even when the API returns `errors` (e.g. `AbilityScore.desc` null bug), logging a warning.

### Navigation Model

**N-level** inline keyboard flow: **Categories → Paginated List → Item Detail (with 📂 sub-entity buttons) → Sub-list → Sub-item Detail → …**

All state is stored as `NavAction` frozen dataclass instances via PTB's `arbitrary_callback_data` feature (no 64-byte string limit):

| `NavAction.action` | Purpose | Key Fields |
|---|---|---|
| `"menu"` | Return to top-level categories | — |
| `"list"` | Show paginated item list | `type_name`, `page` |
| `"detail"` | Show item detail with 📂 buttons | `type_name`, `index`, `concrete_type` (for unions) |
| `"sub_list"` | Show sub-entity list (e.g. subclasses of a class) | `type_name`, `index`, `field`, `page`, `concrete_type` |
| `"noop"` | No-op (informational buttons) | — |

Each `NavAction` carries a `back` tuple that encodes where the ⬅️ Back button should navigate.

### Schema Registry & Navigable Fields

A field is **navigable** (shown as a 📂 button in the detail view) when:
1. It is a `LIST` of `OBJECT` or `UNION` items
2. The element type (or every union member) has `index` and `name` fields
3. The element type (or at least one union member) has a root detail query

Examples of auto-discovered navigable relationships:
- **Class** → proficiencies, saving_throws, spells, subclasses
- **Race** → languages, subraces, traits
- **Spell** → classes, subclasses
- **Monster** → condition_immunities, forms

### Query Builder

GraphQL queries are **generated dynamically** from `TypeInfo` metadata — no hardcoded query strings:
- `build_list_query(ti, registry)` — paginated list with index + name + badge fields
- `build_detail_query(ti, registry)` — full detail with depth-2 field expansion; navigable fields get `{ index name }` only at top level
- `build_sub_list_query(parent_ti, field, registry)` — fetches a specific sub-field from a parent item

Union types (e.g. `AnyEquipment`) are handled with `__typename` + inline fragments (`... on Weapon { … }`).

### Key Constants

- `PAGE_SIZE = 10` — items per keyboard page
- `COLUMNS = 2` — buttons per row in category grid
- `_DETAIL_DEPTH = 2` — recursion limit for detail query field expansion

### Detail Formatters

`navigation.py` uses a `_FORMATTERS` dispatch dict mapping **GraphQL type names** (e.g. `"Spell"`, `"Monster"`, `"Weapon"`) to dedicated formatter functions. Fallback: `_format_generic` which auto-formats scalar fields as `*Key:* value` pairs. All output uses MarkdownV2 with `_esc()` for special character escaping.

## Coding Conventions

### Must Follow

- **Async only**: use `python-telegram-bot` v20+ async API. Never use the synchronous API.
- **Bot init**: `Application.builder().token(...).arbitrary_callback_data(True).post_init(post_init).build()` pattern.
- **Token**: never hardcode — always read from env via `python-dotenv`.
- **GraphQL queries**: generate dynamically using `bot/api/query_builder.py`. Never hardcode query strings.
- **HTTP client**: `httpx.AsyncClient` for all API calls. Use `DnDClient` singleton from `bot/api/client.py`.
- **Handler registration**: all handlers registered in `main.py` via `application.add_handler()`.
- **Callback data**: use `NavAction` dataclass instances (arbitrary callback data). Never encode state as raw strings.
- **Formatting**: Telegram MarkdownV2 — escape special chars (`_*[]()~`>#+\-=|{}.!\\`) with `_esc()` from `navigation.py`.
- **Error handling**: catch `telegram.error.BadRequest`, `telegram.ext.InvalidCallbackData`, and `bot.api.client.APIError` in every handler. Show user-friendly message with 🏠 Menu button.
- **Logging**: use `logging` module, not `print()`.
- **Type hints**: required on all function signatures.
- **Docstrings**: every module must have a module-level docstring explaining its purpose.
- **Navigation**: use `InlineKeyboardMarkup` + `InlineKeyboardButton` only. Never use `ReplyKeyboardMarkup` for navigation.
- **Pagination**: top-level lists use server-side `skip`/`limit` (detect next page by fetching `PAGE_SIZE + 1`). Sub-lists use client-side slicing.

### Adding a New Menu Category

1. Add a `MenuCategory(type_name, label, emoji)` entry to `MENU_CATEGORIES` in `bot/schema/registry.py`.
2. (Optional) Add a `_format_<type>()` function in `bot/handlers/navigation.py` and register it in the `_FORMATTERS` dict. Without a custom formatter, the generic formatter will be used.

Navigable sub-entity buttons (📂) are discovered automatically from the schema — no manual configuration needed.

### Adding a Custom Formatter

1. Create `_format_<type>(item: dict) -> str` in `navigation.py` using `_esc()` for MarkdownV2.
2. Register it in `_FORMATTERS` with the **GraphQL type name** as key (e.g. `"Subclass": _format_subclass`).

### Thin Handlers Principle

Handlers in `handlers/` should only orchestrate: parse NavAction → build query via query_builder → call API client → format → send response. Business logic and API interaction belong in `bot/api/` and `bot/schema/`.
