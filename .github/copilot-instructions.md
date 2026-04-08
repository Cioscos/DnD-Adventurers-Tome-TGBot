# Copilot Instructions

## Repository

- Remote: `https://github.com/Cioscos/dnd_bot_revamped.git` — branch `main`.
- Always commit and push changes to a new branch based on the feature you're working on.

## GitHub Pages (docs/)

The `docs/` folder contains a Jekyll-based GitHub Pages site showcasing the bot's features.

- **URL**: `https://cioscos.github.io/dnd_bot_revamped`
- **Theme**: `pages-themes/cayman@v0.2.0` (via `jekyll-remote-theme`)
- **Config**: `docs/_config.yml` — `baseurl: "/dnd_bot_revamped"`, `url: "https://cioscos.github.io"`
- **Pages source**: GitHub repository Settings → Pages → branch `main`, folder `/docs`
- **Languages**: bilingual EN/IT via `.lang-en` / `.lang-it` CSS classes + `assets/js/lang-switch.js`
- **Assets**: custom CSS in `docs/assets/css/style.scss`, images in `docs/assets/images/`
- **Excluded from Jekyll build**: `Gemfile`, `Gemfile.lock`, `README.it.md`

When updating the site, always use `{{ '/path' | relative_url }}` for all asset and internal links — never hardcode paths.

## MCP Servers

- **Context7**: ALWAYS use it to retrieve up-to-date documentation for every library before writing code.
- **dnd-mcp**: ALWAYS use it to understand D&D domain data and relationships before designing GraphQL queries.

## Project Overview

An async Telegram bot with three main sections:

1. **Wiki D&D 5e** — browse the D&D 5e compendium (spells, monsters, classes, races, equipment, etc.) via inline keyboards, fetching data from the public GraphQL API. The bot **dynamically discovers** the API schema at startup via GraphQL introspection.
2. **Gestione Personaggio** — full D&D character management: HP, AC, ability scores, skills (with proficiency and d20 rolls), spells, inventory, currency, dice, notes, maps, conditions, heroic inspiration, modification history, and more. Data is persisted in a local SQLite database via SQLAlchemy async.
3. **Funzionalità Gruppo (Party)** — group Telegram feature: `/party` and `/party_stop` commands that show a live-updated party status message with all active characters' HP, AC, active conditions, and last dice roll.

The top-level `/start` menu always shows two buttons:
- `📖 Wiki D&D` → opens the wiki explorer
- `⚔️ Il mio personaggio` → opens character selection / creation

**Chat-type scoping**: `/start` is **private-chat only**. If called inside a group or supergroup, it replies with an Italian warning message and returns early — no menu is shown. `/party` and `/party_stop` are **group-only** (they reject private chats). No other commands have chat-type restrictions.

**UI language**: Detected automatically from `update.effective_user.language_code`. Supported locales: `it` (default) and `en`. All user-facing strings are loaded from YAML locale files — never hardcoded.

### Tech Stack

| Dependency | Version | Purpose |
|---|---|---|
| `python-telegram-bot[callback-data]` | ≥ 22.0 | Telegram Bot API wrapper (async) + arbitrary callback data (LRU cache) |
| `httpx` | ≥ 0.27.0 | Async HTTP client for GraphQL |
| `python-dotenv` | ≥ 1.0.0 | `.env` file loading |
| `sqlalchemy` | ≥ 2.0 | Async ORM for character persistence |
| `aiosqlite` | ≥ 0.20 | SQLite async driver (used by SQLAlchemy) |
| `rapidfuzz` | ≥ 3.0 | Fuzzy string matching for spell search |
| `pyyaml` | ≥ 6.0 | YAML locale file parsing for i18n |
| `cachetools` | (auto) | Installed by the `[callback-data]` extra for the callback LRU cache |

### Architecture

```
bot/
├── main.py                  # Entry point — Application builder (with PicklePersistence), dual-handler logging setup, schema init + DB init (post_init), handler registration; global error handler + /stop command
├── api/
│   ├── client.py            # DnDClient: async GraphQL client (httpx.AsyncClient, singleton)
│   ├── introspection.py     # __schema query constant + parser → TypeInfo objects
│   └── query_builder.py     # Dynamic GraphQL query generation from TypeInfo (list, detail, sub-list)
├── data/
│   ├── classes.py           # DND_CLASSES list, ResourceConfig dataclass, CLASS_RESOURCES formulas, get_resources_for_class()
│   └── skills.py            # SKILLS list of 18 (slug, ability) tuples + SKILL_ABILITY_MAP dict
├── db/
│   ├── engine.py            # SQLAlchemy async engine, AsyncSession factory, init_db(), get_session()
│   ├── history.py           # Character history helpers: log_history_event, get_history, clear_history (50-entry cap)
│   └── models.py            # ORM models: Character, CharacterClass, ClassResource, AbilityScore, Spell, SpellSlot,
│                            #             Item, Currency, Ability, Map, GroupMember, PartySession, CharacterHistory + enums
├── locales/
│   ├── it.yaml              # Italian strings (~570 keys, hierarchical)
│   └── en.yaml              # English translations (mirrors it.yaml structure)
├── schema/
│   ├── types.py             # FieldInfo, TypeInfo, MenuCategory dataclasses
│   └── registry.py          # SchemaRegistry singleton — introspects API, maps root queries, computes navigable fields
├── handlers/
│   ├── start.py             # /start command → top-level 2-choice menu (Wiki | Personaggio); private-chat only — warns in groups
│   ├── navigation.py        # N-level CallbackQueryHandler dispatcher + MarkdownV2 formatters (wiki)
│   ├── party.py             # /party, /party_stop commands + PartyAction callbacks + track_group_member + maybe_update_party_message
│   └── character/
│       ├── __init__.py      # Conversation state constants (58 states)
│       ├── conversation.py  # Master ConversationHandler — routes CharAction callbacks, stop_command_handler, builds handler
│       ├── selection.py     # Character create / select / delete; creation wizard includes class selection step
│       ├── menu.py          # Character main menu with summary
│       ├── hit_points.py    # HP (set max, set current, damage, healing) + rest (restores ClassResource on rest); fires party update hook
│       ├── armor_class.py   # CA (base, shield, magic); fires party update hook on change
│       ├── stats.py         # Ability scores (FOR/DES/COS/INT/SAG/CAR) with modifiers
│       ├── spells.py        # Learn / forget / use spells (slot picker, concentration tracking, TS, pin) + fuzzy search
│       ├── spell_slots.py   # Add / use / restore / remove spell slot levels
│       ├── bag.py           # Typed inventory: Generic/Weapon/Armor/Shield/Consumable/Tool; encumbrance tracking; equip/unequip with AC sync
│       ├── currency.py      # Coins management + currency conversion
│       ├── abilities.py     # Special abilities (passive/active, uses, restoration type)
│       ├── multiclass.py    # Multiclassing: guided/custom class add, subclass, level up/down, resource auto-gen
│       ├── class_resources.py # Class-specific resources (Ki, Rage, etc.): view / use / restore per ClassResource
│       ├── dice.py          # Dice roller (d4–d100) + dedicated initiative roll (1d20+DEX mod); fires party update hook on every roll
│       ├── notes.py         # Text notes + voice notes
│       ├── maps.py          # Map images/documents organised by zone
│       ├── conditions.py    # D&D 5e conditions tracker (14 binary + Exhaustion 0–6); fires party update hook on toggle/adjust
│       ├── history.py       # Character modification history: show_history (multi-msg split), handle_clear_history, HISTORY_EXTRA_MSGS_KEY
│       ├── skills.py        # Skills (Abilità) screen: list view + detail view with proficiency toggle and d20 roll + history logging
│       ├── inspiration.py   # Heroic Inspiration token: show screen, toggle grant/spend, history logging
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
    ├── formatting.py        # Character screen formatters — all accept lang: str = "it", use translator.t()
    ├── party_formatting.py  # Party message formatter: format_party_message(characters, session, lang) → MarkdownV2; helpers _get_active_conditions(), _get_last_roll()
    └── i18n.py              # Translator singleton, get_lang(update) helper, asyncio hot-reload watcher
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
| `characters` | `id`, `user_id`, `name`, `race`, `gender`, `hit_points`, `current_hit_points`, `base_armor_class`, `shield_armor_class`, `magic_armor`, `spell_slots_mode`, `concentrating_spell_id` (FK → spells.id), `rolls_history` (JSON), `notes` (JSON), `settings` (JSON), `is_party_active` (bool, default False), `conditions` (JSON, default empty dict), `skills` (JSON, default empty dict), `heroic_inspiration` (bool, default False) |
| `character_classes` | `character_id` → FK, `class_name`, `level`, `subclass` (optional) |
| `class_resources` | `class_id` → FK (character_classes.id, cascade), `name`, `current`, `total`, `restoration_type`, `note` |
| `ability_scores` | `character_id` → FK, `name` (strength/dexterity/…), `value` |
| `spells` | `character_id` → FK, `name`, `level`, `description`, `casting_time`, `range_area`, `components`, `duration`, `is_concentration`, `is_ritual`, `higher_level`, `attack_save`, `is_pinned` |
| `spell_slots` | `character_id` → FK, `level`, `total`, `used` |
| `items` | `character_id` → FK, `name`, `description`, `weight`, `quantity`, `item_type` (String, default `"generic"`), `item_metadata` (Text/JSON), `is_equipped` (Boolean, default `False`) |
| `currencies` | `character_id` → FK (1:1), `copper`, `silver`, `electrum`, `gold`, `platinum` |
| `abilities` | `character_id` → FK, `name`, `description`, `max_uses`, `uses`, `is_passive`, `is_active`, `restoration_type` |
| `maps` | `character_id` → FK, `zone_name`, `file_id`, `file_type` |
| `group_members` | `group_id` (BigInt), `user_id` (BigInt) — unique together; tracks every user who has ever written in the group |
| `party_sessions` | `id`, `group_id` (BigInt, unique), `group_title`, `mode` (public/private), `message_chat_id` (BigInt), `message_id` (Int), `started_at` (ISO str), `expires_at` (ISO str) |
| `character_history` | `id`, `character_id` (FK → characters.id, cascade), `timestamp` (String 20, `DD/MM/YYYY HH:MM` UTC), `event_type` (String 50), `description` (Text) — max 50 rows per character (oldest pruned automatically) |

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

Key `action` values: `char_select`, `char_new`, `char_menu`, `char_hp`, `char_ac`, `char_stats`, `char_level`, `char_skills`, `char_spells`, `char_slots`, `char_bag`, `char_currency`, `char_abilities`, `char_multiclass`, `char_class_res`, `char_dice`, `char_notes`, `char_maps`, `char_rest`, `char_conditions`, `char_history`, `char_inspiration`, `char_settings`, `char_party_active`, `char_delete`.

Key `char_spells` sub-actions: `learn`, `learn_conc_yes`, `learn_conc_no`, `detail`, `forget`, `use`, `use_slot`, `activate_conc`, `drop_conc`, `conc_save`, `pin`, `edit_menu`, `edit_<field>` (e.g. `edit_casting_time`, `edit_is_concentration`), `search`, `search_show`.

Key `char_multiclass` sub-actions: `add`, `guided` (show class list), `custom` (free-text entry), `select_guided` (class chosen from list, `extra=class_name`), `skip_subclass`, `remove`, `remove_confirm` (`extra=class_name`).

Key `char_class_res` sub-actions: `menu` (`extra=class_id`), `use` (`item_id=resource_id, extra=class_id`), `restore_one` (`item_id=resource_id, extra=class_id`), `restore_all` (`extra=class_id`), `noop`.

Key `char_conditions` sub-actions: `detail` (`extra=slug`, opens condition detail), `toggle` (`extra=slug`, toggles a binary condition on/off), `exhaust_up` (increases Exhaustion level by 1), `exhaust_down` (decreases Exhaustion level by 1). The `extra` field carries the condition slug (e.g. `"blinded"`, `"exhaustion"`).

Key `char_history` sub-actions: `clear` (deletes all history entries for the character and re-shows the empty screen).

Key `char_bag` sub-actions: `detail` (`item_id=item_id`, opens item detail), `equip` (`item_id=item_id`, toggles equip/unequip), `qty_add` (`item_id=item_id`, +1 quantity), `qty_rem` (`item_id=item_id`, −1 quantity), `delete` / `delete_confirm` (`item_id=item_id`), `skip` (skips an optional field in the add flow).

Key `char_dice` sub-actions: `initiative` (rolls 1d20+DEX modifier directly, saves to `rolls_history` as `["🎯 INI", [total]]`, logs `dice_roll` to character history, triggers party update). No `sub` → show dice menu; `sub` starts with `d` (e.g. `d6`) → count picker; `sub=roll` with `extra="{count}|{die}"` → roll; `sub=clear_history` → clear.

Key `char_skills` sub-actions: `detail` (`extra=slug`, opens the detail screen for that skill), `toggle` (`extra=slug`, toggles proficiency on/off and stays on the detail screen), `roll` (`extra=slug`, rolls d20 + computed bonus, shows result inline on the detail screen and logs to history with event type `dice_roll`). No `extra` → shows the skills list.

Key `char_inspiration` sub-actions: `toggle` (grants the token if inactive, spends it if active, then returns to the inspiration screen). No `sub` → shows the inspiration screen.

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

`bot/utils/formatting.py` provides localized formatters for every character screen: `format_character_summary` (accepts optional `spells`, `abilities`, `equipped_items` for active/equipped status, and `dex_score: int | None` to display initiative bonus in the header), `format_hp`, `format_ac`, `format_ability_scores`, `format_spells`, `format_spell_detail`, `format_spell_slots`, `format_bag`, `format_item_detail`, `format_equipped_items`, `format_currency`, `format_abilities`, `format_maps`, `format_dice_history`, `format_character_active_status`, `format_multiclass_menu`, `format_class_resources`, `format_conditions`, `format_condition_detail`, `format_skills`, `format_skill_detail`, `format_inspiration`. All accept `lang: str = "it"`, use `translator.t()` for all strings, and output MarkdownV2 with `_esc()`. Helper functions `get_ability_labels(lang)`, `get_currency_labels(lang)`, `get_restoration_labels(lang)` return language-aware label dicts.

**Important**: condition description strings stored in YAML locale files are **pre-escaped MarkdownV2** (e.g. `\.` for a literal dot). Do **not** pass them through `_esc()` — use them directly. Only plain-text strings (names, labels) should be escaped.

## Coding Conventions

### Must Follow

- **Async only**: use `python-telegram-bot` v20+ async API. Never use the synchronous API.
- **Bot init**: `Application.builder().token(...).arbitrary_callback_data(True).persistence(persistence).post_init(post_init).build()` pattern. A `PicklePersistence` instance must always be passed — see the *Persistence* section below.
- **Token**: never hardcode — always read from env via `python-dotenv`.
- **GraphQL queries**: generate dynamically using `bot/api/query_builder.py`. Never hardcode query strings.
- **HTTP client**: `httpx.AsyncClient` for all API calls. Use `DnDClient` singleton from `bot/api/client.py`.
- **Handler registration**: all handlers registered in `main.py` via `application.add_handler()`. Character `ConversationHandler` must be registered **before** the party `CallbackQueryHandler`, which must come before the wiki `CallbackQueryHandler`.
- **Wiki callback data**: use `NavAction` dataclass instances. Never encode state as raw strings.
- **Character callback data**: use `CharAction` dataclass instances. The party and wiki `CallbackQueryHandler`s must filter out `CharAction` instances.
- **Party callback data**: use `PartyAction` dataclass instances (`bot/models/party_state.py`). The wiki `CallbackQueryHandler` must also exclude `PartyAction` via `pattern=lambda d: not isinstance(d, CharAction) and not isinstance(d, PartyAction)`.
- **Formatting**: Telegram MarkdownV2 — escape special chars with `_esc()`. Wiki uses `_esc()` from `navigation.py`; character screens use `_esc()` from `utils/formatting.py`.
- **UI language**: All user-facing strings are loaded from YAML locale files via the `Translator` singleton (`bot/utils/i18n.py`). Never hardcode Italian (or any) strings — use `translator.t("key", lang=lang, **kwargs)`. Default language is `"it"`. See *i18n / Localization* section below.
- **Language detection**: call `lang = get_lang(update)` at the top of every handler function that has access to an `Update` object. Pass `lang=lang` to all formatter and keyboard builder calls.
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
3. Add keyboard builder(s) to `bot/keyboards/character.py` — each must accept `lang: str = "it"`.
4. Add formatter(s) to `bot/utils/formatting.py` — each must accept `lang: str = "it"` and use `translator.t()`.
5. Add all new user-facing strings to **both** `bot/locales/it.yaml` and `bot/locales/en.yaml` under an appropriate key hierarchy.
6. Wire the new action into `character_callback_handler()` in `conversation.py`.
7. Add the new state(s) to the `states` dict in `build_character_conversation_handler()`.
8. For every state that awaits **text input**: include `build_cancel_keyboard(char_id, back_action, lang=lang)` in the prompt message (see *Cancel pattern for text inputs* above).

### Spell Management Details

- **Quick-add flow**: name (text) → level (text) → concentration? (inline Sì/No keyboard). All other fields added afterwards via ✏️ Modifica in the detail view.
- **Editable spell fields**: `level`, `casting_time`, `range_area`, `components`, `duration`, `is_concentration` (toggle), `is_ritual` (toggle), `attack_save`, `description`, `higher_level`. Each dispatched via `edit_<field>` sub-action.
- **Concentration**: only one active at a time (`concentrating_spell_id` on `Character`). Auto-activated on "Usa Incantesimo" for concentration spells. Dropped on both short and long rest.
- **Concentration saving throw**: DC = `max(10, damage // 2)`. Roll = `d20 + CON modifier`. Nat 1 always fails, nat 20 always succeeds. On failure, `concentrating_spell_id` is set to `None`.
- **Fuzzy spell search**: `sub="search"` → `ask_spell_search()` (state `CHAR_SPELL_SEARCH`); user types query; `handle_spell_search_text()` runs `rapidfuzz.process.extract(WRatio, score_cutoff=50, limit=20)` against spell names; results shown via `build_spell_search_results_keyboard()`. Back from spell detail to search results uses `extra="search_show"` (routed by `not sub and data.extra == "search_show"` check). Query is stored in `context.user_data["char_spell_search_pending"]`.
- **Pin**: `is_pinned=True` shows the spell in the main menu summary alongside passive active abilities.
- **`format_character_summary`** must receive `spells`, `abilities`, and `equipped_items` lists to display the active/equipped status section. Pass `dex_score` (DEX ability score integer) to show the initiative bonus (`⚡ Ini: +2`) in the character header.
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

### Conditions Details

- **14 binary conditions** (on/off): Blinded, Charmed, Deafened, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Poisoned, Prone, Restrained, Stunned, Unconscious.
- **Exhaustion** condition with levels 0–6 (0 = inactive). Adjusted via ➕/➖ buttons; 6 = death.
- **Storage**: stored as a JSON dict in `Character.conditions` (e.g. `{"blinded": true, "exhaustion": 3}`). All missing keys default to `False`/`0`. Column added via idempotent DB migration.
- **`CONDITIONS_ORDER`** constant in `bot/utils/formatting.py` defines the canonical display order of all 15 slugs. It is imported by `bot/keyboards/character.py` to guarantee consistent ordering.
- **Condition slugs** (snake_case): `blinded`, `charmed`, `deafened`, `frightened`, `grappled`, `incapacitated`, `invisible`, `paralyzed`, `petrified`, `poisoned`, `prone`, `restrained`, `stunned`, `unconscious`, `exhaustion`.
- **Locale keys**: names under `character.conditions.names.<slug>`, descriptions under `character.conditions.desc.<slug>`. Descriptions are **pre-escaped MarkdownV2** in YAML — never pass them through `_esc()`.
- **List view** (`format_conditions`): shows `✅ *Name*` / `⬛ *Name*` per condition; exhaustion shows `✅ *Esaurimento*: {level}/6` when active.
- **Detail view** (`format_condition_detail`): shows name (bold), full D&D 5e description (raw, pre-escaped MarkdownV2), then status line `{marker} {label}` (binary) or `{marker} Livello: *N*/6` (exhaustion).

### Skills Details

- **18 standard D&D 5e skills** each mapped to one of the 6 ability scores. Source of truth: `bot/data/skills.py` — `SKILLS` is a list of `(slug, ability_name)` tuples (alphabetical order); `SKILL_ABILITY_MAP` is an O(1) dict.
- **Proficiency bonus formula**: `max(2, 2 + (total_level - 1) // 4)`. Returns `+2` for level 0 (no class). Exposed as `Character.proficiency_bonus` computed property. Breakpoints: lv1–4 → +2, lv5–8 → +3, lv9–12 → +4, lv13–16 → +5, lv17–20 → +6.
- **Bonus formula**: `bonus = ability_modifier + (proficiency_bonus if proficient else 0)`. Ability modifier = `(score - 10) // 2`.
- **Storage**: `Character.skills` JSON dict (e.g. `{"acrobatics": true, "stealth": false, …}`). Missing keys default to `False` (not proficient). Column added via idempotent DB migration entry in `engine.py`.
- **Skill slugs** (snake_case): `acrobatics`, `animal_handling`, `arcana`, `athletics`, `deception`, `history`, `insight`, `intimidation`, `investigation`, `medicine`, `nature`, `perception`, `performance`, `persuasion`, `religion`, `sleight_of_hand`, `stealth`, `survival`.
- **Skill → ability mapping**: Acrobatics/Sleight of Hand/Stealth → DEX; Animal Handling/Insight/Medicine/Perception/Survival → WIS; Arcana/History/Investigation/Nature/Religion → INT; Athletics → STR; Deception/Intimidation/Performance/Persuasion → CHA.
- **List view** (`format_skills`): shows proficiency bonus for current level + instruction line. Each skill button shows `{prof_icon} {name} ({abbr}): {bonus}`.
- **Detail view** (`format_skill_detail`): shows skill name (bold), ability abbreviation + bonus, proficiency status, D&D 5e description. Optional last-roll line at bottom when `last_roll=(die_result, total)` is passed.
- **Keyboard flow**: List → tap skill → Detail (`sub="detail"`, `extra=slug`). On detail: toggle button (`sub="toggle"`), roll button (`sub="roll"`), ⬅️ Back → list.
- **Toggle**: stays on the detail screen after toggling (does NOT return to list). Logs `skill_change` event to history.
- **Roll**: `random.randint(1, 20) + bonus`. Result shown inline on the detail screen. Logged to history with event type `dice_roll` and description `"Roll {skill_name} (d20({die}) {bonus} = {total})"`.
- **Locale keys**: `character.skills.names.<slug>` (18 names), `character.skills.desc.<slug>` (18 plain-text descriptions, passed through `_esc()` in the formatter — NOT pre-escaped in YAML), `character.skills.ability_abbr.<ability>` (6 abbreviations), plus `title`, `prof_bonus_label`, `instruction`, `updated`, `proficient_icon`, `not_proficient_icon`, `detail_proficient`, `detail_not_proficient`, `btn_toggle_proficient`, `btn_toggle_not_proficient`, `btn_roll`, `roll_result`, `roll_logged`.
- **Button position**: 🎯 Abilità appears immediately after 📊 Punteggi Abilità in the character main menu.

### Heroic Inspiration Details

- **Rule**: D&D 5e 2024 mechanic — a character either has the token (`True`) or doesn't (`False`). When held, it can be spent to reroll any die.
- **Storage**: `Character.heroic_inspiration` (Boolean, default `False`). Column added via idempotent DB migration entry in `engine.py`.
- **Handler**: `bot/handlers/character/inspiration.py` — `show_inspiration_menu(update, context, char_id)` and `toggle_heroic_inspiration(update, context, char_id)`. No text input needed — all interactions are pure callbacks.
- **State**: `CHAR_INSPIRATION_MENU` (state 57, the 58th total state in `range(58)`).
- **Action routing**: `char_inspiration` with no `sub` → show screen; `sub="toggle"` → grant if inactive / spend if active.
- **Character summary**: when `char.heroic_inspiration == True`, `format_character_active_status` appends the line `✨ *Ispirazione Eroica attiva*` to the active-status section of the main menu summary.
- **Screen** (`format_inspiration`): shows title, status line (`✅ Hai l'Ispirazione Eroica!` / `⬛ Non hai l'Ispirazione Eroica.`), and a plain-text description. Button label switches between `✨ Ottieni Ispirazione` and `💫 Usa Ispirazione` depending on current state.
- **History**: toggle fires `asyncio.create_task(_log(char_id, "inspiration_change", ...))` — fire-and-forget.
- **Rest behaviour**: inspiration is **not** reset automatically on rest (the DM awards it manually).
- **Locale keys**: all under `character.inspiration.*` — `title`, `status_active`, `status_inactive`, `description`, `btn_grant`, `btn_spend`, `granted`, `spent`, `active_label`. Menu button: `character.menu.btn_inspiration`. History label: `character.history.inspiration_change`.

### Dice Details

- **Dice types**: d4, d6, d8, d10, d12, d20, d100. Selecting a die opens a count picker (1–10); confirming rolls `{count}{die}` and saves to `rolls_history` as `["{count}{die}", [list_of_results]]`.
- **Initiative roll**: dedicated `🎯 Iniziativa` button in `build_dice_keyboard` (`sub="initiative"`). Rolls 1d20 + DEX modifier in a single tap — no count picker. Saved to `rolls_history` as `["🎯 INI", [total]]` where `total = die + dex_mod`. Result screen shows full breakdown: `d20: {die} + DES: {mod} = {total}`.
- **`roll_initiative`** in `dice.py`: loads `AbilityScore` for `dexterity` from DB (defaults to 10 if not set), rolls, appends to history, fires `_trigger_party_update` and `_log` (event type `dice_roll`).
- **`format_character_header`** accepts optional `dex_score: int | None` — when provided adds `⚡ Ini: {modifier}` line below the CA line. Only passed from `menu.py` (main menu); other screens that call the header do not pass it.
- **Rolls history storage**: JSON list on `Character.rolls_history`, capped at 50 entries. Format: `[label, list_of_values]` — e.g. `["3d6", [2, 5, 4]]` or `["🎯 INI", [15]]`.
- **Locale keys**: `character.dice.btn_initiative`, `character.dice.initiative_title`, `character.dice.initiative_result` (MarkdownV2 with `{die}`, `{mod_str}`, `{total}`), `character.common.initiative_label`.
### Bag / Inventory Details

- **Item types**: `generic` (default), `weapon`, `armor`, `shield`, `consumable`, `tool`. Chosen via inline keyboard at the start of the add-item flow.
- **Type icons**: shown in the bag list and detail — 🗡️ weapon, 🛡️ armor, 🔰 shield, 🧪 consumable, 🔧 tool, 📦 generic.
- **Add-item flow** (multi-step):
  1. Name (text, `CHAR_BAG_ADD_NAME`)
  2. Quantity (text, `CHAR_BAG_ADD_QUANTITY`)
  3. Weight (text, `CHAR_BAG_ADD_WEIGHT`) — required for all types; shown with cancel keyboard
  4. Item type selection (inline, `CHAR_BAG_ADD_INLINE`, `step="type"`)
  5. Type-specific inline steps dispatched through `step` key in `context.user_data["char_bag_pending"]`:
     - **Weapon**: damage type → weapon type → properties multi-select (state `CHAR_BAG_ADD_INLINE`)
     - **Weapon** optional: damage dice (text, `CHAR_BAG_ADD_DAMAGE_DICE`)
     - **Armor**: armor type → stealth penalty (state `CHAR_BAG_ADD_INLINE`)
     - **Armor** optional: AC value (text, `CHAR_BAG_ADD_AC_VALUE`), strength requirement (text, `CHAR_BAG_ADD_STR_REQ`)
     - **Shield** optional: AC bonus (text, `CHAR_BAG_ADD_AC_VALUE`)
     - **Consumable** optional: effect (text, `CHAR_BAG_ADD_EFFECT`)
     - **Tool** optional: tool type (text, `CHAR_BAG_ADD_TOOL_TYPE`)
  6. Description (text, `CHAR_BAG_ADD_DESCRIPTION`) — optional; "⏭️ Salta" button available
- **Optional steps**: skippable via a "⏭️ Salta" button that routes through `handle_bag_skip` callback handler.
- **Metadata storage**: the `item_metadata` column stores a JSON string. Structure per type:
  - **weapon**: `{"damage_dice": "1d8|null", "damage_type": "str", "weapon_type": "str", "properties": ["str", …]}`
  - **armor**: `{"armor_type": "str", "ac_value": int|null, "stealth_disadvantage": bool, "strength_req": int|null}`
  - **shield**: `{"ac_bonus": int|null}`
  - **consumable**: `{"effect": "str|null"}`
  - **tool**: `{"tool_type": "str|null"}`
  - **generic**: `{}` (empty dict)
- **Equip / unequip** (`toggle_equip_item`): only Weapon, Armor, Shield support equipping.
  - **Armor**: at most 1 equipped at a time (auto-unequips the previous one). On equip, sets `character.base_armor_class = ac_value`; on unequip resets to `10`.
  - **Shield**: at most 1 equipped at a time. On equip, sets `character.shield_armor_class = ac_bonus`; on unequip resets to `0`.
  - **Weapon**: multiple can be equipped simultaneously (simple toggle).
  - After equipping/unequipping Armor or Shield, `maybe_update_party_message` is called (fire-and-forget) to sync the party display.
- **`is_equipped` display**: equipped items show a ⚔️/🛡️ marker in the bag list and "✅ Equipaggiato / ❌ Non equipaggiato" in the detail view.
- **Deduplication** (stacking): only applies to `item_type == "generic"` — same as the original behaviour.
- **`format_item_detail`**: accepts a `dict` with keys `name, description, weight, quantity, item_type, item_metadata, is_equipped`. Metadata fields are rendered only when present/non-null.
- **`format_equipped_items`**: accepts `list[dict]` with keys `name, item_type, item_metadata`. Called from `menu.py` to populate the equipped-items section of the character summary.
- **`format_character_summary`** accepts `equipped_items: list | None = None` and `dex_score: int | None = None`. When `dex_score` is provided, `format_character_header` shows the initiative line `⚡ Ini: {modifier}` below the AC line. When `equipped_items` is provided, renders an equipped-items block at the bottom of the summary.
- **Conversation states added** (6 new): `CHAR_BAG_ADD_INLINE`, `CHAR_BAG_ADD_DAMAGE_DICE`, `CHAR_BAG_ADD_EFFECT`, `CHAR_BAG_ADD_AC_VALUE`, `CHAR_BAG_ADD_STR_REQ`, `CHAR_BAG_ADD_TOOL_TYPE`. Total state count: **58** (including `CHAR_INSPIRATION_MENU` added later).
- **Locale keys**: all under `character.bag.*` — `item_types.*` (6 type labels), `item_type_icons.*`, weapon/armor/shield/consumable/tool metadata labels, `btn_equip`, `btn_unequip`, `equipped_label`, `not_equipped_label`, `btn_qty_add` (`"➕ +1"`), `btn_qty_rem` (`"➖ -1"`).
- **Button labels**: must NOT contain MarkdownV2 escaping. `btn_qty_add`/`btn_qty_rem` use plain `+1`/`-1`, not `\+1`/`\-1`.

### Character History Details
- **DB table**: `character_history` (`id`, `character_id` FK cascade, `timestamp` String 20, `event_type` String 50, `description` Text). New table — auto-created by `Base.metadata.create_all`, no migration entry needed.
- **Helper module**: `bot/db/history.py` — `log_history_event(char_id, event_type, description)` inserts a row and prunes oldest if count > `MAX_HISTORY = 50`; `get_history(char_id)` returns rows newest-first; `clear_history(char_id)` deletes all rows.
- **Timestamps**: stored as `DD/MM/YYYY HH:MM` UTC strings (String 20) — human-readable, timezone-agnostic.
- **Event types** (string slugs): `hp_change`, `rest`, `ac_change`, `stats_change`, `spell_slot_change`, `spell_change`, `bag_change`, `currency_change`, `ability_change`, `multiclass_change`, `level_change`, `condition_change`, `skill_change`, `dice_roll`, `inspiration_change`.
- **Logging pattern**: every handler that modifies character state fires `asyncio.create_task(_log(char_id, event_type, description))` — fire-and-forget, never blocks user response. Each handler file defines its own `async def _log(char_id, event_type, description)` helper at the bottom that wraps `log_history_event` in a try/except.
- **Display**: `show_history()` in `handlers/character/history.py` splits the formatted text at **3800 chars** per Telegram message. The first message gets the `🗑️ Cancella Storico` + `🏠 Menu` keyboard; extra messages are plain text. Extra message IDs are stored as `[(chat_id, msg_id), …]` in `context.user_data["char_history_extra_msgs"]` (`HISTORY_EXTRA_MSGS_KEY` constant).
- **Multi-message cleanup**: `show_character_menu()` in `menu.py` imports `HISTORY_EXTRA_MSGS_KEY` and deletes all extra messages at the start before editing the primary message to the menu. This ensures no orphaned messages remain when navigating back.
- **Clear button**: `sub="clear"` on `char_history` action → `handle_clear_history()` → calls `clear_history`, re-shows the empty history screen.
- **Locale keys**: `character.history.title`, `character.history.empty`, `character.history.count`, `character.history.part_indicator`, `character.history.btn_clear`, `character.history.cleared`, `character.history.other`, and `character.history.events.<slug>` for each event type label. Menu button: `character.menu.btn_history`.

### Party Feature Details

- **Commands**: `/party` (group-only) and `/party_stop`. Both refuse to run outside groups.
- **Session lifetime**: 48 hours. Stored as ISO timestamp strings in `party_sessions.expires_at`. The countdown is displayed in every party message and updated on each HP change.
- **Group member tracking**: a `MessageHandler` (registered with `group=1` so it runs alongside other handlers) records every user who sends a text message in a group into the `group_members` table. The `/party` command issuer is also tracked on invocation.
- **Active character selection**: `Character.is_party_active` (bool, default `False`) flags the character used in party display. Toggle via `char_party_active` action → `toggle_party_active()` in `settings.py`. Only one character per `user_id` can be `is_party_active=True` at a time (others are set to `False` automatically). If a user has exactly **one** character and none is active, it is included automatically in the party list.
- **Mode selection flow**:
  - `/party` → shows `build_party_mode_keyboard(group_id)` with 🌐 Pubblica / 🔒 Privata.
  - **Public mode** (`party_mode`, `extra="public"`): sends the party message in the group, stores `message_chat_id = group_id` in the session.
  - **Private mode** (`party_mode`, `extra="private"`): edits the mode-selection message to show a "master presses here" prompt with `build_party_master_reveal_keyboard(group_id)`. The master presses the button (`party_master_reveal`) → bot sends a private message to the master → stores `message_chat_id = master.user_id` in the session.
- **Real-time updates**: `maybe_update_party_message(char_id, bot)` in `handlers/party.py` finds all active `PartySession`s that include the character's user (via `GroupMember` join), rebuilds the message text, and calls `bot.edit_message_text`. It is invoked as `asyncio.create_task(_trigger_party_update(...))` — fire-and-forget, never blocks the user response — from:
  - `hit_points.py` after every HP change (set max, set current, damage, heal) and rest
  - `armor_class.py` after every AC change (base, shield, magic)
  - `bag.py` after equip/unequip of Armor or Shield (since CA changes)
  - `conditions.py` after every condition toggle or exhaustion adjustment
  - `dice.py` after every dice roll
- **Session cleanup**: if `edit_message_text` raises `BadRequest` (message too old/deleted), the session row is deleted. `/party_stop` also edits the party message to "🛑 Sessione party terminata." before deleting the session.
- **Party message format** (`bot/utils/party_formatting.py`): MarkdownV2 with group title, countdown, and per-character rows showing name, class/level, HP bar, AC, active conditions (omitted when none), and last dice roll (omitted when history is empty). `format_party_message(characters, session, lang="it")` takes `list[tuple[Character, str | None]]` (character + optional username) and the active `PartySession`. Fire-and-forget callers (no `Update`) pass `lang="it"` explicitly. Helper functions `_get_active_conditions(char, lang)` and `_get_last_roll(char)` return compact strings or `""` to conditionally include those lines.
- **`build_settings_keyboard`** now accepts `is_party_active: bool` to render the current toggle state.

### i18n / Localization

- **`Translator` singleton** (`bot/utils/i18n.py`): loaded at import time from `bot/locales/`. Key lookup uses dot-notation (e.g. `"character.hp.title"`). Fallback chain: `user_lang → "it" → key itself` (missing key returns the key string and logs a warning). Kwarg interpolation via `str.format_map()` (e.g. `translator.t("character.hp.current_label", lang=lang, current=45, max=60)`).
- **Language detection**: `get_lang(update: Update) -> str` normalises `update.effective_user.language_code` (e.g. `"it-IT"` → `"it"`). Falls back to `"it"` if the code is not among loaded locales. Import from `bot.utils.i18n`.
- **Hot-reload**: `translator.start_watcher()` is started as an asyncio task in `post_init`. It checks file mtimes every 300 seconds and reloads changed YAML files without restarting the bot. Locale edits take effect within 5 minutes automatically.
- **Locale files**: `bot/locales/it.yaml` and `bot/locales/en.yaml`. Keys are hierarchical YAML — match the structure in the existing files when adding new keys.
- **Button labels vs message text**: button label keys must NOT contain MarkdownV2 escaping (e.g. `(Liv. 5)` not `\(Liv\. 5\)`). Message text keys may contain MarkdownV2 escaping where needed (e.g. `*bold*`).

#### Adding a new locale string

1. Add the key (and Italian text) to `bot/locales/it.yaml`.
2. Add the same key (with the English translation) to `bot/locales/en.yaml`.
3. Use it in code via `translator.t("your.key", lang=lang, **kwargs)`.
4. Never skip step 2 — a missing key in `en.yaml` falls back to Italian but logs a warning.

#### Adding a new language

1. Copy `bot/locales/it.yaml` to `bot/locales/<code>.yaml` (e.g. `de.yaml`).
2. Translate all values.
3. The `Translator` automatically discovers and loads any `.yaml` file present in `bot/locales/` at startup.

### Persistence

The bot uses `PicklePersistence` (PTB built-in) to survive restarts. Configuration lives in `main.py`.

```python
persistence = PicklePersistence(
    filepath="data/persistence.pkl",
    store_data=PersistenceInput(
        user_data=True,
        chat_data=False,
        bot_data=False,
        callback_data=True,
    ),
    update_interval=60,
)
```

| What | Persisted | Why |
|---|---|---|
| `user_data` | ✅ | Stores `"active_char_id"` (avoids re-selection after restart) and all `*_pending` mid-flow keys |
| `chat_data` | ❌ | Not used |
| `bot_data` | ❌ | Not used |
| `callback_data` cache | ✅ | **Required** with `arbitrary_callback_data=True` — without it every inline button becomes invalid after a restart |
| `ConversationHandler` state | ✅ | `persistent=True` + `name="character_conversation"` are set on the handler — the user resumes at the exact menu/step they were in |

**Important rules:**
- `os.makedirs("data", exist_ok=True)` must be called **before** `Application.builder()` — PTB reads the pickle file at `build()` time, before `post_init` (which is where `init_db()` creates `data/`).
- `data/persistence.pkl` is already covered by `/data/` in `.gitignore` — never commit it.
- `CharAction`, `NavAction`, and `PartyAction` are frozen dataclasses and are natively picklable — no custom `__reduce__` needed.
- The `*_pending` keys (e.g. `char_hp_pending_op`, `char_spell_pending`) are restored on restart together with the conversation state, so multi-step flows resume seamlessly. `/stop` clears all of them if the user wants a clean slate.

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

