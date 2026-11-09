"""Incantesimi che danno un dado o un bonus fisso ai tiri (Benedizione, Guida, Resistenza, Passare senza Tracce, Protezione dalle Lame)."""
from __future__ import annotations

from core.data.skills import SKILLS
from core.rules.spell_effects import SpellChoice, SpellEffect, SpellTarget, SpellVariant
from core.rules.types import Cost, Modifier, RollOptionSpec

_D4 = lambda _ctx, _inputs: "1d4"  # noqa: E731


def _d4_option(spell: str, label: dict[str, str], rolls: tuple[str, ...], *, once: bool = False, available=None) -> RollOptionSpec:
    """Il d4 si somma al tiro già fatto. ``once``: lo stato si chiude all'uso (Guida e Resistenza 2014 si spengono al primo d4)."""
    return RollOptionSpec(
        key=f"spell:{spell}:add", phase="after_roll", after="add", rolls=rolls, extra_dice=_D4, label=label,
        cost=Cost(state_key=f"spell:{spell}") if once else None, available=available or (lambda _ctx: True))


_BLESS = SpellVariant(
    options=(_d4_option("bless", {"it": "Benedizione: somma 1d4 al tiro", "en": "Bless: add 1d4 to the roll"},
                        ("attack", "save", "death_save")),),
    concentration=True, rounds=10)  # 1 minuto

_GUIDANCE_LABEL = {"it": "Guida: somma 1d4 alla prova", "en": "Guidance: add 1d4 to the check"}
_GUIDANCE_2014 = SpellVariant(
    options=(_d4_option("guidance", _GUIDANCE_LABEL, ("skill", "ability", "initiative"), once=True),),
    concentration=True, rounds=10)
_GUIDANCE_2024 = SpellVariant(
    options=(_d4_option("guidance", _GUIDANCE_LABEL, ("skill", "ability"),
                        available=lambda ctx: ctx.skill == ((ctx.spell_data or {}).get("choices") or {}).get("skill")),),
    choices=(SpellChoice("skill", {"it": "Abilità", "en": "Skill"}, lambda edition: [slug for slug, _ability in SKILLS]),),
    concentration=True, rounds=10)

# 2014: un solo TS, prima o dopo il tiro (qui dopo); il 2024 riduce il danno ed è un'altra primitiva, non ancora nel catalogo
_RESISTANCE_2014 = SpellVariant(
    options=(_d4_option("resistance", {"it": "Resistenza: somma 1d4 al tiro salvezza", "en": "Resistance: add 1d4 to the saving throw"},
                        ("save", "death_save"), once=True),),
    concentration=True, rounds=10)

_PASS_WITHOUT_TRACE = SpellVariant(
    modifiers=lambda d: (Modifier("skill", 10, when=lambda c: c.skill == "stealth"),), concentration=True, rounds=600)  # 1 ora

# Il dado negativo è sugli attaccanti, che non sono personaggi dell'app: resta un promemoria per il GM
_BLADE_WARD_2024 = SpellVariant(
    concentration=True, rounds=10,
    text={"it": "Chi ti attacca sottrae 1d4 al tiro per colpire: lo applica il GM agli attaccanti.",
          "en": "Whoever attacks you subtracts 1d4 from the attack roll: the GM applies it to the attackers."})

SPELLS: tuple[SpellEffect, ...] = (
    SpellEffect("bless", ("bless",), ("Benedizione", "Bless"), SpellTarget("allies", lambda slot: slot + 2),
                {"2014": _BLESS, "2024": _BLESS}),
    SpellEffect("guidance", ("guidance",), ("Guida", "Guidance"), SpellTarget("ally"),
                {"2014": _GUIDANCE_2014, "2024": _GUIDANCE_2024}),
    SpellEffect("resistance", ("resistance",), ("Resistenza", "Resistance"), SpellTarget("ally"), {"2014": _RESISTANCE_2014}),
    SpellEffect("pass_without_trace", ("pass-without-trace",), ("Passare Senza Tracce", "Pass without Trace"),
                SpellTarget("aura", lambda slot: 20), {"2014": _PASS_WITHOUT_TRACE, "2024": _PASS_WITHOUT_TRACE}),
    SpellEffect("blade_ward", ("blade-ward",), ("Protezione dalle Lame", "Interdizione alle Lame", "Blade Ward"),
                SpellTarget("self"), {"2024": _BLADE_WARD_2024}),
)
