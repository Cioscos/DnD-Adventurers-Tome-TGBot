"""FastAPI application for the D&D Bot Mini App backend.

Exposes REST endpoints for all character management features.
Authentication is done via Telegram WebApp initData HMAC verification
(see api/auth.py). Shares the same SQLite database as the Telegram bot.

Run with:
    uvicorn api.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before importing routers — auth.py reads BOT_TOKEN at module level.
load_dotenv()

from api.routers import (
    abilities,
    characters,
    classes,
    currency,
    dice,
    history,
    hp,
    items,
    maps,
    notes,
    spell_slots,
    spells,
    stats,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CORS: allow only the GitHub Pages origin (add localhost for dev)
# ---------------------------------------------------------------------------

_ALLOWED_ORIGINS = [
    "https://cioscos.github.io",
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview
]

app = FastAPI(
    title="D&D Bot API",
    description="REST backend for the D&D Bot Telegram Mini App",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["X-Telegram-Init-Data", "Content-Type", "Accept"],
)

# ---------------------------------------------------------------------------
# Health check (no auth)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Register all routers
# ---------------------------------------------------------------------------

app.include_router(characters.router)
app.include_router(hp.router)
app.include_router(stats.router)
app.include_router(classes.router)
app.include_router(spells.router)
app.include_router(spell_slots.router)
app.include_router(items.router)
app.include_router(currency.router)
app.include_router(abilities.router)
app.include_router(notes.router)
app.include_router(maps.router)
app.include_router(dice.router)
app.include_router(history.router)
