"""Internationalisation (i18n) support for the D&D bot.

Provides a :class:`Translator` singleton that loads YAML locale files from
``bot/locales/`` and exposes a :meth:`~Translator.t` method for key-based
string lookup with interpolation.  A background asyncio task automatically
hot-reloads locale files when their modification time changes.

Usage example::

    from bot.utils.i18n import translator, get_lang
    from telegram import Update

    lang = get_lang(update)
    text = translator.t("start.welcome", lang=lang)
    text_with_vars = translator.t("character.hp.prompt_damage", lang=lang)

Locale files live in ``bot/locales/{lang_code}.yaml`` (e.g. ``it.yaml``,
``en.yaml``).  Keys use dot-notation for nested lookup:
``"character.hp.title"`` maps to ``data["character"]["hp"]["title"]``.

Fallback chain: ``user_lang`` → ``default_lang`` ("it") → the key itself.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml
from telegram import Update

logger = logging.getLogger(__name__)

# Directory containing YAML locale files, relative to this module's parent (bot/)
_LOCALES_DIR = Path(__file__).parent.parent / "locales"

# How often (seconds) to check for file changes
_DEFAULT_RELOAD_INTERVAL = 300


class Translator:
    """Thread-safe (GIL) locale loader and string resolver.

    Parameters
    ----------
    locales_dir:
        Directory that contains ``{lang}.yaml`` files.
    default_lang:
        Fallback language code used when the user's language is not supported.
    reload_interval:
        Seconds between mtime checks for hot-reload.
    """

    def __init__(
        self,
        locales_dir: Path = _LOCALES_DIR,
        default_lang: str = "it",
        reload_interval: int = _DEFAULT_RELOAD_INTERVAL,
    ) -> None:
        self._locales_dir = locales_dir
        self.default_lang = default_lang
        self._reload_interval = reload_interval

        # lang_code → parsed YAML dict
        self._locales: dict[str, dict[str, Any]] = {}
        # lang_code → last known mtime (float)
        self._mtimes: dict[str, float] = {}

        self._load_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def t(self, key: str, lang: str = "it", **kwargs: Any) -> str:
        """Return the translated string for *key* in *lang*.

        Falls back to *default_lang* then to the bare *key* when not found.
        Named placeholders in the YAML value are substituted using
        ``str.format_map(kwargs)``.

        Parameters
        ----------
        key:
            Dot-separated path, e.g. ``"character.hp.prompt_damage"``.
        lang:
            BCP-47 base language code, e.g. ``"it"`` or ``"en"``.
        **kwargs:
            Variables to interpolate into the translated string.
        """
        # Resolve in preferred lang, then default, then return key
        value = self._lookup(key, lang)
        if value is None and lang != self.default_lang:
            value = self._lookup(key, self.default_lang)
        if value is None:
            logger.warning("Missing i18n key: %r (lang=%s)", key, lang)
            return key

        if kwargs:
            try:
                return str(value).format_map(kwargs)
            except (KeyError, IndexError, ValueError) as exc:
                logger.warning("i18n interpolation error for key %r: %s", key, exc)
                return str(value)
        return str(value)

    def get_lang(self, update: Update) -> str:
        """Extract and normalise the language code from a PTB *update*.

        Returns the normalised base code (e.g. ``"it"``, ``"en"``) if it is
        supported, otherwise :attr:`default_lang`.
        """
        user = getattr(update, "effective_user", None)
        if user is None:
            return self.default_lang
        lc: str = user.language_code or ""
        # "it-IT" → "it", "en-US" → "en"
        base = lc.split("-")[0].lower()
        return base if base in self._locales else self.default_lang

    def reload(self) -> None:
        """Force-reload all locale files from disk."""
        self._load_all()
        logger.info("i18n: all locales reloaded.")

    async def start_watcher(self) -> None:
        """Asyncio coroutine that checks locale file mtimes every N seconds.

        Start this as a fire-and-forget task in the bot's ``post_init``::

            asyncio.create_task(translator.start_watcher())
        """
        logger.info(
            "i18n watcher started (interval=%ds, dir=%s)",
            self._reload_interval,
            self._locales_dir,
        )
        while True:
            await asyncio.sleep(self._reload_interval)
            self._check_and_reload()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Load every ``*.yaml`` file found in the locales directory."""
        if not self._locales_dir.exists():
            logger.warning("i18n locales directory not found: %s", self._locales_dir)
            return
        for path in sorted(self._locales_dir.glob("*.yaml")):
            lang = path.stem
            self._load_locale(lang, path)

    def _load_locale(self, lang: str, path: Path) -> None:
        """Parse a single YAML locale file and cache it."""
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            self._locales[lang] = data
            self._mtimes[lang] = path.stat().st_mtime
            logger.debug("i18n: loaded locale '%s' from %s", lang, path)
        except Exception as exc:
            logger.error("i18n: failed to load locale '%s' (%s): %s", lang, path, exc)

    def _check_and_reload(self) -> None:
        """Check mtimes and reload any locale file that has changed."""
        if not self._locales_dir.exists():
            return
        for path in self._locales_dir.glob("*.yaml"):
            lang = path.stem
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime != self._mtimes.get(lang, 0.0):
                old = lang in self._locales
                self._load_locale(lang, path)
                action = "reloaded" if old else "loaded new"
                logger.info("i18n watcher: %s locale '%s'", action, lang)

    def _lookup(self, key: str, lang: str) -> str | None:
        """Navigate the nested locale dict via dot-notation key.

        Returns ``None`` if the key or language is not found.
        """
        data: Any = self._locales.get(lang)
        if data is None:
            return None
        for part in key.split("."):
            if not isinstance(data, dict):
                return None
            data = data.get(part)
            if data is None:
                return None
        return data if not isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

#: Global :class:`Translator` instance.  Import and use directly::
#:
#:     from bot.utils.i18n import translator, get_lang
translator = Translator()


def get_lang(update: Update) -> str:
    """Convenience wrapper around :meth:`Translator.get_lang`."""
    return translator.get_lang(update)
