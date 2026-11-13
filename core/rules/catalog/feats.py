"""Effetti dei talenti nel motore delle regole di classe.

Un talento preso è una riga ``Ability`` con ``feature_key = "feat.<chiave>"`` (chiave di ``core.data.feats*``). Qui ogni
talento ha una ``FeatureSpec`` con la stessa chiave: ``active_features`` la restituisce insieme a un ``FeatSource``, che
fa le veci della riga di classe (livello = livello totale, ``id`` nullo come ``source_class_id`` delle righe dei talenti).
``FeatSpec`` resta la scheda di selezione (prerequisiti, +1 alla caratteristica, ripetibilità).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from core.rules.edition import character_edition
from core.rules.types import Edition, FeatureSpec

FEAT_FEATURES: dict[str, FeatureSpec] = {}
# Chiavi di ``Ability.options`` senza le quali il talento non agisce («da completare»)
FEAT_NEEDS: dict[str, tuple[str, ...]] = {}

FeatStatus = Literal["active", "incomplete", "other_edition"]


def feat(key: str, edition: Edition, it: str, en: str, sit: str, sen: str, **kw: Any) -> FeatureSpec:
    """Voce del registro: ``key`` è la chiave del talento (``2024_alert``), la spec ha chiave ``feat.<key>``."""
    kw.setdefault("passive", kw.get("on_use") is None)
    return FeatureSpec(key=f"feat.{key}", class_key="feat", edition=edition, level=1, source_title=f"{it} / {en} (talento)",
                       name={"it": it, "en": en}, summary={"it": sit, "en": sen}, action_type=kw.pop("action_type", None), **kw)


def _register(*specs: FeatureSpec, needs: dict[str, tuple[str, ...]] | None = None) -> None:
    for spec in specs:
        FEAT_FEATURES[spec.key] = spec
    FEAT_NEEDS.update(needs or {})


@dataclass(frozen=True)
class FeatSource:
    """Al posto della riga di classe per i privilegi dei talenti."""
    ability: Any
    level: int

    @property
    def id(self) -> None:
        return None

    @property
    def class_name(self) -> str:
        return "feat"

    @property
    def subclass_key(self) -> None:
        return None

    @property
    def options(self) -> dict:
        return getattr(self.ability, "options", None) or {}


def _abilities(char: Any) -> list:
    """Le righe del personaggio, se caricate: un ORM non caricato non deve scatenare un lazy load asincrono."""
    try:
        from sqlalchemy import inspect as sa_inspect
        state = sa_inspect(char, raiseerr=False)
    except ImportError:  # pragma: no cover
        state = None
    if state is not None and "abilities" in state.unloaded:
        return []
    return list(getattr(char, "abilities", None) or [])


def feat_status(char: Any, ability: Any) -> FeatStatus | None:
    spec = FEAT_FEATURES.get(getattr(ability, "feature_key", None) or "")
    if spec is None:
        return None
    if spec.edition != character_edition(char):
        return "other_edition"
    opts = getattr(ability, "options", None) or {}
    if any(not opts.get(k) for k in FEAT_NEEDS.get(spec.key, ())):
        return "incomplete"
    return "active"


def owned_feats(char: Any) -> list[tuple[FeatureSpec, FeatSource]]:
    level = max(1, sum(getattr(c, "level", 0) or 0 for c in getattr(char, "classes", None) or []))
    return [(FEAT_FEATURES[a.feature_key], FeatSource(a, level)) for a in _abilities(char)
            if feat_status(char, a) == "active"]


# ---------------------------------------------------------------------------
# Tipi del motore usati dalle voci dei talenti (i talenti 2014 stanno in ``feats_2014.py``)
# ---------------------------------------------------------------------------

from core.rules.types import Cost, Modifier, RollOptionSpec, Uses  # noqa: E402  (dopo le definizioni del registro)

D20_TESTS = ("attack", "save", "skill", "initiative", "death_save", "concentration")


# ---------------------------------------------------------------------------
# Talenti d'Origine 2024 (Manuale del Giocatore 2024, pagg. 200-202)
# ---------------------------------------------------------------------------

def _f24(key: str, **kw: Any) -> FeatureSpec:
    """Voce 2024 con nome e riassunto della scheda di selezione (``core/data/feats_2024.py``)."""
    from core.data.feats_2024 import ALL_FEATS  # import locale: i dati dei talenti non dipendono dal motore
    data = ALL_FEATS[f"2024_{key}"]
    return feat(f"2024_{key}", "2024", data.name["it"], data.name["en"], data.summary["it"], data.summary["en"], **kw)


def _unarmed(ctx: Any) -> bool:
    return ctx.item is None and ctx.attack_mode != "ranged"


_register(
    _f24("alert", modifiers=(Modifier("initiative", lambda ctx: ctx.char.proficiency_bonus),)),
    _f24("tough", modifiers=(Modifier("hp_max", lambda ctx: 2 * ctx.class_level),)),
    _f24("lucky", passive=False, uses=Uses(proficiency=True, minimum=0), restoration="long_rest",
         roll_options=(RollOptionSpec(
             key="feat.2024_lucky", phase="before", rolls=D20_TESTS, mode="advantage", cost=Cost(feature_key="feat.2024_lucky"),
             label={"it": "Fortunato: spendi un punto per avere vantaggio", "en": "Lucky: spend a point to gain advantage"}),)),
    _f24("savage_attacker", weapon_damage_twice=True),
    _f24("tavern_brawler", unarmed_die="1d4", modifiers=(Modifier("damage_reroll", 1, when=_unarmed),)),
    _f24("healer"),  # Medico da campo e i ritiri delle cure: l'app non ha un'azione «cura un altro» (D1, testo)
    _f24("crafter"),  # strumenti a testo in ``general_proficiencies`` finché non c'è il catalogo degli strumenti
    _f24("musician"),  # idem; Canto incoraggiante: Ispirazione agli alleati, testo per il GM
    _f24("skilled"),
    # Lancio gratuito una volta per riposo lungo con il percorso «arcanum» (``core/rules/pact_casts.py``): l'incantesimo
    # di 1º livello sta in ``options["spell"]``; CD e attacco con ``options["ability"]`` (``spell_stats``)
    _f24("magic_initiate", passive=False, uses=Uses(table={1: 1}), restoration="long_rest", arcanum_group="spell"),
    needs={"feat.2024_crafter": ("tools",), "feat.2024_musician": ("instruments",), "feat.2024_skilled": ("picks",),
           "feat.2024_magic_initiate": ("list", "ability", "cantrips", "spell")},
)

from core.rules.catalog import feats_2024 as _general_2024  # noqa: E402,F401  (talenti generali 2024: si registrano)
from core.rules.catalog import feats_2014 as _feats_2014  # noqa: E402,F401  (talenti 2014: si registrano)
