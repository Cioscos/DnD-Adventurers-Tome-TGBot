"""Sync delle feature di classe come righe Ability.

Una classe a catalogo per l'edizione del personaggio segue il catalogo; le altre
restano su ``CLASS_RESOURCES`` finché i Task 19-42 non le sostituiscono. Le righe si
ritrovano via ``(source_class_id, feature_key)``. Usi spesi e descrizioni modificate
non si perdono: una riga tolta lascia il suo stato in ``settings["archived_features"]``.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.data.classes import CLASS_RESOURCES, class_table_key, get_class_feature_specs
from core.db.models import Ability, Character, CharacterClass, RestorationType
from core.rules.catalog import active_features, features_for
from core.rules.edition import EDITIONS, character_edition, class_key
from core.rules.level_choices import reconcile_choices
from core.rules.proficiencies import apply_feature_grants
from core.rules.types import FeatureSpec, RuleContext
from core.rules.uses import max_uses

ARCHIVED_FEATURES = "archived_features"


async def sync_class_feature_abilities(
    session: AsyncSession,
    char: Character,
    cls: CharacterClass,
    *,
    lang: str = "it",
) -> None:
    """Crea/aggiorna le Ability auto-generate dalla classe ``cls``.

    Richiede che ``char.abilities``, ``char.classes``, ``char.ability_scores`` e
    ``char.items`` siano già caricati (selectinload).
    """
    edition = character_edition(char)
    if features_for(edition, class_key(cls)):
        _sync_from_catalog(session, char, cls, lang)
    else:
        _sync_from_class_resources(session, char, cls, lang)
    # Il bonus di competenza dipende dal livello totale: può cambiare anche le altre classi.
    for other in char.classes:
        if other is not cls and features_for(edition, class_key(other)):
            _sync_from_catalog(session, char, other, lang)
    reconcile_choices(char)
    apply_feature_grants(char, lang)


async def sync_cataloged_features(session: AsyncSession, char: Character, lang: str = "it") -> None:
    """Cambio di edizione, sottoclasse, caratteristica o import: tocca solo le classi a catalogo."""
    edition = character_edition(char)
    for cls in char.classes:
        if features_for(edition, class_key(cls)):
            _sync_from_catalog(session, char, cls, lang)
    reconcile_choices(char)
    apply_feature_grants(char, lang)
    await session.flush()


def clean_archive(raw: object) -> dict[str, dict]:
    """Da un file importato tiene solo `{str: {"spent": int >= 0, "description": str}}`; il resto è scartato."""
    if not isinstance(raw, dict):
        return {}
    clean: dict[str, dict] = {}
    for key, state in raw.items():
        if not isinstance(state, dict):
            continue
        entry: dict = {}
        if type(state.get("spent")) is int and state["spent"] >= 0:
            entry["spent"] = state["spent"]
        if isinstance(state.get("description"), str):
            entry["description"] = state["description"]
        if entry:
            clean[key] = entry
    return clean


def _restoration(spec: FeatureSpec, level: int) -> RestorationType:
    value = spec.restoration
    if isinstance(value, dict):
        value = value[max((lv for lv in value if lv <= level), default=min(value))]
    return RestorationType(value)


def _spec_anywhere(edition: str, key_of_class: str, feature_key: str) -> FeatureSpec | None:
    """La spec dall'edizione corrente o, se manca lì, dall'altra."""
    for ed in (edition, *EDITIONS):
        for spec in features_for(ed, key_of_class):
            if spec.key == feature_key:
                return spec
    return None


def _generated_descriptions(key_of_class: str, feature_key: str) -> set[str]:
    """I testi scritti dall'app per questa feature: tutto il resto è una modifica dell'utente."""
    texts: set[str] = set()
    for ed in EDITIONS:
        for spec in features_for(ed, key_of_class):
            if spec.key == feature_key:
                texts.update(spec.summary.values())
    for cfg in CLASS_RESOURCES.get(class_table_key(key_of_class), []):
        if cfg.key == feature_key:
            texts.update(cfg.description.values())
    return texts


def _sync_from_catalog(session: AsyncSession, char: Character, cls: CharacterClass, lang: str) -> None:
    edition = character_edition(char)
    key_of_class = class_key(cls)
    ctx = RuleContext(char=char, edition=edition, class_row=cls, class_level=cls.level)
    # Il prefisso esclude le righe `feat.*` e le chiavi estranee arrivate da un file importato.
    rows = {
        a.feature_key: a for a in char.abilities
        if a.is_class_feature and a.source_class_id == cls.id
        and (a.feature_key or "").startswith(f"{key_of_class}.")
    }
    old_archive = (char.settings or {}).get(ARCHIVED_FEATURES) or {}
    archive = dict(old_archive)
    due: set[str] = set()

    for spec, owner in active_features(char):
        if owner is not cls:
            continue
        new_max = max_uses(spec, ctx)
        if new_max == 0:
            continue
        due.add(spec.key)
        ability = rows.get(spec.key)
        saved = archive.pop(spec.key, {}) if ability is None or ability.max_uses is None else {}
        if ability is None:
            ability = Ability(character_id=char.id, source_class_id=cls.id, is_class_feature=True,
                              feature_key=spec.key, is_active=True)
            session.add(ability)
            char.abilities.append(ability)
            spent = saved.get("spent", 0)
        elif ability.max_uses is None:
            spent = saved.get("spent", 0)
        else:
            spent = _spent(ability)

        ability.name = spec.name.get(lang) or spec.name["it"]
        ability.action_type = spec.action_type
        ability.is_passive = spec.passive
        # Senza contatore la ricarica non esiste: `none` distingue questa riga da una risorsa illimitata.
        ability.restoration_type = RestorationType.NONE if spec.uses is None else _restoration(spec, cls.level)
        ability.short_rest_recovers = spec.short_rest_recovers
        if "description" in saved:
            ability.description = saved["description"]
        elif ability.description is None or ability.description in _generated_descriptions(key_of_class, spec.key):
            ability.description = spec.summary.get(lang) or spec.summary["it"]

        ability.max_uses = new_max
        if new_max is None:
            ability.uses = None
            if spent:  # senza contatore il dato sparirebbe: serve se la riga torna limitata
                archive[spec.key] = {"spent": spent}
        else:
            ability.uses = new_max - min(spent, new_max)

    for key, ability in rows.items():
        if key in due:
            continue
        spec = _spec_anywhere(edition, key_of_class, key)
        if spec is not None and spec.subclass is not None and cls.subclass_key is None:
            continue  # sottoclasse non riconosciuta: non possiamo sapere che il privilegio non spetti
        state = {}
        if _spent(ability):
            state["spent"] = _spent(ability)
        if ability.description not in _generated_descriptions(key_of_class, key) and ability.description is not None:
            state["description"] = ability.description
        if state:
            archive[key] = state
        char.abilities.remove(ability)  # delete-orphan: la riga sparisce al flush

    if archive != old_archive:
        char.settings = {**(char.settings or {}), ARCHIVED_FEATURES: archive}


def _spent(ability: Ability) -> int:
    if ability.max_uses is None or ability.uses is None:
        return 0
    return max(0, ability.max_uses - ability.uses)


def _sync_from_class_resources(session: AsyncSession, char: Character, cls: CharacterClass, lang: str) -> None:
    """Non tocca mai la ``description`` (è editabile dall'utente) né le feature ``cha_based`` al level-up."""
    specs = get_class_feature_specs(cls.class_name, cls.level, char, lang)
    existing = {
        a.feature_key: a
        for a in char.abilities
        if a.is_class_feature and a.source_class_id == cls.id
    }

    for spec in specs:
        ability = existing.get(spec["key"])
        if ability is None:
            ability = Ability(
                character_id=char.id,
                source_class_id=cls.id,
                is_class_feature=True,
                feature_key=spec["key"],
                name=spec["name"],
                description=spec["description"],
                max_uses=spec["max_uses"],
                uses=spec["max_uses"],
                is_active=True,
                is_passive=False,
                restoration_type=spec["restoration_type"],
                action_type=spec["action_type"],
            )
            session.add(ability)
            char.abilities.append(ability)
            continue

        # Aggiorna il nome (il catalogo è la fonte di verità per le feature).
        ability.name = spec["name"]
        ability.action_type = spec["action_type"]

        # Le feature CHA-based non si ricalcolano al level-up (parità col vecchio
        # update_resources_for_level): il loro max dipende dal mod CAR, non dal livello.
        if spec["cha_based"]:
            continue

        new_max = spec["max_uses"]
        old_max = ability.max_uses if ability.max_uses is not None else new_max
        ability.max_uses = new_max
        current = ability.uses if ability.uses is not None else new_max
        delta = new_max - old_max
        if delta > 0:
            # Il level-up concede capacità: gli usi spesi restano spesi, ma i
            # punti appena guadagnati sono subito disponibili.
            ability.uses = min(new_max, current + delta)
        elif current > new_max:
            ability.uses = new_max
