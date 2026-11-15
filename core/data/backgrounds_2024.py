"""Background 2024 (Manuale del Giocatore 2024, pag. 177-185; oracolo docs/superpowers/rules/2024/backgrounds.md).

Ogni background: tre caratteristiche (+2/+1 o +1/+1/+1, massimo 20), un talento d'Origine, due abilità, uno strumento
(fisso, o una tupla = scelta del giocatore) e il pacchetto A nel formato di ``core.rules.starting_equipment``
(``{tool}`` = lo strumento scelto). Il pacchetto B vale sempre 50 mo. Nomi italiani di lavoro (vedi l'oracolo).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.data.tools import TOOLS

_S, _D, _C, _I, _W, _H = "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"
_ARTISAN = tuple(k for k, t in TOOLS.items() if t.category == "artisan")
_GAMING = tuple(k for k, t in TOOLS.items() if t.category == "gaming")
_INSTRUMENT = tuple(k for k, t in TOOLS.items() if t.category == "instrument")
_CLOTHES = "travelers-clothes"
GOLD_OPTION = 50


@dataclass(frozen=True)
class BackgroundData:
    key: str
    name: dict[str, str]
    abilities: tuple[str, str, str]
    origin_feat: str
    skills: tuple[str, str]
    tool: str | tuple[str, ...]  # tupla = scelta
    equipment: str  # formato di STARTING_EQUIPMENT, es. "…+gold:8"


def _bg(key, it, en, abilities, feat, skills, tool, equipment) -> BackgroundData:
    return BackgroundData(key, {"it": it, "en": en}, abilities, f"2024_{feat}", skills, tool, equipment)


BACKGROUNDS_2024: dict[str, BackgroundData] = {b.key: b for b in (
    # pag. 178
    _bg("acolyte", "Accolito", "Acolyte", (_I, _W, _H), "magic_initiate", ("insight", "religion"),
        "calligraphers_supplies", "calligraphers_supplies+book-prayers+holy-symbol+parchment*10+robe+gold:8"),
    _bg("artisan", "Artigiano", "Artisan", (_S, _D, _I), "crafter", ("investigation", "persuasion"),
        _ARTISAN, f"{{tool}}+pouch*2+{_CLOTHES}+gold:32"),
    # pag. 179
    _bg("charlatan", "Ciarlatano", "Charlatan", (_D, _C, _H), "skilled", ("deception", "sleight_of_hand"),
        "forgery_kit", "forgery_kit+costume+fine-clothes+gold:15"),
    _bg("criminal", "Criminale", "Criminal", (_D, _C, _I), "alert", ("sleight_of_hand", "stealth"),
        "thieves_tools", f"dagger*2+thieves_tools+crowbar+pouch*2+{_CLOTHES}+gold:16"),
    # pag. 180
    _bg("entertainer", "Intrattenitore", "Entertainer", (_S, _D, _H), "musician", ("acrobatics", "performance"),
        _INSTRUMENT, f"{{tool}}+costume*2+mirror+perfume+{_CLOTHES}+gold:11"),
    _bg("farmer", "Contadino", "Farmer", (_S, _C, _W), "tough", ("animal_handling", "nature"),
        "carpenters_tools", f"sickle+carpenters_tools+healers-kit+iron-pot+shovel+{_CLOTHES}+gold:30"),
    # pag. 181
    _bg("guard", "Guardia", "Guard", (_S, _I, _W), "alert", ("athletics", "perception"),
        _GAMING, f"spear+crossbow-light+bolts*20+{{tool}}+hooded-lantern+manacles+quiver+{_CLOTHES}+gold:12"),
    _bg("guide", "Guida", "Guide", (_D, _C, _W), "magic_initiate", ("stealth", "survival"),
        "cartographers_tools", f"shortbow+arrows*20+cartographers_tools+bedroll+quiver+tent+{_CLOTHES}+gold:3"),
    # pag. 182
    _bg("hermit", "Eremita", "Hermit", (_C, _W, _H), "healer", ("medicine", "religion"),
        "herbalism_kit", f"quarterstaff+herbalism_kit+bedroll+book-philosophy+lamp+oil*3+{_CLOTHES}+gold:16"),
    _bg("merchant", "Mercante", "Merchant", (_C, _I, _H), "lucky", ("animal_handling", "persuasion"),
        "navigators_tools", f"navigators_tools+pouch*2+{_CLOTHES}+gold:22"),
    # pag. 183
    _bg("noble", "Nobile", "Noble", (_S, _I, _H), "skilled", ("history", "persuasion"),
        _GAMING, "{tool}+fine-clothes+perfume+gold:29"),
    _bg("sage", "Sapiente", "Sage", (_C, _I, _W), "magic_initiate", ("arcana", "history"),
        "calligraphers_supplies", "quarterstaff+calligraphers_supplies+book-history+parchment*8+robe+gold:8"),
    # pag. 184
    _bg("sailor", "Marinaio", "Sailor", (_S, _D, _W), "tavern_brawler", ("acrobatics", "perception"),
        "navigators_tools", f"dagger+navigators_tools+rope+{_CLOTHES}+gold:20"),
    _bg("scribe", "Scriba", "Scribe", (_D, _I, _W), "skilled", ("investigation", "perception"),
        "calligraphers_supplies", "calligraphers_supplies+fine-clothes+lamp+oil*3+parchment*12+gold:23"),
    # pag. 185
    _bg("soldier", "Soldato", "Soldier", (_S, _D, _C), "savage_attacker", ("athletics", "intimidation"),
        _GAMING, f"spear+shortbow+arrows*20+{{tool}}+healers-kit+quiver+{_CLOTHES}+gold:14"),
    _bg("wayfarer", "Viandante", "Wayfarer", (_D, _W, _H), "lucky", ("insight", "stealth"),
        "thieves_tools", f"dagger*2+thieves_tools+gaming-set+bedroll+pouch*2+{_CLOTHES}+gold:16"),
)}
