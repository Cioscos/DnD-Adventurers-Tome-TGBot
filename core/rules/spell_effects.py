"""Effetti degli incantesimi lanciati sui personaggi: tipi del catalogo e modificatori degli stati ``spell:<chiave>``."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from core.rules.types import Modifier, RollOptionSpec

SPELL_STATE_PREFIX = "spell:"
SPELL_CLOCK_PREFIX = "spell_cast:"


def roll(count: int, sides: int, bonus: int = 0) -> int:
    """``count`` dadi a ``sides`` facce più ``bonus`` (Vita Falsata, Rigenerazione, Resistenza dell'Orso)."""
    return sum(random.randint(1, sides) for _ in range(count)) + bonus


@dataclass(frozen=True)
class SpellTarget:
    kind: Literal["self", "ally", "allies", "aura"]
    count: Callable[[int], int] = lambda slot: 1  # numero massimo di bersagli per livello di slot


@dataclass(frozen=True)
class SpellChoice:
    key: str
    label: dict[str, str]
    options: Callable[[str], list[str]]  # per edizione
    inflicts: bool = True  # False: il tipo scelto è un tipo a cui si resiste (Protezione dall'Energia), non un danno inflitto


@dataclass(frozen=True)
class SpellVariant:
    # riceve i ``data`` dello stato: slot_level, choices, caster_id, caster_name, spell_key
    modifiers: Callable[[dict], tuple[Modifier, ...]] = lambda d: ()
    options: tuple[RollOptionSpec, ...] = ()
    rounds: int | None = None
    rounds_by_slot: Callable[[int], int] | None = None  # durata in round secondo lo slot (Sortilegio, Marchio del Cacciatore)
    until_rest: bool = False
    concentration: bool = False
    choices: tuple[SpellChoice, ...] = ()
    on_apply: Callable[[Any, dict], None] | None = None
    text: dict[str, str] | None = None
    condition: str | None = None  # condizione che lo stato impone al bersaglio e toglie quando finisce (Invisibile)
    also_conditions: tuple[str, ...] = ()  # altre condizioni imposte e tolte con ``condition`` (Morte Apparente: Accecato)
    immune_conditions: tuple[str, ...] = ()  # condizioni che il bersaglio non può avere finché dura
    ends_on: tuple[str, ...] = ("manual",)  # fini dello stato sul bersaglio (``attack`` / ``cast``: Invisibilità)
    max_targets: Callable[[int], int] | None = None  # sostituisce ``target.count`` quando il numero di bersagli cambia con l'edizione (Saltare 2014)
    track: bool = False  # lo stato (e l'orologio di concentrazione) esiste anche senza modificatori: effetti solo descrittivi
    # PF al lancio, per ogni bersaglio: i temporanei (il maggiore vince) e la cura (limitata al massimo, Aiuto alza prima il massimo).
    # Senza altro effetto l'incantesimo è istantaneo: nessuno stato né orologio (Vita Falsata 2024, Parola del Potere: Fortificare).
    per_target: Callable[[dict], dict] | None = None  # dati tirati per ogni bersaglio e uniti ai ``data`` dello stato (Banchetto degli Eroi: 2d10)
    temp_hp: Callable[[dict], int] | None = None
    temp_hp_ends: bool = False  # i PF temporanei dati e rimasti al bersaglio svaniscono quando lo stato finisce (Eroismo, Resistenza dell'Orso)
    heal: Callable[[dict], int] | None = None
    # A inizio del turno del bersaglio: ``turn_heal(data, personaggio)`` (Rigenerazione, Aura di Vita) e PF temporanei (Eroismo)
    turn_heal: Callable[[dict, Any], int] | None = None
    turn_temp_hp: Callable[[dict], int] | None = None
    clock_ends_on: tuple[str, ...] = ()  # fini dell'orologio del lanciatore oltre a concentrazione e riposo (``unconscious``: Legame di Protezione)
    ends_at_zero_temp: bool = False  # 2024: lo stato sul bersaglio finisce quando i PF temporanei sono esauriti (Armatura di Agathys)
    # Promemoria per il GM quando il bersaglio subisce danno: ``f(data, aveva_PF_temporanei) -> {"it", "en"}`` o ``None``
    retaliation: Callable[[dict, bool], dict[str, str] | None] | None = None
    needs_dc: bool = False  # la CD dei TS di chi lancia si fissa al lancio nei ``data`` dello stato (le punizioni)
    shares_damage: bool = False  # il lanciatore subisce lo stesso danno del bersaglio (Legame di Protezione)
    weapon_choice: bool = False  # il lancio sceglie un'arma non magica del bersaglio: ``choices["item_id"]`` (Arma Magica, Arma Elementale)
    weapon_kinds: tuple[str, ...] = ()  # chiavi di ``WEAPONS`` fra cui scegliere (Randello Incantato: club, quarterstaff); vuoto: qualunque arma non magica
    weapon_ability: bool = False  # l'arma scelta usa la caratteristica da incantatore (``data["ability"]``, fissata al lancio) per attacco e danno
    weapon_die: Callable[[int], str] | None = None  # il dado dell'arma scelta, secondo il livello del personaggio
    on_close: Callable[[dict], dict] | None = None  # stato che lo stato sul bersaglio lascia alla fine (Velocità: la letargia), come ``data["on_close"]``
    extra_action: bool = False  # a ogni turno del bersaglio un'azione in più, limitata (Velocità)

    def duration(self, slot: int) -> int | None:
        """Durata in round dell'incantesimo lanciato con lo slot ``slot``."""
        return self.rounds_by_slot(slot) if self.rounds_by_slot else self.rounds


@dataclass(frozen=True)
class SpellEffect:
    key: str
    srd_index: tuple[str, ...]
    names: tuple[str, ...]  # it, en, e gli altri nomi (2024)
    target: SpellTarget
    variants: dict[str, SpellVariant] = field(default_factory=dict)  # "2014" / "2024"

    def max_targets(self, edition: str, slot: int) -> int:
        variant = self.variants.get(edition)
        return (variant.max_targets if variant and variant.max_targets else self.target.count)(slot)


def own_aura_clocks(char: Any) -> list[dict]:
    """Le aure che ``char`` proietta con un suo incantesimo in corso (orologio ``spell_cast:*`` di un incantesimo con ``target.kind == "aura"``):
    ``{spell_key, name, edition, data}``. Nessuno stato sui bersagli: chi siede alla serata le riceve da qui (``projected_auras``)."""
    from core.rules.catalog.spells import SPELL_EFFECTS  # import locale: il registro importa questo modulo

    out: list[dict] = []
    for state in char.active_states or []:
        key = str(state.get("key", ""))
        data = (state.get("data") or {}).get("state_data")
        effect = SPELL_EFFECTS.get(key[len(SPELL_CLOCK_PREFIX):]) if key.startswith(SPELL_CLOCK_PREFIX) and data else None
        if effect and effect.target.kind == "aura":
            out.append({"spell_key": effect.key, "name": state.get("name") or effect.key, "edition": data.get("edition", "2014"), "data": data})
    return out


def _hp_max(variant: SpellVariant, data: dict) -> int:
    return sum(m.value for m in variant.modifiers(data) if m.target == "hp_max")


def spell_instances(char: Any) -> list[tuple[dict, "SpellEffect", SpellVariant, dict]]:
    """Gli incantesimi che agiscono su ``char``: ``(stato, effetto, variante, data)``. Sono i suoi stati ``spell:*`` e le aure vive di incantesimi,
    sue (orologio) e dei compagni della serata (``char.party_auras``, messe dal server): una sola per incantesimo (con due lanciatori sullo stesso bersaglio, l'ultimo; per i PF massimi il più forte)."""
    from core.rules.auras import party_auras  # import locale: auras usa il catalogo
    from core.rules.catalog.spells import SPELL_EFFECTS  # import locale: il registro importa questo modulo

    by_spell: dict[str, tuple[dict, SpellEffect, SpellVariant, dict]] = {}  # due lanciatori, stesso incantesimo: vale l'ultimo
    for state in char.active_states or []:
        key = str(state.get("key", ""))
        if not key.startswith(SPELL_STATE_PREFIX):
            continue
        data = state.get("data") or {}
        effect = SPELL_EFFECTS.get(data.get("spell_key") or key[len(SPELL_STATE_PREFIX):])
        variant = effect and effect.variants.get(data.get("edition", "2014"))
        if variant:
            held = by_spell.get(effect.key)
            if held and _hp_max(held[2], held[3]) > _hp_max(variant, data):
                continue  # PF massimi: fra due lanciatori vale il più potente (manuale), non il più recente
            by_spell.pop(effect.key, None)
            by_spell[effect.key] = (state, effect, variant, data)
    out = list(by_spell.values())
    seen: set[str] = set()
    for aura in [*own_aura_clocks(char), *party_auras(char, "spell")]:
        effect = SPELL_EFFECTS.get(aura["spell_key"])
        variant = effect and effect.variants.get(aura["edition"])
        if variant and aura["spell_key"] not in seen:
            seen.add(aura["spell_key"])
            out.append(({"key": SPELL_STATE_PREFIX + effect.key, "name": aura["name"]}, effect, variant, aura["data"]))
    return out


def spell_state_modifiers(char: Any) -> list[tuple[Modifier, str]]:
    """Per ogni incantesimo che agisce su ``char`` i modificatori della variante dell'edizione del lanciatore (``data["edition"]``)."""
    return [(m, f"spell:{effect.key}") for _s, effect, variant, data in spell_instances(char) for m in variant.modifiers(data)]


def spell_state_options(char: Any) -> list[tuple[RollOptionSpec, dict]]:
    """Le opzioni al tiro degli incantesimi che agiscono su ``char`` (variante dell'edizione del lanciatore), ognuna con i ``data`` del suo stato."""
    return [(o, data) for _s, _e, variant, data in spell_instances(char) for o in variant.options]


def enchanted_weapon(char: Any, item: Any) -> tuple[SpellVariant, dict] | None:
    """La variante e i ``data`` dell'incantesimo che ha cambiato caratteristica o dado di ``item`` (Randello Incantato), se ce n'è uno."""
    return next(((variant, data) for _s, _e, variant, data in spell_instances(char)
                 if (variant.weapon_ability or variant.weapon_die) and str((data.get("choices") or {}).get("item_id")) == str(item.id)), None)
