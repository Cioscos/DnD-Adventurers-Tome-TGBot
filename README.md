# D&D 5e Telegram Bot (Wiki + Characters + Party)

Async Telegram bot for D&D 5e with three integrated core areas:

1. D&D 5e Wiki via GraphQL (dynamic deep navigation)
2. Full character management with SQLite persistence
3. Group Party session with live updates

Italian documentation is available at `docs/README.it.md`.

## Feature Overview

### 1) D&D 5e Wiki

- GraphQL endpoint: `https://www.dnd5eapi.co/graphql/2014`
- Automatic schema introspection at startup (types, root queries, navigable fields)
- 11 categories: Spells, Monsters, Classes, Races, Equipment, Conditions, Magic Items, Feats, Rules, Backgrounds, Weapon Properties
- N-level navigation: categories -> paginated list -> detail -> navigable sub-entities
- Dynamically generated GraphQL queries (no hardcoded query strings)
- Union type support with `__typename` + inline fragments
- Partial error handling: when possible, the bot still shows available data even with GraphQL errors

### 2) Character Management

- Character creation/selection/deletion
- HP (max/current, damage, healing, rest), AC (base/shield/magic)
- Ability scores + modifiers
- Full skills (18) with proficiency and `d20` roll + bonus
- Spells: learn, edit fields, consume slots, concentration, fuzzy search
- Spell slots, typed inventory, equip/unequip with AC sync
- Currencies, special abilities, maps, text and voice notes
- Multiclassing with auto-generated class resources and level management
- D&D 5e conditions (14 binary + Exhaustion 0-6)
- Heroic inspiration (grant/use toggle)
- Character change history (max 50 events)
- Conversation and callback state persistence via `PicklePersistence`

### 3) Group Party

- Group commands: `/party` and `/party_stop`
- Display modes: public in group or private to the GM
- Party message updates in real time on HP/AC/conditions/rolls
- Session countdown (48 hours)
- Includes HP bar, AC, active conditions, and latest roll per character

## Commands and Chat Scope

| Command | Scope | Notes |
|---|---|---|
| `/start` | Private chat only | Shows main menu with `Wiki D&D` and `My character`; in groups it shows a warning and exits |
| `/party` | Groups/supergroups only | Starts party mode selection |
| `/party_stop` | Groups/supergroups only | Stops active party session |
| `/stop` | Private (global/conversation fallback) | Cancels current flow and clears `*_pending` keys |

## Tech Stack

- Python 3.10+
- `python-telegram-bot[callback-data] >= 22.0`
- `httpx >= 0.27.0`
- `sqlalchemy >= 2.0` + `aiosqlite >= 0.20`
- `python-dotenv >= 1.0.0`
- `rapidfuzz >= 3.0`
- `pyyaml >= 6.0`

## Installation

### Windows (PowerShell)

```powershell
git clone https://github.com/Cioscos/dnd_bot_revamped.git
Set-Location dnd_bot_revamped
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
BOT_TOKEN=your_bot_token_here
DEV_CHAT_ID=optional_telegram_chat_id
DB_PATH=data/dnd_bot.db
```

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | Yes | Telegram bot token |
| `DEV_CHAT_ID` | No | Developer chat ID used for unhandled error tracebacks |
| `DB_PATH` | No | SQLite DB path (default: `data/dnd_bot.db`) |

## Run

```powershell
python -m bot.main
```

## Architecture (Summary)

```text
bot/
|- main.py                 # app bootstrap, persistence, handler registration, error handler
|- api/                    # GraphQL client, introspection, dynamic query builder
|- schema/                 # schema registry and navigable fields
|- handlers/
|  |- start.py             # /start (private only)
|  |- navigation.py        # wiki callbacks
|  |- party.py             # /party, /party_stop, live update
|  '- character/           # conversation and character features
|- db/                     # async engine, ORM models, history helper
|- keyboards/              # inline keyboards for wiki/character/party
|- locales/                # i18n YAML (it/en)
'- utils/                  # MarkdownV2 formatters, i18n, party formatting
```

## i18n and Formatting

- User language detected from `update.effective_user.language_code`
- Supported locales: `it` (default) and `en`
- User-facing strings in `bot/locales/it.yaml` and `bot/locales/en.yaml`
- Message output in MarkdownV2 with dedicated escaping helpers

## Persistence

- Character database: SQLite (default `data/dnd_bot.db`)
- Bot state: `data/persistence.pkl` (`user_data`, callback cache, conversation state)
- Dataclass callbacks (`NavAction`, `CharAction`, `PartyAction`) remain valid after restart

## Operational Notes

- The bot uses inline keyboards only for navigation
- DB sessions are handled through async context managers
- Unhandled errors: local logging + traceback forwarding to `DEV_CHAT_ID` when configured

## License

Project intended for educational/personal use. D&D content is sourced from [D&D 5e API](https://www.dnd5eapi.co/) under SRD.
