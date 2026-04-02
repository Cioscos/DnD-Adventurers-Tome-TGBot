# Copilot Instructions

## Repository

- Remote: `https://github.com/Cioscos/dnd_bot_revamped.git` — branch `main`.
- Active feature branch: `main`.
- Always commit and push changes to this repository.

## MCP Servers

- **Context7**: ALWAYS use it to retrieve up-to-date documentation for every library before writing code.
- **dnd-mcp**: ALWAYS use it to understand D&D domain data and relationships before designing GraphQL queries.

## Project Overview

An async Telegram bot with two main sections:

1. **Wiki D&D 5e** — browse the D&D 5e compendium (spells, monsters, classes, races, equipment, etc.) via inline keyboards, fetching data from the public GraphQL API. The bot **dynamically discovers** the API schema at startup via GraphQL introspection.
2. **Gestione Personaggio** — full D&D character management: HP, AC, ability scores, spells, inventory, currency, dice, notes, maps, and more. Data is persisted in a local SQLite database via SQLAlchemy async.

The top-level `/start` menu always shows two buttons:
- `📖 Wiki D&D` → opens the wiki explorer
- `⚔️ Il mio personaggio` → opens character selection / creation

**UI language**: Italian (all user-facing strings).

### Tech Stack

| Dependency | Version | Purpose |
|---|---|---|
| `python-telegram-bot[callback-data]` | ≥ 22.0 | Telegram Bot API wrapper (async) + arbitrary callback data (LRU cache) |
| `httpx` | ≥ 0.27.0 | Async HTTP client for GraphQL |
| `python-dotenv` | ≥ 1.0.0 | `.env` file loading |
| `sqlalchemy` | ≥ 2.0 | Async ORM for character persistence |
| `aiosqlite` | ≥ 0.20 | SQLite async driver (used by SQLAlchemy) |
| `rapidfuzz` | ≥ 3.0 | Fuzzy string matching for spell search |
| `cachetools` | (auto) | Installed by the `[callback-data]` extra for the callback LRU cache |

### Architecture

```
bot/
├── main.py                  # Entry point — Application builder, dual-handler logging setup, schema init + DB init (post_init), handler registration; global error handler + /stop command
├── api/
│   ├── client.py            # DnDClient: async GraphQL client (httpx.AsyncClient, singleton)
│   ├── introspection.py     # __schema query constant + parser → TypeInfo objects
│   └── query_builder.py     # Dynamic GraphQL query generation from TypeInfo (list, detail, sub-list)
├── db/
│   ├── engine.py            # SQLAlchemy async engine, AsyncSession factory, init_db(), get_session()
│   └── models.py            # ORM models: Character, CharacterClass, AbilityScore, Spell, SpellSlot,
│                            #             Item, Currency, Ability, Map + enums
├── schema/
│   ├── types.py             # FieldInfo, TypeInfo, MenuCategory dataclasses
│   └── registry.py          # SchemaRegistry singleton — introspects API, maps root queries, computes navigable fields
├── handlers/
│   ├── start.py             # /start command → top-level 2-choice menu (Wiki | Personaggio)
│   ├── navigation.py        # N-level CallbackQueryHandler dispatcher + MarkdownV2 formatters (wiki)
│   └── character/
│       ├── __init__.py      # Conversation state constants (47 states)
│       ├── conversation.py  # Master ConversationHandler — routes CharAction callbacks, stop_command_handler, builds handler
│       ├── selection.py     # Character create / select / delete
│       ├── menu.py          # Character main menu with summary
│       ├── hit_points.py    # HP (set max, set current, damage, healing) + rest
│       ├── armor_class.py   # CA (base, shield, magic)
│       ├── stats.py         # Ability scores (FOR/DES/COS/INT/SAG/CAR) with modifiers
│       ├── spells.py        # Learn / forget / use spells (slot picker, concentration tracking, TS, pin) + fuzzy search
│       ├── spell_slots.py   # Add / use / restore / remove spell slot levels
│       ├── bag.py           # Inventory with encumbrance tracking
│       ├── currency.py      # Coins management + currency conversion
│       ├── abilities.py     # Special abilities (passive/active, uses, restoration type)
│       ├── multiclass.py    # Multiclassing + level up/down
│       ├── dice.py          # Dice roller (d4–d100) with history
│       ├── notes.py         # Text notes + voice notes
│       ├── maps.py          # Map images/documents organised by zone
│       └── settings.py      # Per-character settings
├── keyboards/
│   ├── builder.py           # Wiki keyboards: categories, paginated list, detail (📂 buttons), sub-list
│   └── character.py         # Character keyboards: selection, main menu (multi-column), all feature screens, build_cancel_keyboard
├── models/
│   ├── state.py             # NavAction frozen dataclass (wiki callback data) + make_back()
│   └── character_state.py   # CharAction frozen dataclass (character callback data) + make_char_back()
└── utils/
    └── formatting.py        # Italian-language text formatters for character screens
```

### D&D API (Wiki)

- **Endpoint**: `https://www.dnd5eapi.co/graphql/2014`
- **Timeout**: 15 seconds
- **Schema discovery**: at startup `SchemaRegistry.initialize()` runs a single `__schema` introspection query that discovers all 203 types, their fields, root query mappings, and pagination support.
- **11 menu categories**: Spells, Monsters, Classes, Races, Equipment, Conditions, Magic Items, Feats, Rules, Backgrounds, Weapon Props — configured in `MENU_CATEGORIES` list in `registry.py`.
- **Pagination**: detected from introspection (root list fields with `skip`/`limit` args). Sub-lists use client-side pagination.
- **Partial errors**: the client returns partial `data` even when the API returns `errors` (e.g. `AbilityScore.desc` null bug), logging a warning.

### Database (Character Management)

- **File**: `data/dnd_bot.db` (SQLite, path overridable via `DB_PATH` env var)
- **Init**: `init_db()` called once in `post_init` — creates tables if they don't exist AND runs `_migrate_schema()` which adds missing columns via `ALTER TABLE` (idempotent, safe for existing DBs)
- **Session**: use the `get_session()` async context manager from `bot/db/engine.py` for all DB operations

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ Yes | Telegram bot token from @BotFather |
| `DEV_CHAT_ID` | Optional | Developer's Telegram chat ID — unhandled exceptions are sent here as private messages. Get it from @userinfobot. |
| `DB_PATH` | Optional | Override the SQLite database path (default: `data/dnd_bot.db`) |

#### ORM Tables

| Table | Key fields |
|---|---|
| `characters` | `id`, `user_id`, `name`, `race`, `gender`, `hit_points`, `current_hit_points`, `base_armor_class`, `shield_armor_class`, `magic_armor`, `spell_slots_mode`, `concentrating_spell_id` (FK → spells.id), `rolls_history` (JSON), `notes` (JSON), `settings` (JSON) |
| `character_classes` | `character_id` → FK, `class_name`, `level` |
| `ability_scores` | `character_id` → FK, `name` (strength/dexterity/…), `value` |
| `spells` | `character_id` → FK, `name`, `level`, `description`, `casting_time`, `range_area`, `components`, `duration`, `is_concentration`, `is_ritual`, `higher_level`, `attack_save`, `is_pinned` |
| `spell_slots` | `character_id` → FK, `level`, `total`, `used` |
| `items` | `character_id` → FK, `name`, `description`, `weight`, `quantity` |
| `currencies` | `character_id` → FK (1:1), `copper`, `silver`, `electrum`, `gold`, `platinum` |
| `abilities` | `character_id` → FK, `name`, `description`, `max_uses`, `uses`, `is_passive`, `is_active`, `restoration_type` |
| `maps` | `character_id` → FK, `zone_name`, `file_id`, `file_type` |

### Navigation Model

#### Wiki (NavAction)

**N-level** inline keyboard flow: **Main Menu → Wiki Categories → Paginated List → Item Detail (with 📂 sub-entity buttons) → Sub-list → …**

All state is stored as `NavAction` frozen dataclass instances via PTB's `arbitrary_callback_data` feature:

| `NavAction.action` | Purpose | Key Fields |
|---|---|---|
| `"menu"` | Return to top-level main menu (Wiki \| Personaggio) | — |
| `"wiki"` | Show wiki category grid | — |
| `"list"` | Show paginated item list | `type_name`, `page` |
| `"detail"` | Show item detail with 📂 buttons | `type_name`, `index`, `concrete_type` (for unions) |
| `"sub_list"` | Show sub-entity list (e.g. subclasses of a class) | `type_name`, `index`, `field`, `page`, `concrete_type` |
| `"noop"` | No-op (informational buttons) | — |

#### Character Management (CharAction)

**Hybrid** navigation: inline keyboards for menus, `ConversationHandler` for text input.

```python
@dataclass(frozen=True)
class CharAction:
    action: str      # e.g. "char_select" | "char_menu" | "char_hp" | …
    char_id: int = 0
    sub: str = ""    # sub-action within a screen (e.g. "damage", "heal")
    item_id: int = 0 # DB row id for items, spells, abilities, etc.
    page: int = 0
    extra: str = ""  # generic extra string (zone name, currency type, …)
    back: tuple[str, ...] = ()
```

Key `action` values: `char_select`, `char_new`, `char_menu`, `char_hp`, `char_ac`, `char_stats`, `char_level`, `char_spells`, `char_slots`, `char_bag`, `char_currency`, `char_abilities`, `char_multiclass`, `char_dice`, `char_notes`, `char_maps`, `char_rest`, `char_settings`, `char_delete`.

Key `char_spells` sub-actions: `learn`, `learn_conc_yes`, `learn_conc_no`, `detail`, `forget`, `use`, `use_slot`, `activate_conc`, `drop_conc`, `conc_save`, `pin`, `edit_menu`, `edit_<field>` (e.g. `edit_casting_time`, `edit_is_concentration`), `search`, `search_show`.

### Schema Registry & Navigable Fields (Wiki)

A field is **navigable** (shown as a 📂 button in the detail view) when:
1. It is a `LIST` of `OBJECT` or `UNION` items
2. The element type (or every union member) has `index` and `name` fields
3. The element type (or at least one union member) has a root detail query

Examples of auto-discovered navigable relationships:
- **Class** → proficiencies, saving_throws, spells, subclasses
- **Race** → languages, subraces, traits
- **Spell** → classes, subclasses
- **Monster** → condition_immunities, forms

### Query Builder (Wiki)

GraphQL queries are **generated dynamically** from `TypeInfo` metadata — no hardcoded query strings:
- `build_list_query(ti, registry)` — paginated list with index + name + badge fields
- `build_detail_query(ti, registry)` — full detail with depth-2 field expansion; navigable fields get `{ index name }` only at top level
- `build_sub_list_query(parent_ti, field, registry)` — fetches a specific sub-field from a parent item

Union types (e.g. `AnyEquipment`) are handled with `__typename` + inline fragments (`... on Weapon { … }`).

### Key Constants

- `PAGE_SIZE = 10` — items per wiki keyboard page
- `PAGE_SIZE = 8` — items per character keyboard page (in `keyboards/character.py`)
- `COLUMNS = 2` — buttons per row in wiki category grid and character main menu short-button columns
- `_LONG_THRESHOLD = 20` — character main menu: buttons with `len(label) > 20` are placed in a single column at the end; shorter buttons are paired 2-per-row
- `_DETAIL_DEPTH = 2` — recursion limit for wiki detail query field expansion

### Detail Formatters (Wiki)

`navigation.py` uses a `_FORMATTERS` dispatch dict mapping **GraphQL type names** (e.g. `"Spell"`, `"Monster"`, `"Weapon"`) to dedicated formatter functions. Fallback: `_format_generic` which auto-formats scalar fields as `*Key:* value` pairs. All output uses MarkdownV2 with `_esc()` for special character escaping.

### Character Formatters

`bot/utils/formatting.py` provides Italian-language formatters for every character screen: `format_character_summary` (accepts optional `spells` and `abilities` for active status), `format_hp`, `format_ac`, `format_ability_scores`, `format_spells`, `format_spell_detail`, `format_spell_slots`, `format_bag`, `format_currency`, `format_abilities`, `format_maps`, `format_dice_history`, `format_character_active_status`. All use MarkdownV2 with `_esc()`.

## Coding Conventions

### Must Follow

- **Async only**: use `python-telegram-bot` v20+ async API. Never use the synchronous API.
- **Bot init**: `Application.builder().token(...).arbitrary_callback_data(True).post_init(post_init).build()` pattern.
- **Token**: never hardcode — always read from env via `python-dotenv`.
- **GraphQL queries**: generate dynamically using `bot/api/query_builder.py`. Never hardcode query strings.
- **HTTP client**: `httpx.AsyncClient` for all API calls. Use `DnDClient` singleton from `bot/api/client.py`.
- **Handler registration**: all handlers registered in `main.py` via `application.add_handler()`. Character `ConversationHandler` must be registered **before** the wiki `CallbackQueryHandler`.
- **Wiki callback data**: use `NavAction` dataclass instances. Never encode state as raw strings.
- **Character callback data**: use `CharAction` dataclass instances. The wiki `CallbackQueryHandler` must filter out `CharAction` instances with `pattern=lambda d: not isinstance(d, CharAction)`.
- **Formatting**: Telegram MarkdownV2 — escape special chars with `_esc()`. Wiki uses `_esc()` from `navigation.py`; character screens use `_esc()` from `utils/formatting.py`.
- **UI language**: Italian for all user-facing strings in character management. Wiki strings may remain in English.
- **Error handling**: catch `telegram.error.BadRequest`, `telegram.ext.InvalidCallbackData`, and `bot.api.client.APIError` in every handler. Show user-friendly message with 🏠 Menu button.
- **Logging**: use `logging` module, not `print()`. The root logger is configured in `main.py` with two handlers: `StreamHandler` (console) and `RotatingFileHandler` (`logs/dnd_bot.log`, 5 MB / 3 backups, append mode). After setup, `logging.getLogger("httpx").setLevel(logging.WARNING)` silences per-request Telegram API noise from `httpx`.
- **Error handler**: `error_handler(update, context)` in `main.py` is registered with `application.add_error_handler()`. It logs the exception locally and sends the full HTML-formatted traceback (chunked to ≤4096 chars) to the developer's private chat via `DEV_CHAT_ID` env variable. If `DEV_CHAT_ID` is not set, only local logging occurs. Never remove this handler.
- **Type hints**: required on all function signatures.
- **Docstrings**: every module must have a module-level docstring explaining its purpose.
- **Navigation**: use `InlineKeyboardMarkup` + `InlineKeyboardButton` only. Never use `ReplyKeyboardMarkup` for navigation.
- **Pagination**: wiki top-level lists use server-side `skip`/`limit` (detect next page by fetching `PAGE_SIZE + 1`). Sub-lists and character lists use client-side slicing.
- **Database sessions**: always use `async with get_session() as session:` — never create a session directly. The context manager handles commit and rollback automatically.
- **Cancel pattern for text inputs**: every `ask_*` function that transitions to a text-input state MUST include a `build_cancel_keyboard(char_id, back_action)` keyboard in its prompt message. The `back_action` must be the `CharAction.action` string of the parent menu (e.g. `"char_hp"`, `"char_bag"`). Intermediate prompts within multi-step flows (e.g. weight step in bag, levels step in multiclass) must also include the cancel keyboard. This ensures the user can always abort without using `/stop`.
- **`/stop` command**: `stop_command_handler()` in `conversation.py` is registered as a `ConversationHandler` fallback. It clears all `*pending*` keys from `context.user_data`, sends "✋ Operazione annullata." and routes to the character menu or selection. A lightweight global `/stop` command in `main.py` handles the case when the user is outside the conversation.

### Adding a New Wiki Menu Category

1. Add a `MenuCategory(type_name, label, emoji)` entry to `MENU_CATEGORIES` in `bot/schema/registry.py`.
2. (Optional) Add a `_format_<type>()` function in `bot/handlers/navigation.py` and register it in the `_FORMATTERS` dict. Without a custom formatter, the generic formatter will be used.

Navigable sub-entity buttons (📂) are discovered automatically from the schema — no manual configuration needed.

### Adding a Custom Wiki Formatter

1. Create `_format_<type>(item: dict) -> str` in `navigation.py` using `_esc()` for MarkdownV2.
2. Register it in `_FORMATTERS` with the **GraphQL type name** as key (e.g. `"Subclass": _format_subclass`).

### Adding a New Character Feature

1. Add new state constant(s) to `bot/handlers/character/__init__.py` (update the `range()` count).
2. Create the handler module in `bot/handlers/character/<feature>.py`.
3. Add keyboard builder(s) to `bot/keyboards/character.py`.
4. Add formatter(s) to `bot/utils/formatting.py`.
5. Wire the new action into `character_callback_handler()` in `conversation.py`.
6. Add the new state(s) to the `states` dict in `build_character_conversation_handler()`.
7. For every state that awaits **text input**: include `build_cancel_keyboard(char_id, back_action)` in the prompt message (see *Cancel pattern for text inputs* above).

### Spell Management Details

- **Quick-add flow**: name (text) → level (text) → concentration? (inline Sì/No keyboard). All other fields added afterwards via ✏️ Modifica in the detail view.
- **Editable spell fields**: `level`, `casting_time`, `range_area`, `components`, `duration`, `is_concentration` (toggle), `is_ritual` (toggle), `attack_save`, `description`, `higher_level`. Each dispatched via `edit_<field>` sub-action.
- **Concentration**: only one active at a time (`concentrating_spell_id` on `Character`). Auto-activated on "Usa Incantesimo" for concentration spells. Dropped on both short and long rest.
- **Concentration saving throw**: DC = `max(10, damage // 2)`. Roll = `d20 + CON modifier`. Nat 1 always fails, nat 20 always succeeds. On failure, `concentrating_spell_id` is set to `None`.
- **Fuzzy spell search**: `sub="search"` → `ask_spell_search()` (state `CHAR_SPELL_SEARCH`); user types query; `handle_spell_search_text()` runs `rapidfuzz.process.extract(WRatio, score_cutoff=50, limit=20)` against spell names; results shown via `build_spell_search_results_keyboard()`. Back from spell detail to search results uses `extra="search_show"` (routed by `not sub and data.extra == "search_show"` check). Query is stored in `context.user_data["char_spell_search_pending"]`.
- **Pin**: `is_pinned=True` shows the spell in the main menu summary alongside passive active abilities.
- **`format_character_summary`** must receive `spells` and `abilities` lists to display the active status section.
- **`spell_management` setting** (`characters.settings["spell_management"]`): controls how the spell list is navigated.
  - `"paginate_by_level"` (default) — shows a **level picker** first (one button per level that has ≥1 spell, max 3 per row); tapping a level shows only the spells of that level with pagination. The `extra` field of `CharAction` carries the selected level as a string (e.g. `"3"`; `"0"` = cantrips). Empty `extra` → show picker.
  - `"select_level_directly"` — flat paginated list of all spells ordered by `level, name` (direct scroll, no level filter).
  - The `back` tuple in `CharAction` for the detail view encodes `extra` at index 5 (`make_char_back(..., extra=level_extra)`) so the ⬅️ button in the detail view returns to the correct filtered page.

### Voice Notes

Voice notes are stored as local `.ogg` files on disk and referenced in the `notes` JSON field as `[VOICE:files/<char_id>/<safe_title>.ogg]`.

**Saving** (`handle_voice_note`):
- Download the Telegram voice file via `get_file()` + `download_to_drive()` to `files/<char_id>/<safe_title>.ogg`.
- Store the local path in the DB as `[VOICE:<path>]`.
- Never store only the Telegram `file_id` — it expires and bots cannot re-send it as voice.

**Sending** (`show_note`):
- **Never use `send_voice` or `send_audio`** — Telegram raises `Voice_messages_forbidden` for users who have the privacy setting enabled, and also detects OGG/Opus files as voice even via `send_audio`.
- Always use `send_document` with **`disable_content_type_detection=True`** to prevent server-side content detection from reclassifying the file as a voice message.

**Deleting** (`delete_note`):
- Remove the local `.ogg` file via `Path.unlink()` when deleting a voice note from the DB.



Handlers in `handlers/` should only orchestrate: parse callback data → query DB or API → format → send response. Business logic belongs in `bot/db/` (character) or `bot/api/` and `bot/schema/` (wiki).

