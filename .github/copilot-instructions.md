# Copilot Instructions

## Repository

- Remote: `https://github.com/Cioscos/dnd_bot_revamped.git` — branch `main`.
- Always commit and push changes to a new branch based on the feature you're working on.

## MCP Servers

- **Context7**: ALWAYS use it to retrieve up-to-date documentation for every library before writing code.
- **dnd-mcp**: ALWAYS use it to understand D&D domain data and relationships before designing GraphQL queries.

## Project Overview

An async Telegram bot with three main sections:

1. **Wiki D&D 5e** — browse the D&D 5e compendium (spells, monsters, classes, races, equipment, etc.) via inline keyboards, fetching data from the public GraphQL API. The bot **dynamically discovers** the API schema at startup via GraphQL introspection.
2. **Gestione Personaggio** — full D&D character management: HP, AC, ability scores, spells, inventory, currency, dice, notes, maps, and more. Data is persisted in a local SQLite database via SQLAlchemy async.
3. **Funzionalità Gruppo (Party)** — group Telegram feature: `/party` and `/party_stop` commands that show a live-updated party status message with all active characters' HP.

The top-level `/start` menu always shows two buttons:
- `📖 Wiki D&D` → opens the wiki explorer
- `⚔️ Il mio personaggio` → opens character selection / creation

**Chat-type scoping**: `/start` is **private-chat only**. If called inside a group or supergroup, it replies with an Italian warning message and returns early — no menu is shown. `/party` and `/party_stop` are **group-only** (they reject private chats). No other commands have chat-type restrictions.

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
├── data/
│   └── classes.py           # DND_CLASSES list, ResourceConfig dataclass, CLASS_RESOURCES formulas, get_resources_for_class()
├── db/
│   ├── engine.py            # SQLAlchemy async engine, AsyncSession factory, init_db(), get_session()
│   └── models.py            # ORM models: Character, CharacterClass, ClassResource, AbilityScore, Spell, SpellSlot,
│                            #             Item, Currency, Ability, Map, GroupMember, PartySession + enums
├── schema/
│   ├── types.py             # FieldInfo, TypeInfo, MenuCategory dataclasses
│   └── registry.py          # SchemaRegistry singleton — introspects API, maps root queries, computes navigable fields
├── handlers/
│   ├── start.py             # /start command → top-level 2-choice menu (Wiki | Personaggio); private-chat only — warns in groups
│   ├── navigation.py        # N-level CallbackQueryHandler dispatcher + MarkdownV2 formatters (wiki)
│   ├── party.py             # /party, /party_stop commands + PartyAction callbacks + track_group_member + maybe_update_party_message
│   └── character/
│       ├── __init__.py      # Conversation state constants (48 states)
│       ├── conversation.py  # Master ConversationHandler — routes CharAction callbacks, stop_command_handler, builds handler
│       ├── selection.py     # Character create / select / delete; creation wizard includes class selection step
│       ├── menu.py          # Character main menu with summary
│       ├── hit_points.py    # HP (set max, set current, damage, healing) + rest (restores ClassResource on rest); fires party update hook
│       ├── armor_class.py   # CA (base, shield, magic)
│       ├── stats.py         # Ability scores (FOR/DES/COS/INT/SAG/CAR) with modifiers
│       ├── spells.py        # Learn / forget / use spells (slot picker, concentration tracking, TS, pin) + fuzzy search
│       ├── spell_slots.py   # Add / use / restore / remove spell slot levels
│       ├── bag.py           # Inventory with encumbrance tracking
│       ├── currency.py      # Coins management + currency conversion
│       ├── abilities.py     # Special abilities (passive/active, uses, restoration type)
│       ├── multiclass.py    # Multiclassing: guided/custom class add, subclass, level up/down, resource auto-gen
│       ├── class_resources.py # Class-specific resources (Ki, Rage, etc.): view / use / restore per ClassResource
│       ├── dice.py          # Dice roller (d4–d100) with history
│       ├── notes.py         # Text notes + voice notes
│       ├── maps.py          # Map images/documents organised by zone
│       └── settings.py      # Per-character settings (spell management mode, party active toggle)
├── keyboards/
│   ├── builder.py           # Wiki keyboards: categories, paginated list, detail (📂 buttons), sub-list
│   ├── character.py         # Character keyboards: selection, main menu (multi-column), all feature screens, build_cancel_keyboard
│   └── party.py             # Party keyboards: mode selection (public/private), master reveal button
├── models/
│   ├── state.py             # NavAction frozen dataclass (wiki callback data) + make_back()
│   ├── character_state.py   # CharAction frozen dataclass (character callback data) + make_char_back()
│   └── party_state.py       # PartyAction frozen dataclass (party callback data)
└── utils/
    ├── formatting.py        # Italian-language text formatters for character screens
    └── party_formatting.py  # Party message formatter: format_party_message(characters, session) → MarkdownV2
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
| `characters` | `id`, `user_id`, `name`, `race`, `gender`, `hit_points`, `current_hit_points`, `base_armor_class`, `shield_armor_class`, `magic_armor`, `spell_slots_mode`, `concentrating_spell_id` (FK → spells.id), `rolls_history` (JSON), `notes` (JSON), `settings` (JSON), `is_party_active` (bool, default False) |
| `character_classes` | `character_id` → FK, `class_name`, `level`, `subclass` (optional) |
| `class_resources` | `class_id` → FK (character_classes.id, cascade), `name`, `current`, `total`, `restoration_type`, `note` |
| `ability_scores` | `character_id` → FK, `name` (strength/dexterity/…), `value` |
| `spells` | `character_id` → FK, `name`, `level`, `description`, `casting_time`, `range_area`, `components`, `duration`, `is_concentration`, `is_ritual`, `higher_level`, `attack_save`, `is_pinned` |
| `spell_slots` | `character_id` → FK, `level`, `total`, `used` |
| `items` | `character_id` → FK, `name`, `description`, `weight`, `quantity` |
| `currencies` | `character_id` → FK (1:1), `copper`, `silver`, `electrum`, `gold`, `platinum` |
| `abilities` | `character_id` → FK, `name`, `description`, `max_uses`, `uses`, `is_passive`, `is_active`, `restoration_type` |
| `maps` | `character_id` → FK, `zone_name`, `file_id`, `file_type` |
| `group_members` | `group_id` (BigInt), `user_id` (BigInt) — unique together; tracks every user who has ever written in the group |
| `party_sessions` | `id`, `group_id` (BigInt, unique), `group_title`, `mode` (public/private), `message_chat_id` (BigInt), `message_id` (Int), `started_at` (ISO str), `expires_at` (ISO str) |

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

Key `action` values: `char_select`, `char_new`, `char_menu`, `char_hp`, `char_ac`, `char_stats`, `char_level`, `char_spells`, `char_slots`, `char_bag`, `char_currency`, `char_abilities`, `char_multiclass`, `char_class_res`, `char_dice`, `char_notes`, `char_maps`, `char_rest`, `char_settings`, `char_party_active`, `char_delete`.

Key `char_spells` sub-actions: `learn`, `learn_conc_yes`, `learn_conc_no`, `detail`, `forget`, `use`, `use_slot`, `activate_conc`, `drop_conc`, `conc_save`, `pin`, `edit_menu`, `edit_<field>` (e.g. `edit_casting_time`, `edit_is_concentration`), `search`, `search_show`.

Key `char_multiclass` sub-actions: `add`, `guided` (show class list), `custom` (free-text entry), `select_guided` (class chosen from list, `extra=class_name`), `skip_subclass`, `remove`, `remove_confirm` (`extra=class_name`).

Key `char_class_res` sub-actions: `menu` (`extra=class_id`), `use` (`item_id=resource_id, extra=class_id`), `restore_one` (`item_id=resource_id, extra=class_id`), `restore_all` (`extra=class_id`), `noop`.

#### Party Feature (PartyAction)

**Standalone** inline keyboard flow for group party management (NOT inside `ConversationHandler`).

```python
@dataclass(frozen=True)
class PartyAction:
    action: str       # "party_mode" | "party_master_reveal" | "party_noop"
    group_id: int = 0 # Telegram group chat_id
    extra: str = ""   # e.g. "public" or "private" for party_mode
```

| `PartyAction.action` | Purpose |
|---|---|
| `"party_mode"` | User chose display mode; `extra` = `"public"` or `"private"` |
| `"party_master_reveal"` | Master presses the button to receive party list privately |
| `"party_noop"` | No-op (informational buttons) |

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

`bot/utils/formatting.py` provides Italian-language formatters for every character screen: `format_character_summary` (accepts optional `spells` and `abilities` for active status), `format_hp`, `format_ac`, `format_ability_scores`, `format_spells`, `format_spell_detail`, `format_spell_slots`, `format_bag`, `format_currency`, `format_abilities`, `format_maps`, `format_dice_history`, `format_character_active_status`, `format_multiclass_menu`, `format_class_resources`. All use MarkdownV2 with `_esc()`.

## Coding Conventions

### Must Follow

- **Async only**: use `python-telegram-bot` v20+ async API. Never use the synchronous API.
- **Bot init**: `Application.builder().token(...).arbitrary_callback_data(True).post_init(post_init).build()` pattern.
- **Token**: never hardcode — always read from env via `python-dotenv`.
- **GraphQL queries**: generate dynamically using `bot/api/query_builder.py`. Never hardcode query strings.
- **HTTP client**: `httpx.AsyncClient` for all API calls. Use `DnDClient` singleton from `bot/api/client.py`.
- **Handler registration**: all handlers registered in `main.py` via `application.add_handler()`. Character `ConversationHandler` must be registered **before** the party `CallbackQueryHandler`, which must come before the wiki `CallbackQueryHandler`.
- **Wiki callback data**: use `NavAction` dataclass instances. Never encode state as raw strings.
- **Character callback data**: use `CharAction` dataclass instances. The party and wiki `CallbackQueryHandler`s must filter out `CharAction` instances.
- **Party callback data**: use `PartyAction` dataclass instances (`bot/models/party_state.py`). The wiki `CallbackQueryHandler` must also exclude `PartyAction` via `pattern=lambda d: not isinstance(d, CharAction) and not isinstance(d, PartyAction)`.
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
- **Chat-type scoping**: `/start` (and all Wiki/Gestione Personaggio features) are **private-chat only**. `start_command()` checks `chat.type in ("group", "supergroup")` and replies with an Italian warning if so. `/party` and `/party_stop` are **group-only** and perform the symmetric check. Never remove these guards.
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

### Class Management Details

- **Class selection mode**: when adding a class (both during creation and in the multiclass menu) the user first chooses between "📖 Scegli da lista" (guided) and "✍️ Personalizzata" (free text). Guided shows 12 predefined D&D 5e class buttons; custom falls back to free text (`CHAR_MULTICLASS_ADD` state).
- **Creation wizard**: after entering the character name, `selection.py` immediately calls `ask_add_class(flow="creation")`. When the flow completes it goes to `show_character_menu` instead of `show_multiclass_menu`.
- **Subclass**: optional free-text step after the level input. A "⏭️ Salta" button (`sub="skip_subclass"`) skips it. Stored in `CharacterClass.subclass`; shown in `class_summary` and `format_multiclass_menu`.
- **`bot/data/classes.py`**: single source of truth for class resource configuration. `DND_CLASSES` lists the 12 Italian-named classes. `ResourceConfig` dataclass holds `name`, `formula: Callable[[int], int]`, `restoration_type`, `note`, `cha_based`. `CLASS_RESOURCES: dict[str, list[ResourceConfig]]` maps class name → configs. `get_resources_for_class(class_name, level, char)` returns ready-to-insert dicts. `update_resources_for_level(class_name, new_level, existing_resources, char)` recalculates totals in-place after a level change.
- **Auto-generated resources**: when a predefined class is added, `_finalize_add_class()` in `multiclass.py` calls `get_resources_for_class()` and creates `ClassResource` rows. Resources with `total == 0` at that level are skipped; they are added when level increases.
- **Level change hook**: `apply_level_change()` calls `update_class_resources_on_level_change()` from `class_resources.py` after each level change. `current` is capped to the new `total` but never reset.
- **Barbaro lv20**: `total = 99` represents unlimited Furie; the UI displays "∞".
- **Bardo Ispirazione Bardica**: `cha_based=True` — `total` is set to `max(1, CHA_modifier)` at class creation time, reading from `char.ability_scores`. If the character's CHA changes later, the user must update manually.
- **Warlock Slot Patto**: tracked as `ClassResource` with `restoration_type=SHORT_REST`, separate from the spell slot system. Note displayed in UI.
- **Guerriero Dadi Superiorità**: included for all fighters (not just Battle Master) for simplicity. A `note` field on the resource record explains this.
- **Rest integration**: `handle_rest()` in `hit_points.py` calls `restore_class_resources_on_rest(char_id, rest_type)` from `class_resources.py` after the standard rest logic. This restores all `ClassResource` rows matching the rest type.
- **Resource screen** (`char_class_res`): shows `[➖] [🔋 Name: current/total] [➕]` rows per resource, a "🔄 Ripristina Tutto" button, and a back/menu nav row. Tapping ➖/➕ adjusts by 1; restore all resets `current = total`.

### Party Feature Details

- **Commands**: `/party` (group-only) and `/party_stop`. Both refuse to run outside groups.
- **Session lifetime**: 48 hours. Stored as ISO timestamp strings in `party_sessions.expires_at`. The countdown is displayed in every party message and updated on each HP change.
- **Group member tracking**: a `MessageHandler` (registered with `group=1` so it runs alongside other handlers) records every user who sends a text message in a group into the `group_members` table. The `/party` command issuer is also tracked on invocation.
- **Active character selection**: `Character.is_party_active` (bool, default `False`) flags the character used in party display. Toggle via `char_party_active` action → `toggle_party_active()` in `settings.py`. Only one character per `user_id` can be `is_party_active=True` at a time (others are set to `False` automatically). If a user has exactly **one** character and none is active, it is included automatically in the party list.
- **Mode selection flow**:
  - `/party` → shows `build_party_mode_keyboard(group_id)` with 🌐 Pubblica / 🔒 Privata.
  - **Public mode** (`party_mode`, `extra="public"`): sends the party message in the group, stores `message_chat_id = group_id` in the session.
  - **Private mode** (`party_mode`, `extra="private"`): edits the mode-selection message to show a "master presses here" prompt with `build_party_master_reveal_keyboard(group_id)`. The master presses the button (`party_master_reveal`) → bot sends a private message to the master → stores `message_chat_id = master.user_id` in the session.
- **Real-time updates**: `maybe_update_party_message(char_id, bot)` in `handlers/party.py` finds all active `PartySession`s that include the character's user (via `GroupMember` join), rebuilds the message text, and calls `bot.edit_message_text`. It is invoked as `asyncio.create_task(_trigger_party_update(...))` from `hit_points.py` after every HP change and rest — fire-and-forget, never blocks the user response.
- **Session cleanup**: if `edit_message_text` raises `BadRequest` (message too old/deleted), the session row is deleted. `/party_stop` also edits the party message to "🛑 Sessione party terminata." before deleting the session.
- **Party message format** (`bot/utils/party_formatting.py`): MarkdownV2 with group title, countdown, and per-character rows showing name, class/level, HP bar, and AC. `format_party_message(characters, session)` takes `list[tuple[Character, str | None]]` (character + optional username) and the active `PartySession`.
- **`build_settings_keyboard`** now accepts `is_party_active: bool` to render the current toggle state.

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

