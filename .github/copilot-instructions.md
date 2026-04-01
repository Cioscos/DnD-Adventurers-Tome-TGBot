# Copilot Instructions

## Repository
- The remote repository is https://github.com/Cioscos/dnd_bot_revamped.git
- Always commit and push changes to this repository.

## MCP Servers
- ALWAYS use Context7 MCP server to retrieve up-to-date documentation for every library before writing code.
- ALWAYS use the local dnd-mcp server to understand D&D domain data and relationships before designing GraphQL queries.

## Best Practices
- Use python-telegram-bot v20+ with full async/await support. Never use the synchronous API.
- Use `Application.builder().token(...).build()` pattern for bot initialization.
- Use `ConversationHandler` or encoded `callback_data` to manage multi-step navigation state.
- Never hardcode the bot token. Always read it from environment variables via `python-dotenv`.
- All GraphQL queries must be defined as constants in `api/queries.py`. Never inline query strings.
- Use `httpx.AsyncClient` or the `gql` library with async transport for all API calls.
- All handlers must be registered in `main.py` using `application.add_handler()`.
- Format bot messages with Telegram MarkdownV2 and escape special characters properly.
- Handle `telegram.error.BadRequest` and network errors in every handler.
- Log errors using the standard `logging` module, not `print()`.
- Keep handlers thin: business logic and API calls belong in dedicated modules, not in handler functions.
- Write type hints on all functions.
- Each module must have a docstring explaining its purpose.
- Use `InlineKeyboardMarkup` with `InlineKeyboardButton` for all navigation. Never use reply keyboards for navigation.
- Paginate long lists (more than 10 items) using "Next ➡️" / "⬅️ Prev" buttons.
- Keep `callback_data` under 64 bytes (Telegram limit): use short keys or a server-side state store if needed.
