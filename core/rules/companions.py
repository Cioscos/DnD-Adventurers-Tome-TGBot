"""Compagni concessi da un privilegio: PF, CA e bonus dal livello di classe, dal bonus di competenza e dalla Saggezza."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.game.stats import effective_ability_mod
from core.rules.edition import character_edition, class_key


@dataclass(frozen=True)
class CompanionStats:
    """``max_hp``/``armor_class`` ``None``: restano i valori scritti. I bonus si sommano a quelli dello statblock."""
    max_hp: int | None = None
    armor_class: int | None = None
    attack_bonus: int = 0
    damage_bonus: int = 0


def _rangers_companion(base_hp: int, base_ac: int, level: int, pb: int, _wis: int, _statblock: dict) -> CompanionStats:
    # 2014: PF il maggiore fra la scheda e 4 x livello; CA, attacco e danni sommano il bonus di competenza.
    return CompanionStats(max(base_hp, 4 * level), base_ac + pb, pb, pb)


def _primal_companion(_hp: int, _ac: int, level: int, pb: int, wis: int, statblock: dict) -> CompanionStats:
    # 2024: PF 5 + 5 x livello (Cielo 4 + 4 x livello), CA 13 + SAG, attacco = attacco con incantesimi, danno + SAG.
    per_level = 4 if statblock.get("primal_type") == "sky" else 5
    return CompanionStats(per_level * (level + 1), 13 + wis, pb + wis, wis)


BEAST_COMPANION = "ranger.rangers_companion"  # il compagno del Signore delle Bestie 2014: agisce solo se il ranger glielo ordina
BEAST_ORDERS = ("attack", "help", "disengage", "dash", "dodge")
MAX_MULTIATTACK, MAX_HIT_DICE = 6, 40  # tetti dei numeri dello statblock che il server legge (validati al salvataggio)


def stat_int(statblock: dict, key: str, default: int = 0, *, high: int = 10_000) -> int:
    """Numero dello statblock letto in modo difensivo: un dato salvato prima della validazione (testo, bool, negativo,
    enorme) vale ``default`` invece di far cadere la richiesta con un 500."""
    value = (statblock or {}).get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= high else default


BEAST_BONUS_ORDERS = ("help", "disengage", "dash", "dodge")  # Addestramento Straordinario: tutti tranne l'attacco


# chiave -> (classe, edizione, formula)
COMPANION_FEATURES: dict[str, tuple[str, str, Callable[..., CompanionStats]]] = {
    "ranger.rangers_companion": ("ranger", "2014", _rangers_companion),
    "ranger.primal_companion": ("ranger", "2024", _primal_companion),
}


def companion_stats(char, comp) -> CompanionStats | None:
    """Valori del compagno di privilegio per il personaggio; ``None`` se non ne ha uno o il privilegio non è dell'edizione."""
    entry = COMPANION_FEATURES.get(comp.feature_key or "")
    if entry is None or entry[1] != character_edition(char):
        return None
    level = sum(c.level for c in char.classes if class_key(c) == entry[0])
    if not level:
        return None
    wis = effective_ability_mod(char, "wisdom")
    return entry[2](comp.max_hp, comp.armor_class, level, char.proficiency_bonus, wis, comp.statblock or {})
