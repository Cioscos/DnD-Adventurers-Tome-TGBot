"""Costanti e helper comuni alle scuole del Mago 2014 (Tradizione Arcana)."""
from __future__ import annotations

from core.rules.catalog._common import feature
from core.rules.types import RuleContext

ED, CK = "2014", "wizard"


def mod(ctx: RuleContext, ability: str) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, ability)


def dc(ctx: RuleContext) -> int:
    return 8 + ctx.char.proficiency_bonus + mod(ctx, "intelligence")


def say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


# scuola -> (titolo del Sapiente, nome it, nome en, scuola it, scuola en, livello pagina)
SAVANTS = {
    "abjuration": ("Abiuratore Sapiente / Abjuration Savant (Abiurazione 2, pag. 85)", "Abiuratore Sapiente", "Abjuration Savant",
                   "abiurazione", "abjuration"),
    "enchantment": ("Ammaliatore Sapiente / Enchantment Savant (Ammaliamento 2, pag. 85)", "Ammaliatore Sapiente", "Enchantment Savant",
                    "ammaliamento", "enchantment"),
    "divination": ("Divinatore Sapiente / Divination Savant (Divinazione 2, pag. 86)", "Divinatore Sapiente", "Divination Savant",
                   "divinazione", "divination"),
    "conjuration": ("Evocatore Sapiente / Conjuration Savant (Evocazione 2, pag. 86)", "Evocatore Sapiente", "Conjuration Savant",
                    "evocazione", "conjuration"),
    "illusion": ("Illusionista Sapiente / Illusion Savant (Illusione 2, pag. 86)", "Illusionista Sapiente", "Illusion Savant",
                 "illusione", "illusion"),
    "evocation": ("Invocatore Sapiente / Evocation Savant (Invocazione 2, pag. 87)", "Invocatore Sapiente", "Evocation Savant",
                  "invocazione", "evocation"),
    "necromancy": ("Necromante Sapiente / Necromancy Savant (Necromanzia 2, pag. 87)", "Necromante Sapiente", "Necromancy Savant",
                   "necromanzia", "necromancy"),
    "transmutation": ("Trasmutatore Sapiente / Transmutation Savant (Trasmutazione 2, pag. 88)", "Trasmutatore Sapiente",
                      "Transmutation Savant", "trasmutazione", "transmutation"),
}


def savant(school: str):
    title, it, en, school_it, school_en = SAVANTS[school]
    return feature(f"{school}_savant", CK, ED, 2, title, (it, en),
                   (f"Tempo e costo per copiare nel libro un incantesimo di {school_it} sono dimezzati.",
                    f"The time and gold to copy a {school_en} spell into the book are halved."),
                   subclass=school, passive=True, copy_school=school)
