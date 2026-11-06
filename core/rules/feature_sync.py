"""Sync delle feature di classe come righe Ability.

Una classe a catalogo per l'edizione del personaggio segue il catalogo; le altre
restano su ``CLASS_RESOURCES`` finché i Task 19-42 non le sostituiscono. Le righe si
ritrovano via ``(source_class_id, feature_key)``. Usi spesi e descrizioni modificate
non si perdono: una riga tolta lascia il suo stato in ``settings["archived_features"]``.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.data.classes import CLASS_RESOURCES, class_table_key, get_class_feature_specs
from core.game.stats import effective_ability_mod, sync_base_ac
from core.db.models import Ability, Character, CharacterClass, RestorationType, Spell
from core.rules.catalog import active_features, features_for
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.edition import EDITIONS, character_edition, class_key
from core.rules.level_choices import reconcile_choices, seed_from_sheet
from core.rules.proficiencies import apply_feature_grants
from core.rules.states import begin_state, has_state, settle_closed
from core.rules.types import FeatureSpec, RuleContext
from core.rules.uses import max_uses

ARCHIVED_FEATURES = "archived_features"
ABILITY_BONUS_KEY = "feature_ability_bonus"  # settings: {feature_key: {ability: punti realmente aggiunti}}
RETROFIT_DONE = "retrofit_done"  # settings: chiavi di classe già passate dal retrofit (una volta per classe, N7)
GRANTED_SPELL_KEYS = "granted_spell_keys"  # incantesimi il cui «sempre preparato» è stato messo da un privilegio


def _mark(edition: str, cls: object) -> str:
    """Chiave del segno: edizione e classe, perché un catalogo 2024 che arriva dopo non eredita il segno del 2014 (R34)."""
    return f"{edition}:{class_key(cls)}"


def _retro_ids(char: Character, retrofit: bool) -> set[int]:
    """Classi a catalogo che il retrofit (R34, R39) riguarda: solo quelle mai passate di qui. Una classe che entra con un
    catalogo successivo ci passa per quel catalogo, le altre non tornano ``retrofit`` a ogni versione."""
    if not retrofit:
        return set()
    edition = character_edition(char)
    done = set((char.settings or {}).get(RETROFIT_DONE) or [])
    return {c.id for c in char.classes if features_for(edition, class_key(c)) and _mark(edition, c) not in done}


def _mark_retrofitted(char: Character) -> None:
    """Ogni classe a catalogo sincronizzata (anche alla creazione) non è più da retrofit."""
    edition = character_edition(char)
    done = list((char.settings or {}).get(RETROFIT_DONE) or [])
    new = [_mark(edition, c) for c in char.classes if features_for(edition, class_key(c)) and _mark(edition, c) not in done]
    if new:
        char.settings = {**(char.settings or {}), RETROFIT_DONE: [*done, *dict.fromkeys(new)]}


async def sync_class_feature_abilities(
    session: AsyncSession,
    char: Character,
    cls: CharacterClass,
    *,
    lang: str = "it",
    retrofit: bool = False,
) -> None:
    """Crea/aggiorna le Ability auto-generate dalla classe ``cls``.

    Richiede che ``char.abilities``, ``char.classes``, ``char.ability_scores`` e
    ``char.items`` siano già caricati (selectinload). ``retrofit``: personaggio che esisteva prima del catalogo o
    importato (R34): i bonus ai punteggi che ha già diritto ad avere si segnano come applicati senza toccare i punteggi.
    """
    edition = character_edition(char)
    retro = _retro_ids(char, retrofit)
    if features_for(edition, class_key(cls)):
        _sync_from_catalog(session, char, cls, lang)
    else:
        _sync_from_class_resources(session, char, cls, lang)
    # Il bonus di competenza dipende dal livello totale: può cambiare anche le altre classi.
    for other in char.classes:
        if other is not cls and features_for(edition, class_key(other)):
            _sync_from_catalog(session, char, other, lang)
    seed_from_sheet(char, retro)
    reconcile_choices(char, retro)
    apply_feature_grants(char, lang)
    _sync_ability_bonuses(char, retrofit=retrofit, retro_ids=retro)
    _mark_retrofitted(char)
    _sync_permanent_states(char)
    _end_unwielded_states(char)
    await _sync_granted_spells(session, char, lang)


async def sync_cataloged_features(
    session: AsyncSession, char: Character, lang: str = "it", *, retrofit: bool = False,
) -> None:
    """Cambio di edizione, sottoclasse, caratteristica o import: tocca solo le classi a catalogo (``retrofit``: vedi sopra)."""
    edition = character_edition(char)
    retro = _retro_ids(char, retrofit)
    for cls in char.classes:
        if features_for(edition, class_key(cls)):
            _sync_from_catalog(session, char, cls, lang)
    seed_from_sheet(char, retro)
    reconcile_choices(char, retro)
    apply_feature_grants(char, lang)
    _sync_ability_bonuses(char, retrofit=retrofit, retro_ids=retro)
    _mark_retrofitted(char)
    _sync_permanent_states(char)
    _end_unwielded_states(char)
    await _sync_granted_spells(session, char, lang)
    await session.flush()


def _end_unwielded_states(char: Character) -> None:
    """Gli stati legati a un'arma (``data["bound_item"]``, Arma Consacrata) finiscono quando quell'arma non è più impugnata:
    tolta, riposta, sostituita o eliminata. Rimetterla in mano non li riavvia."""
    wielded = {i.id for i in char.items or [] if i.is_equipped}
    states = list(char.active_states or [])
    closed = [s for s in states if (s.get("data") or {}).get("bound_item") not in (None, *wielded)]
    if closed:
        char.active_states = [s for s in states if s not in closed]
        settle_closed(char, closed)


def _sync_permanent_states(char: Character) -> None:
    """Gli stati sempre attivi dei privilegi (Purezza di Spirito): li avvia se mancano, tolgono quelli di un privilegio che non c'è più."""
    wanted = {spec.permanent_state.key: spec for spec, _row in active_features(char) if spec.permanent_state}
    states = list(char.active_states or [])
    kept = [s for s in states if not (s.get("data") or {}).get("permanent") or s.get("key") in wanted]
    if len(kept) != len(states):
        char.active_states = kept
    for key, spec in wanted.items():
        if not has_state(char, key):
            begin_state(char, spec.permanent_state, spec.key, spec.name["it"])


def _sync_ability_bonuses(char: Character, *, retrofit: bool = False, retro_ids: set[int] | None = None) -> None:
    """Punteggi dei privilegi con ``ability_bonus`` (Campione Primordiale): scritti sul punteggio una volta sola, con il
    massimo del privilegio, e tolti se il privilegio non è più attivo. I punti davvero aggiunti stanno in
    ``settings``, così un punteggio già al massimo non perde nulla quando il privilegio sparisce.

    R34: con ``retrofit`` (personaggio esistente al primo sync dopo l'arrivo del catalogo, import) il bonus si segna come
    già applicato senza punti: i punteggi sono quelli che il giocatore ha scritto. Chi sale di livello lo riceve."""
    wanted = {spec.key: spec for spec, _row in active_features(char) if spec.ability_bonus}
    owner = {spec.key: row.id for spec, row in active_features(char) if spec.ability_bonus}
    retro_ids = _retro_ids(char, retrofit) if retro_ids is None else retro_ids
    applied = clean_ability_bonus((char.settings or {}).get(ABILITY_BONUS_KEY))
    if not wanted and not applied:
        return
    scores = {a.name: a for a in char.ability_scores}
    old_con = effective_ability_mod(char, "constitution")
    changed = False
    for key in [k for k in applied if k not in wanted and applied[k]]:  # `{}`: nessun punto dato, il segno resta (R34)
        for ability, points in applied.pop(key).items():
            if ability in scores:
                scores[ability].value -= points
        changed = True
    for key, spec in wanted.items():
        if key in applied:
            continue
        applied[key] = {}
        if retrofit and owner[key] in retro_ids:
            changed = True
            continue
        for ability, bonus in spec.ability_bonus.items():
            row = scores.get(ability)
            if row is None:
                continue
            points = max(0, min(row.value + bonus, max(spec.ability_cap, row.value)) - row.value)
            row.value += points
            if points:
                applied[key][ability] = points
        changed = True
    if not changed:
        return
    char.settings = {**(char.settings or {}), ABILITY_BONUS_KEY: applied}
    char.recalculate_carry_capacity()
    sync_base_ac(char)
    delta = effective_ability_mod(char, "constitution") - old_con
    if delta and (char.settings or {}).get("hp_auto_calc", True):
        char.hit_points = max(0, char.hit_points + delta * char.total_level)
        char.current_hit_points = max(0, min(char.current_hit_points + delta * char.total_level, char.hit_points))


async def _sync_granted_spells(session: AsyncSession, char: Character, lang: str) -> None:
    """Incantesimi dei privilegi attivi: sempre preparati. Mai cancellati: se il privilegio sparisce (cambio di
    edizione, livello) l'incantesimo resta e torna a contare come gli altri. Si toglie solo il segno messo da un
    privilegio: quello dato a mano o dall'import resta dell'utente."""
    if not GRANTED_SPELLS:
        return
    granted = {key: row for spec, row in active_features(char) for key in spec.granted_spells}
    # Query e non `char.spells`: non tutti i chiamanti caricano la relazione.
    rows = (await session.execute(select(Spell).where(Spell.character_id == char.id))).scalars().all()
    have = {s.srd_index: s for s in rows if s.srd_index in GRANTED_SPELLS}
    previous = (char.settings or {}).get(GRANTED_SPELL_KEYS) or []
    for key, spell in have.items():
        if key in previous and key not in granted:
            spell.always_prepared = False
    owned: list[str] = []
    for key, owner in granted.items():
        spell = have.get(key)
        if spell is None:
            data = GRANTED_SPELLS[key]
            spell = Spell(character_id=char.id, name=data.name.get(lang) or data.name["it"], level=data.level,
                          casting_time=data.casting_time, range_area=data.range_area, duration=data.duration,
                          is_concentration=data.is_concentration, is_ritual=data.is_ritual,
                          attack_save=data.attack_save, damage_dice=data.damage_dice, damage_type=data.damage_type,
                          higher_levels_dice=data.higher_levels_dice, srd_index=key,
                          extra_damage_dice=data.extra_damage_dice, extra_damage_type=data.extra_damage_type,
                          components=data.components)
            session.add(spell)
        elif not spell.components and GRANTED_SPELLS[key].components:
            spell.components = GRANTED_SPELLS[key].components  # una riga sincronizzata prima delle componenti le riceve ora
        if key in previous or not spell.always_prepared:
            owned.append(key)
        spell.always_prepared = spell.is_prepared = True
        spell.class_id = spell.class_id or owner.id
    if set(owned) != set(previous):
        char.settings = {**(char.settings or {}), GRANTED_SPELL_KEYS: owned}


def mark_ability_bonuses(char: Character) -> None:
    """Import di un file senza ``rules_edition``: niente sync del catalogo, ma i bonus che il personaggio ha già diritto
    ad avere si segnano comunque come applicati (R34), altrimenti il primo sync li ridarebbe. Anche le scelte di livello
    passano dal retrofit (R39): il segno resta assente, così non si perde al primo sync normale."""
    edition = character_edition(char)
    retro = {c.id for c in char.classes if features_for(edition, class_key(c))}
    seed_from_sheet(char, retro)
    reconcile_choices(char, retro)
    _sync_ability_bonuses(char, retrofit=True)


def clean_ability_bonus(raw: object) -> dict[str, dict[str, int]]:
    """Da un file importato o da un PATCH tiene solo `{str: {str: int >= 0}}`; il resto è scartato."""
    if not isinstance(raw, dict):
        return {}
    return {key: {a: p for a, p in points.items() if isinstance(a, str) and type(p) is int and p >= 0}
            for key, points in raw.items() if isinstance(key, str) and isinstance(points, dict)}


def clean_zero_hp_uses(raw: object) -> dict[str, int]:
    """Da un file importato tiene solo `{str: int >= 0}`."""
    if not isinstance(raw, dict):
        return {}
    return {key: n for key, n in raw.items() if isinstance(key, str) and type(n) is int and n >= 0}


def clean_target_immunity(raw: object) -> dict[str, list[str]]:
    """Da un file importato tiene solo `{str: [str]}`."""
    if not isinstance(raw, dict):
        return {}
    return {key: [t for t in targets if isinstance(t, str)] for key, targets in raw.items()
            if isinstance(key, str) and isinstance(targets, list)}


def clean_granted_keys(raw: object) -> list[str]:
    """Da un file importato tiene solo le stringhe di una lista; il resto è scartato."""
    return [key for key in raw if isinstance(key, str)] if isinstance(raw, list) else []


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
        if owner is not cls or spec.no_row:
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
