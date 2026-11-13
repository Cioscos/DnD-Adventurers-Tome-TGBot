"""Catalogo degli strumenti (Manuale del Giocatore 2014 pag. 154, 2024 pag. 220-221).

Nomi italiani dal manuale 2014; ``ability`` è la caratteristica che il 2024 indica per lo strumento (nel 2014 la prova
non è legata a una caratteristica e la sceglie il giocatore). Le chiavi restano stabili: le salva
``Character.tool_proficiencies``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Category = Literal["artisan", "gaming", "instrument", "kit", "thieves", "vehicle"]


@dataclass(frozen=True)
class ToolSpec:
    key: str
    it: str
    en: str
    category: Category
    ability: str


_S, _D, _I, _W, _C = "strength", "dexterity", "intelligence", "wisdom", "charisma"

_ROWS: tuple[tuple[str, str, str, Category, str], ...] = (
    ("alchemists_supplies", "Scorte da alchimista", "Alchemist's supplies", "artisan", _I),
    ("brewers_supplies", "Scorte da mescitore", "Brewer's supplies", "artisan", _I),
    ("calligraphers_supplies", "Scorte da calligrafo", "Calligrapher's supplies", "artisan", _D),
    ("carpenters_tools", "Strumenti da falegname", "Carpenter's tools", "artisan", _S),
    ("cartographers_tools", "Strumenti da cartografo", "Cartographer's tools", "artisan", _W),
    ("cobblers_tools", "Strumenti da calzolaio", "Cobbler's tools", "artisan", _D),
    ("cooks_utensils", "Utensili da cuoco", "Cook's utensils", "artisan", _W),
    ("glassblowers_tools", "Strumenti da soffiatore", "Glassblower's tools", "artisan", _I),
    ("jewelers_tools", "Strumenti da gioielliere", "Jeweler's tools", "artisan", _I),
    ("leatherworkers_tools", "Strumenti da conciatore", "Leatherworker's tools", "artisan", _D),
    ("masons_tools", "Strumenti da costruttore", "Mason's tools", "artisan", _S),
    ("painters_supplies", "Strumenti da pittore", "Painter's supplies", "artisan", _W),
    ("potters_tools", "Strumenti da vasaio", "Potter's tools", "artisan", _I),
    ("smiths_tools", "Strumenti da fabbro", "Smith's tools", "artisan", _S),
    ("tinkers_tools", "Strumenti da inventore", "Tinker's tools", "artisan", _D),
    ("weavers_tools", "Strumenti da tessitore", "Weaver's tools", "artisan", _D),
    ("woodcarvers_tools", "Strumenti da intagliatore", "Woodcarver's tools", "artisan", _D),
    ("dice_set", "Dadi", "Dice set", "gaming", _W),
    ("dragonchess_set", "Scacchi dei draghi", "Dragonchess set", "gaming", _W),
    ("playing_card_set", "Mazzo di carte", "Playing card set", "gaming", _W),
    ("three_dragon_ante_set", "Tre draghi al buio", "Three-Dragon Ante set", "gaming", _W),
    ("bagpipes", "Cornamusa", "Bagpipes", "instrument", _C),
    ("drum", "Tamburo", "Drum", "instrument", _C),
    ("dulcimer", "Dulcimer", "Dulcimer", "instrument", _C),
    ("flute", "Flauto", "Flute", "instrument", _C),
    ("horn", "Corno", "Horn", "instrument", _C),
    ("lute", "Liuto", "Lute", "instrument", _C),
    ("lyre", "Lira", "Lyre", "instrument", _C),
    ("pan_flute", "Flauto di Pan", "Pan flute", "instrument", _C),
    ("shawm", "Ciaramella", "Shawm", "instrument", _C),
    ("viol", "Viola", "Viol", "instrument", _C),
    ("disguise_kit", "Trucchi per il camuffamento", "Disguise kit", "kit", _C),
    ("forgery_kit", "Arnesi da falsario", "Forgery kit", "kit", _D),
    ("herbalism_kit", "Borsa da erborista", "Herbalism kit", "kit", _I),
    ("navigators_tools", "Strumenti da navigatore", "Navigator's tools", "kit", _W),
    ("poisoners_kit", "Sostanze da avvelenatore", "Poisoner's kit", "kit", _I),
    ("thieves_tools", "Arnesi da scasso", "Thieves' tools", "thieves", _D),
    # shortcut: il 2024 non ha più la competenza nei veicoli, Destrezza è una scelta nostra; il giocatore la cambia al tiro.
    ("land_vehicles", "Veicoli terrestri", "Land vehicles", "vehicle", _D),
    ("water_vehicles", "Veicoli acquatici", "Water vehicles", "vehicle", _D),
)

TOOLS: dict[str, ToolSpec] = {k: ToolSpec(k, it, en, cat, ab) for k, it, en, cat, ab in _ROWS}

# Nomi usati finora dall'app (suggerimenti della pagina Identità, etichette di LABELS, import) per gli stessi strumenti.
_EXTRA_ALIASES: dict[str, str] = {
    "strumenti da ladro": "thieves_tools",
    "strumenti da scasso": "thieves_tools",
    "strumenti da alchimista": "alchemists_supplies",
    "strumenti da erborista": "herbalism_kit",
    "kit da erborista": "herbalism_kit",
    "kit da camuffamento": "disguise_kit",
    "kit da avvelenatore": "poisoners_kit",
    "kit da falsario": "forgery_kit",
    "thieves tools": "thieves_tools",
    "dragonchess": "dragonchess_set",
    "playing cards": "playing_card_set",
    "three-dragon ante": "three_dragon_ante_set",
    "dice": "dice_set",
    "vehicles (land)": "land_vehicles",
    "vehicles (water)": "water_vehicles",
}

_ALIASES: dict[str, str] = {
    **{name.lower(): t.key for t in TOOLS.values() for name in (t.it, t.en, t.key)},
    **_EXTRA_ALIASES,
}


def tool_key(name: str) -> str | None:
    """Chiave del catalogo per un nome scritto (italiano o inglese, maiuscole indifferenti); ``None`` se non è uno
    strumento preciso (es. «Strumenti musicali» generico)."""
    return _ALIASES.get(" ".join(str(name).split()).lower().replace("’", "'"))


def tool_label(key: str, lang: str = "it") -> str:
    t = TOOLS[key]
    return t.en if lang == "en" else t.it
