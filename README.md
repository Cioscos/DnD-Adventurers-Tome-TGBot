# 🎲 D&D 5e Telegram Explorer Bot

An interactive Telegram bot that lets you browse the entire **D&D 5th Edition** compendium — spells, monsters, classes, races, equipment, and more — right inside Telegram, powered by the [D&D 5e GraphQL API](https://www.dnd5eapi.co/graphql/2014).

## ✨ Features

- **11 browsable categories**: Spells, Monsters, Classes, Races, Equipment, Conditions, Magic Items, Feats, Rules, Backgrounds, Weapon Properties
- **N-level deep navigation**: Categories → Paginated item list → Full item detail → Navigable sub-entities (e.g. Class → Wizard → 📂 Subclasses → Evocation)
- **Dynamic schema discovery**: At startup the bot introspects the GraphQL API and automatically discovers navigable relationships between entities
- **Smart pagination**: 10 items per page with Next ➡️ / ⬅️ Prev buttons (server-side for top-level lists, client-side for sub-lists)
- **Rich formatting**: Detailed item views formatted in Telegram MarkdownV2 with custom formatters for major types and a generic formatter for all others
- **Arbitrary callback data**: Uses PTB's callback-data cache so navigation state is a Python dataclass — no 64-byte string limit
- **Fully async**: All API calls use `httpx.AsyncClient` for non-blocking I/O
- **Graceful error handling**: User-friendly messages on API failures; partial GraphQL data returned when possible

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Setup

```bash
# Clone the repository
git clone https://github.com/Cioscos/dnd_bot_revamped.git
cd dnd_bot_revamped

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure the bot token
cp .env.example .env
# Edit .env and paste your BOT_TOKEN
```

### Run

```bash
python -m bot.main
```

The bot will start polling for updates. Open your bot in Telegram and send `/start`!

## 📁 Project Structure

```
bot/
├── main.py                  # Entry point — builds Application, inits schema, starts polling
├── handlers/
│   ├── start.py             # /start command handler
│   └── navigation.py        # N-level callback handlers & detail formatters
├── api/
│   ├── client.py            # Async GraphQL client (httpx)
│   ├── introspection.py     # __schema query & parser
│   └── query_builder.py     # Dynamic GraphQL query generation
├── schema/
│   ├── types.py             # FieldInfo, TypeInfo, MenuCategory dataclasses
│   └── registry.py          # SchemaRegistry — introspection cache & navigable field discovery
├── keyboards/
│   └── builder.py           # Dynamic InlineKeyboardMarkup builders
└── models/
    └── state.py             # NavAction callback dataclass & helpers
```

## 🎮 Usage

1. Start the bot with `/start`
2. Tap a category button (e.g. ⚔️ Classes)
3. Browse the paginated list and tap an item (e.g. Wizard)
4. View the full detail card with 📂 buttons for related entities
5. Tap 📂 Subclasses to drill into navigable sub-entities
6. Use ⬅️ Back to return or 🏠 Menu to go home

## 🔧 Configuration

| Variable    | Description                          | Required |
|-------------|--------------------------------------|----------|
| `BOT_TOKEN` | Telegram Bot API token from BotFather | ✅       |

## 📜 License

This project is for educational and personal use. D&D content is provided by the open [D&D 5e API](https://www.dnd5eapi.co/) under the SRD (Systems Reference Document).
