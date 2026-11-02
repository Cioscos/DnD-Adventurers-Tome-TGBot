"""Import da D&D Beyond: JSON del character-service -> CharacterExport + report.

Il JSON DDB contiene dati grezzi (non i valori calcolati dalla scheda): qui si ricavano
solo gli input che la nostra app usa (caratteristiche finali, PF max, oggetti, ...);
TS, abilità e slot li ricalcola l'app; la CA base include la DES come su DDB. Ogni sezione è isolata: un dato inatteso
finisce nel report, non fa fallire l'import.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field

from api.schemas.transfer import (
    CharacterExport, ExportAbility, ExportAbilityScore, ExportCharacter, ExportClass,
    ExportCompanion, ExportCurrency, ExportItem, ExportSpell, ExportSpellSlot,
)
from core.data.damage_types import canonical_damage_type
from core.data.labels import CONDITION_LABELS_IT
from core.game.item_bonuses import item_bonus_total
from core.data.skills import SKILL_ABILITY_MAP
from core.data.classes import class_table_key
from core.data.spell_slots import normalize_class_name
from core.db.models import EquipmentSlot
from core.data.equipment_slots import EQUIPMENT_SLOT_COMPAT
from core.game.stats import ability_modifier

log = logging.getLogger(__name__)

ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")  # DDB stat id 1..6
# alignmentId DDB 1..9
ALIGNMENTS = {1: "Lawful Good", 2: "Neutral Good", 3: "Chaotic Good", 4: "Lawful Neutral", 5: "Neutral",
              6: "Chaotic Neutral", 7: "Lawful Evil", 8: "Neutral Evil", 9: "Chaotic Evil"}
# limitedUse.resetType DDB: 1 short rest, 2 long rest, 3 dawn, altro = gestione manuale
RESET = {1: "short_rest", 2: "long_rest", 3: "long_rest"}
ITEM_RECHARGE = {1: "short_rest", 2: "long_rest", 3: "dawn"}
ARMOR_TYPE = {1: "light", 2: "medium", 3: "heavy"}  # armorTypeId 4 = scudo
# characterValues typeId: 2 bonus magico CA, 3 bonus vario CA, 8 nome personalizzato oggetto
CV_AC_BONUS, CV_ITEM_NAME = (2, 3), 8
CV_SKILL_PROF, CV_SAVE_PROF = 26, 41  # "Skill/Saving Throw Proficiency Level"
# abilitySkills della rule-data DDB
DDB_SKILLS = {2: "athletics", 3: "acrobatics", 4: "sleight_of_hand", 5: "stealth", 6: "arcana", 7: "history",
              8: "investigation", 9: "nature", 10: "religion", 11: "animal_handling", 12: "insight", 13: "medicine",
              14: "perception", 15: "survival", 16: "deception", 17: "intimidation", 18: "performance",
              19: "persuasion"}
CV_AC_OVERRIDE, CV_AC_BASE_OVERRIDE = 1, 4  # "Override AC" (totale), "Override Base Armor + DEX"
# activationType DDB
ACTIVATION = {1: "action", 3: "bonus action", 4: "reaction", 6: "minute", 7: "hour"}
SKIP_FEATURES = {"hit points", "proficiencies", "equipment", "ability score improvement",
                 "ability score increase", "ability score increases", "languages", "age", "size", "speed",
                 "alignment", "creature type", "epic boon"}
# voci-contenitore delle classi 2024 (es. "Core Sorcerer Traits", "Sorcerer Subclass", "Metamagic Options")
_LEVEL_PREFIX_RE = re.compile(r"^\d+: ")  # "8: Ability Score Improvement"
_STRUCTURAL_RE = re.compile(r"^(core .+ traits|\w+ subclass|.+ options|.*ability score improvements?)$")
_UNCHOSEN_RE = re.compile(r"^(choose|select) ", re.I)
NOTE_TITLES = {"backstory": "Backstory", "allies": "Allies", "organizations": "Organizations",
               "enemies": "Enemies", "personalPossessions": "Personal Possessions",
               "otherHoldings": "Other Holdings", "otherNotes": "Other Notes"}
_TAG_RE = re.compile(r"<[^>]+>")
_DICE_RE = re.compile(r"^\d+d\d+$")


class ReportEntry(BaseModel):
    section: str
    name: str = ""
    reason: str  # chiave i18n lato FE


class ImportReport(BaseModel):
    imported: list[ReportEntry] = Field(default_factory=list)
    approximated: list[ReportEntry] = Field(default_factory=list)
    skipped: list[ReportEntry] = Field(default_factory=list)


class DdbImportError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# --- helpers difensivi ------------------------------------------------------

def _d(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _l(v: Any) -> list:
    return v if isinstance(v, list) else []


def _int(v: Any, default: int = 0) -> int:
    if isinstance(v, bool):
        return int(v)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _str(v: Any, n: int = 200) -> str:
    return v.strip()[:n] if isinstance(v, str) else ""


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _text(v: Any) -> str | None:
    """HTML DDB -> testo semplice."""
    if not isinstance(v, str) or not v.strip():
        return None
    t = html.unescape(_TAG_RE.sub("", v.replace("</p>", "\n").replace("<br>", "\n")))
    return re.sub(r"\n{3,}", "\n\n", t).strip() or None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _inactive_item_ids(data: dict) -> set[int]:
    """definition.id degli oggetti che non danno effetti: DDB elenca comunque i loro modificatori
    in modifiers.item (anche se non equipaggiati o non sintonizzati), la scheda li scarta."""
    out = set()
    for it in _l(data.get("inventory")):
        it = _d(it)
        d = _d(it.get("definition"))
        if not it.get("equipped") or (d.get("canAttune") and not it.get("isAttuned")):
            out.add(_int(d.get("id")))
    active = {_int(_d(_d(it).get("definition")).get("id")) for it in _l(data.get("inventory"))} - out
    return out - active  # stesso oggetto due volte, una copia attiva: vale quella


def _multiclass_feature_ids(data: dict) -> set[int]:
    """Privilegi delle classi aggiunte (non iniziali): i loro modificatori con
    availableToMulticlass=false (TS, alcune competenze) non valgono, come sulla scheda DDB."""
    classes = [_d(c) for c in _l(data.get("classes"))]
    if not any(c.get("isStartingClass") for c in classes):
        return set()
    return {_int(_d(_d(f).get("definition")).get("id")) for c in classes if not c.get("isStartingClass")
            for f in _l(c.get("classFeatures"))}


def _modifiers(data: dict, sources: tuple[str, ...] | None = None) -> list[dict]:
    mods = _d(data.get("modifiers"))
    inactive = _inactive_item_ids(data) if sources is None or "item" in sources else set()
    multi = _multiclass_feature_ids(data) if sources is None or "class" in sources else set()
    return [(m | {"_src": src}) for src, ms in mods.items()
            if sources is None or src in sources for m in _l(ms) if isinstance(m, dict)
            and not (src == "item" and _int(m.get("componentId")) in inactive)
            and not (src == "class" and m.get("availableToMulticlass") is False
                     and _int(m.get("componentId")) in multi)]


class _Ctx:
    def __init__(self, data: dict, lang: str = "it"):
        self.data = data
        self.lang = lang
        self.report = ImportReport()
        self.scores: dict[str, int] = {a: 10 for a in ABILITIES}
        self.total_level = 1
        self.out: dict[str, Any] = {}

    def ok(self, section: str, name: str = "") -> None:
        self.report.imported.append(ReportEntry(section=section, name=name, reason="ddb.reason.ok"))

    def approx(self, section: str, name: str, reason: str) -> None:
        self.report.approximated.append(ReportEntry(section=section, name=name, reason=reason))

    def skip(self, section: str, name: str, reason: str) -> None:
        self.report.skipped.append(ReportEntry(section=section, name=name, reason=reason))

    def model(self, cls: type[BaseModel], obj: dict, section: str, name: str):
        try:
            m = cls.model_validate(obj)
        except Exception:
            self.skip(section, name, "ddb.reason.invalid")
            return None
        self.ok(section, name)
        return m

    @property
    def prof(self) -> int:
        return 2 + (self.total_level - 1) // 4

    def mod(self, ability: str) -> int:
        return ability_modifier(self.scores[ability])


# --- sezioni ----------------------------------------------------------------

def _classes(c: _Ctx) -> None:
    classes = sorted((x for x in _l(c.data.get("classes")) if isinstance(x, dict)),
                     key=lambda x: not x.get("isStartingClass"))
    out = []
    for cl in classes:
        d = _d(cl.get("definition"))
        raw = _str(d.get("name"), 100)
        if not raw:
            continue
        key = normalize_class_name(raw)
        if key is None:
            c.approx("classes", raw, "ddb.reason.unknown_class")
        cast = _int(d.get("spellCastingAbilityId"))
        # come il wizard: nome localizzato (tabelle classi in italiano, DDB in inglese)
        shown = (class_table_key(raw) if c.lang == "it" else None) or raw
        obj = {"class_name": shown, "level": _clamp(_int(cl.get("level"), 1), 1, 20),
               "subclass": _str(_d(cl.get("subclassDefinition")).get("name"), 100) or None,
               "spellcasting_ability": ABILITIES[cast - 1] if 1 <= cast <= 6 else None,
               "hit_die": _clamp(_int(d.get("hitDice"), 8), 1, 100) if d.get("hitDice") else None,
               "hit_dice_used": max(0, _int(cl.get("hitDiceUsed")))}
        m = c.model(ExportClass, obj, "classes", raw)
        if m and all(x.class_name != m.class_name for x in out):
            out.append(m)
    c.out["classes"] = out
    c.out["_raw_classes"] = classes
    c.total_level = max(1, sum(x.level for x in out))


def _scores(c: _Ctx) -> None:
    def by_id(key: str) -> dict[int, Any]:
        return {_int(s.get("id")): s.get("value") for s in _l(c.data.get(key)) if isinstance(s, dict)}
    base, bonus, override = by_id("stats"), by_id("bonusStats"), by_id("overrideStats")
    adds = {a: 0 for a in ABILITIES}
    # gli oggetti (es. cinture) sono esclusi: i loro effetti li gestisce l'app sull'oggetto
    for m in _modifiers(c.data, ("race", "class", "background", "feat")):
        sub = m.get("subType")
        if m.get("type") == "bonus" and isinstance(sub, str) and sub.endswith("-score"):
            ab = sub[:-6]
            if ab in adds:
                adds[ab] += _int(m.get("value"))
    for i, ab in enumerate(ABILITIES, start=1):
        if override.get(i) is not None:
            v = _int(override[i], 10)
        else:
            v = _int(base.get(i), 10) + _int(bonus.get(i)) + adds[ab]
        c.scores[ab] = _clamp(v, 1, 30)
    c.out["ability_scores"] = [ExportAbilityScore(name=a, value=v) for a, v in c.scores.items()]
    c.ok("ability_scores")


def _hp(c: _Ctx) -> dict:
    d = c.data
    if d.get("overrideHitPoints") is not None:
        mx = _int(d.get("overrideHitPoints"))
    else:
        per_level = 0
        for m in _modifiers(d):
            if m.get("type") == "bonus" and m.get("subType") == "hit-points-per-level":
                per_level += _int(m.get("value"))
                if m["_src"] not in ("race", "feat"):
                    c.approx("hp", "", "ddb.reason.hp_recomputed")
        mx = (_int(d.get("baseHitPoints")) + _int(d.get("bonusHitPoints"))
              + (c.mod("constitution") + per_level) * c.total_level)
    mx = _clamp(mx, 1, 1_000_000)
    c.ok("hp")
    return {"hit_points": mx, "current_hit_points": _clamp(mx - _int(d.get("removedHitPoints")), 0, mx),
            "temp_hp": max(0, _int(d.get("temporaryHitPoints")))}


MOVEMENT = {1: "walk", 2: "burrow", 3: "climb", 4: "fly", 5: "swim"}  # customSpeeds.movementId
OTHER_SPEEDS = {f"innate-speed-{k}": v for k, v in
                (("burrowing", "burrow"), ("climbing", "climb"), ("flying", "fly"), ("swimming", "swim"))}


SENSES = {1: "blindsight", 2: "darkvision", 3: "tremorsense", 4: "truesight"}  # rule-data senses


def _senses(c: _Ctx) -> list[dict]:
    """Sensi della specie/privilegi ("set-base darkvision 60") + override "Senses" della scheda."""
    found: dict[str, int] = {}
    for m in _modifiers(c.data):
        sub = m.get("subType")
        if m.get("type") == "set-base" and sub in SENSES.values():
            found[sub] = max(found.get(sub, 0), _int(m.get("value")))
    for cs in _l(c.data.get("customSenses")):
        kind, dist = SENSES.get(_int(_d(cs).get("senseId"))), _int(_d(cs).get("distance"))
        if kind and dist > 0:
            found[kind] = dist
    return [{"type": k, "range_ft": _clamp(v, 0, 1000)} for k, v in found.items() if v > 0]


def _speed(c: _Ctx, walk: int) -> tuple[int, list[dict]]:
    """(a piedi, altre) come la scheda DDB: base razza/lignaggio + bonus (l'app non li calcola)."""
    armored = any(isinstance(it, dict) and it.get("equipped")
                  and 1 <= _int(_d(it.get("definition")).get("armorTypeId")) <= 4  # 4 = scudo
                  for it in _l(c.data.get("inventory")))
    bonus, other = 0, {}
    for m in _modifiers(c.data, ("race", "class", "background", "feat")):
        sub, val = m.get("subType"), _int(m.get("value"))
        if m.get("type") == "set" and sub == "innate-speed-walking":
            walk = max(walk, val)
        elif m.get("type") == "set" and sub in OTHER_SPEEDS:
            kind = OTHER_SPEEDS[sub]
            # value null = "pari alla velocità a piedi" (es. Stormborn del Chierico della Tempesta)
            other[kind] = None if m.get("value") is None else max(other.get(kind) or 0, val)
        elif m.get("type") == "bonus" and (sub in ("speed", "speed-walking")
                                           or (sub == "unarmored-movement" and not armored)):
            bonus += val
    walk += _clamp(bonus, 0, 200)
    other = {k: walk if v is None else v for k, v in other.items()}
    for cs in _l(c.data.get("customSpeeds")):  # "Override speeds" della scheda: vince sul calcolato
        kind, dist = MOVEMENT.get(_int(_d(cs).get("movementId"))), _int(_d(cs).get("distance"))
        if kind == "walk" and dist > 0:
            walk = dist
        elif kind and dist > 0:
            other[kind] = dist
    return walk, [{"type": k, "range_ft": _clamp(v, 0, 1000)} for k, v in other.items() if v > 0]


def _identity(c: _Ctx) -> dict:
    d = c.data
    bg = _d(d.get("background"))
    race = _d(d.get("race"))
    traits = _d(d.get("traits"))
    speed, other_speeds = _speed(c, _int(_d(_d(race.get("weightSpeeds")).get("normal")).get("walk"), 30))
    settings = {k: v for k, v in (("speeds", other_speeds), ("senses", _senses(c))) if v}
    ds =_d(d.get("deathSaves"))
    out = {
        "race": _str(race.get("fullName"), 100) or None,
        "gender": _str(d.get("gender"), 50) or None,
        "experience_points": _clamp(_int(d.get("currentXp")), 0, 1_000_000),
        "heroic_inspiration": bool(d.get("inspiration")),
        "background": (_str(_d(bg.get("definition")).get("name"), 100)
                       or _str(_d(bg.get("customBackground")).get("name"), 100) or None),
        "alignment": ALIGNMENTS.get(_int(d.get("alignmentId"))),
        "speed": _clamp(speed, 0, 1000) or 30,
        **({"settings": settings} if settings else {}),
        "personality": {k: _str(traits.get(src), 5000) for k, src in
                        (("traits", "personalityTraits"), ("ideals", "ideals"), ("bonds", "bonds"),
                         ("flaws", "flaws")) if _str(traits.get(src), 5000)},
        "death_saves": {"successes": _clamp(_int(ds.get("successCount")), 0, 3),
                        "failures": _clamp(_int(ds.get("failCount")), 0, 3),
                        "stable": bool(ds.get("isStabilized"))},
    }
    c.ok("identity")
    return out


def _notes(c: _Ctx) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    notes = {}
    src = _d(c.data.get("notes")) | {"appearance": _d(c.data.get("traits")).get("appearance")}
    for key, val in src.items():
        body = _str(val, 20_000)
        if body:
            title = NOTE_TITLES.get(key, key[:1].upper() + key[1:])
            notes[title] = {"body": body, "created_at": now, "updated_at": now,
                            "tags": ["dndbeyond"], "was_voice": False}
    c.ok("notes")
    return notes


def _proficiencies(c: _Ctx) -> dict:
    skills: dict[str, Any] = {}
    saves: dict[str, bool] = {}
    general = {"armor": [], "weapons": [], "tools": [], "other": []}
    langs: list[str] = []
    dmg = {"resistances": [], "immunities": [], "vulnerabilities": []}
    for m in _modifiers(c.data):
        t, sub = m.get("type"), m.get("subType")
        if not isinstance(sub, str):
            continue
        label = _str(m.get("friendlySubtypeName"), 100) or sub
        if _UNCHOSEN_RE.match(label):  # scelta lasciata aperta su DDB ("Choose a Gaming Set")
            continue
        if t in ("proficiency", "expertise"):
            slug = sub.replace("-", "_")
            if slug in SKILL_ABILITY_MAP:
                if t == "expertise" or skills.get(slug) != "expert":
                    skills[slug] = "expert" if t == "expertise" else True
            elif sub.endswith("-saving-throws") and sub[:-14] in ABILITIES:
                saves[sub[:-14]] = True
            elif t == "proficiency":
                cat = ("armor" if sub.endswith("-armor") or sub == "shields"
                       else "weapons" if sub.endswith("-weapons")
                       else "tools" if any(k in sub for k in ("tools", "kit", "supplies", "instrument"))
                       else "other")
                if label not in general[cat]:
                    general[cat].append(label)
        elif t == "language" and label not in langs:
            langs.append(label)
        elif t in ("resistance", "immunity", "vulnerability"):
            slug = canonical_damage_type(sub)
            key = {"resistance": "resistances", "immunity": "immunities", "vulnerability": "vulnerabilities"}[t]
            if slug is None:
                c.skip("defenses", label, "ddb.reason.condition_immunity" if sub in CONDITION_LABELS_IT
                       else "ddb.reason.unknown_damage_type")
            elif slug not in dmg[key]:
                dmg[key].append(slug)
    # livelli di competenza impostati a mano sulla scheda: 1 nessuna, 2 mezza, 3 competente, 4 maestria
    for v in _l(c.data.get("characterValues")):
        v = _d(v)
        kind, level, ref = _int(v.get("typeId")), _int(v.get("value")), _int(v.get("valueId"))
        if kind == CV_SKILL_PROF and ref in DDB_SKILLS:
            slug, target = DDB_SKILLS[ref], skills
        elif kind == CV_SAVE_PROF and 1 <= ref <= 6:
            slug, target = ABILITIES[ref - 1], saves
        else:
            continue
        if level >= 3:
            target[slug] = "expert" if level == 4 and target is skills else True
        else:
            target.pop(slug, None)
            if level == 2:  # l'app non ha la mezza competenza
                c.approx("proficiencies", slug, "ddb.reason.half_proficiency")
    c.ok("proficiencies")
    return {"skills": skills, "saving_throws": saves, "general_proficiencies": general,
            "languages": langs[:20], "damage_modifiers": {k: v for k, v in dmg.items() if v}}


def _item_type(d: dict) -> str:
    ft, name = d.get("filterType"), _str(d.get("name")).lower()
    if ft == "Weapon":
        return "weapon"
    if ft == "Armor":
        return "shield" if _int(d.get("armorTypeId")) == 4 else "armor"
    if ft in ("Ring", "Wondrous item"):
        if any(k in name for k in ("helm", "hat", "circlet", "glove", "gauntlet", "bracer", "boot", "slipper")):
            return "gear"
        return "accessory"
    if d.get("subType") == "Potion" or ft == "Potion":
        return "consumable"
    if d.get("subType") == "Ammunition":
        return "ammunition"
    return "generic"


_SLOT_HINTS = [(("cloak", "cape", "mantle"), EquipmentSlot.CLOAK),
               (("ring",), EquipmentSlot.RING1), (("ring",), EquipmentSlot.RING2),
               (("amulet", "necklace", "periapt", "medallion", "brooch", "pendant", "scarab"), EquipmentSlot.NECK),
               (("helm", "hat", "circlet"), EquipmentSlot.HEAD),
               (("glove", "gauntlet", "bracer"), EquipmentSlot.HANDS),
               (("boot", "slipper"), EquipmentSlot.FEET)]


def _pick_slot(item_type: str, name: str, taken: set) -> EquipmentSlot | None:
    allowed = EQUIPMENT_SLOT_COMPAT.get(item_type, set())
    hinted = [s for keys, s in _SLOT_HINTS if any(k in name.lower() for k in keys)]
    ordered = hinted + sorted(allowed, key=lambda s: s.value)
    return next((s for s in ordered if s in allowed and s not in taken), None)


def _item_meta(c: _Ctx, d: dict, it: dict, item_type: str, name: str, attuned_count: list[int]) -> dict:
    meta: dict[str, Any] = {}
    if item_type == "weapon":
        dice = _str(_d(d.get("damage")).get("diceString"), 20)
        if _DICE_RE.match(dice):
            meta["damage_dice"] = dice
        dt = canonical_damage_type(d.get("damageType"))
        if dt:
            meta["damage_type"] = dt
        props = [p for p in _l(d.get("properties")) if isinstance(p, dict)]
        meta["properties"] = [_str(p.get("name"), 50) for p in props if _str(p.get("name"), 50)]
        vers = next((_str(p.get("notes"), 20) for p in props if p.get("name") == "Versatile"), "")
        if _DICE_RE.match(vers):
            meta["versatile_dice"] = vers
        meta["weapon_type"] = "ranged" if _int(d.get("attackType")) == 2 else "melee"
        cat = {1: "simple", 2: "martial"}.get(_int(d.get("categoryId")))
        if cat:
            meta["weapon_category"] = cat
    elif item_type == "armor":
        meta["ac_value"] = _clamp(_int(d.get("armorClass"), 10), 0, 30)
        if ARMOR_TYPE.get(_int(d.get("armorTypeId"))):
            meta["armor_type"] = ARMOR_TYPE[_int(d.get("armorTypeId"))]
    elif item_type == "shield":
        meta["ac_bonus"] = _clamp(_int(d.get("armorClass"), 2), 0, 10)

    rarity = _slug(_str(d.get("rarity"))).replace("-", "_")
    if rarity in ("common", "uncommon", "rare", "very_rare", "legendary", "artifact") and d.get("magic"):
        meta["rarity"] = rarity
    meta["is_magic"] = bool(d.get("magic"))
    if d.get("canAttune"):
        meta["requires_attunement"] = True
        if it.get("isAttuned"):
            if attuned_count[0] < 3:
                meta["attuned"] = True
                attuned_count[0] += 1
            else:
                c.approx("items", name, "ddb.reason.attunement_limit")
    bonuses = []
    targets = {"armor-class": "ac", "saving-throws": "saves", "spell-attacks": "spell_attack",
               "spell-save-dc": "spell_dc", "speed": "speed", "initiative": "initiative"}
    for m in _l(d.get("grantedModifiers")):
        m = _d(m)
        if m.get("type") != "bonus":
            continue
        if m.get("subType") == "magic" and item_type == "weapon":
            meta["magic_bonus"] = _clamp(_int(m.get("value")), 0, 10)
        elif m.get("subType") in targets and m.get("value") is not None:
            bonuses.append({"target": targets[m["subType"]], "value": _clamp(_int(m.get("value")), -10, 10)})
        else:
            c.approx("items", name, "ddb.reason.item_modifier")
    if bonuses:
        meta["bonuses"] = bonuses
    lu = _d(it.get("limitedUse"))
    mx = _int(lu.get("maxUses"))
    if 1 <= mx <= 100:
        meta["charges"] = {"max": mx, "current": _clamp(mx - _int(lu.get("numberUsed")), 0, mx),
                           "recharge": ITEM_RECHARGE.get(_int(lu.get("resetType")), "none")}
    return meta


def _items(c: _Ctx) -> None:
    custom_names = {str(v.get("valueId")): _str(v.get("value"), 200)
                    for v in _l(c.data.get("characterValues"))
                    if isinstance(v, dict) and _int(v.get("typeId")) == CV_ITEM_NAME and _str(v.get("value"))}
    out, attuned = [], [0]
    inv = [it for it in _l(c.data.get("inventory")) if isinstance(it, dict) and isinstance(it.get("definition"), dict)]
    # i nostri contenitori hanno quantità 1: un contenitore DDB con più copie resta un oggetto semplice
    box_ids = {_int(it.get("id")) for it in inv
               if it["definition"].get("isContainer") and _int(it.get("quantity"), 1) == 1}
    for it in _l(c.data.get("inventory")):
        if not isinstance(it, dict) or not isinstance(it.get("definition"), dict):
            c.skip("items", "", "ddb.reason.invalid")
            continue
        d = it["definition"]
        name = custom_names.get(str(it.get("id"))) or _str(d.get("name"))
        if not name:
            c.skip("items", "", "ddb.reason.invalid")
            continue
        try:
            item_type = _item_type(d)
            meta = _item_meta(c, d, it, item_type, name, attuned)
        except Exception:
            log.exception("ddb item %s", name)
            item_type, meta = "generic", {}
            c.approx("items", name, "ddb.reason.generic_item")
        equipped = bool(it.get("equipped"))
        bundle = max(1, _int(d.get("bundleSize"), 1))
        obj = {"name": name, "description": _text(d.get("description")),
               "weight": round(max(0.0, float(d.get("weight") or 0) if isinstance(d.get("weight"), (int, float)) else 0.0) / bundle, 3),
               "quantity": _clamp(_int(it.get("quantity"), 1), 0, 1_000_000), "item_type": item_type,
               "item_metadata": meta, "is_equipped": equipped}
        iid = _int(it.get("id"))
        if iid in box_ids:
            cap = d.get("capacityWeight")
            meta["container"] = {"capacity_lb": float(cap) if isinstance(cap, (int, float)) and cap > 0 else None,
                                 "counts_weight": d.get("weightMultiplier") != 0, "quick_access": False,
                                 "coins": {k: 0 for k in ("copper", "silver", "electrum", "gold", "platinum")}}
            obj["ref"] = iid
        elif d.get("isContainer"):
            c.approx("items", name, "ddb.reason.container_quantity")
        if _int(it.get("containerEntityId")) in box_ids:  # sciolto: containerEntityId = id del personaggio
            obj["container_ref"] = _int(it.get("containerEntityId"))
        m = c.model(ExportItem, obj, "items", name)
        if m:
            out.append(m)
    in_inventory = {_int(_d(_d(it).get("definition")).get("id")) for it in _l(c.data.get("inventory"))}
    for ci in _l(c.data.get("customItems")):
        ci = _d(ci)
        name = _str(ci.get("name"))
        if not name or _int(ci.get("id"), -1) in in_inventory:  # già importato da inventory
            continue
        obj = {"name": name, "description": _text(ci.get("description")) or _str(ci.get("notes"), 2000) or None,
               "weight": max(0.0, float(ci["weight"])) if isinstance(ci.get("weight"), (int, float)) else 0.0,
               "quantity": _clamp(_int(ci.get("quantity"), 1), 0, 1_000_000)}
        m = c.model(ExportItem, obj, "items", name)
        if m:
            out.append(m)
    # slot dopo: armatura e scudo hanno la precedenza, altrimenti due armi equipaggiate
    # elencate prima occupano entrambe le mani e la CA dello scudo va persa
    taken: set = set()
    for m in sorted((m for m in out if m.is_equipped), key=lambda m: {"armor": 0, "shield": 1}.get(m.item_type, 2)):
        m.equipment_slot = _pick_slot(m.item_type, m.name, taken)
        if m.equipment_slot:
            taken.add(m.equipment_slot)
        elif m.item_type in EQUIPMENT_SLOT_COMPAT:
            c.approx("items", m.name, "ddb.reason.no_free_slot")
    c.out["items"] = out[:500]
    char = c.out["character"]
    armor = next((i for i in out if i.item_type == "armor" and i.equipment_slot == EquipmentSlot.BODY), None)
    shield = next((i for i in out if i.item_type == "shield" and i.equipment_slot is not None), None)
    # la base include già la DES come sulla scheda DDB: l'app non la somma da sola
    dex = c.mod("dexterity")
    if armor:
        cap = {"light": dex, "medium": min(dex, 2)}.get(armor.item_metadata.get("armor_type"), 0)
        char["base_armor_class"] = armor.item_metadata.get("ac_value", 10) + cap
    else:
        unarmored = next((m for m in _modifiers(c.data) if m.get("type") == "set"
                          and m.get("subType") == "unarmored-armor-class"), None)
        base = 10 + dex
        if unarmored:
            stat = _int(unarmored.get("statId"))
            ability = ABILITIES[stat - 1] if 1 <= stat <= 6 else None
            if ability in ("wisdom", "constitution"):  # Monaco / Barbaro: l'app la tiene in sync
                char["unarmored_defense_ability"] = ability
            # come la scheda DDB: mai peggio di 10 + DES (es. Resilienza draconica con CAR negativo)
            base += max(0, (c.mod(ability) if ability else 0) + _clamp(_int(unarmored.get("value")), 0, 10))
        char["base_armor_class"] = base
    char["shield_armor_class"] = shield.item_metadata.get("ac_bonus", 2) if shield else 0
    values = [v for v in _l(c.data.get("characterValues")) if isinstance(v, dict) and v.get("value") is not None]
    char["magic_armor"] = sum(_int(v.get("value")) for v in values if _int(v.get("typeId")) in CV_AC_BONUS)
    over = {_int(v.get("typeId")): _clamp(_int(v.get("value")), 0, 100) for v in values
            if _int(v.get("typeId")) in (CV_AC_OVERRIDE, CV_AC_BASE_OVERRIDE)}
    if CV_AC_OVERRIDE in over:  # CA imposta a mano: scudo e bonus non si sommano più
        # l'app somma da sé i bonus CA degli oggetti attivi (es. Anello di protezione): si scalano dalla base
        char.update(base_armor_class=max(0, over[CV_AC_OVERRIDE] - item_bonus_total(out, "ac")),
                    shield_armor_class=0, magic_armor=0,
                    base_armor_class_override=True, shield_armor_class_override=True)
        char.pop("unarmored_defense_ability", None)
    elif CV_AC_BASE_OVERRIDE in over:
        char.update(base_armor_class=over[CV_AC_BASE_OVERRIDE], base_armor_class_override=True)
        char.pop("unarmored_defense_ability", None)


def _spell_fields(d: dict) -> dict:
    act = _d(d.get("activation"))
    unit, n = ACTIVATION.get(_int(act.get("activationType"))), _int(act.get("activationTime"), 1)
    casting = f"{n} {unit}{'s' if n > 1 and unit in ('minute', 'hour') else ''}" if unit else None
    rng = _d(d.get("range"))
    origin = _str(rng.get("origin"), 50)
    rv = _int(rng.get("rangeValue"))
    range_area = f"{rv} ft." if origin == "Ranged" and rv else origin or None
    if range_area and rng.get("aoeValue"):
        range_area += f" ({_int(rng.get('aoeValue'))} ft. {_str(rng.get('aoeType'), 30)})".replace(" )", ")")
    dur = _d(d.get("duration"))
    dt, di, du = _str(dur.get("durationType"), 30), _int(dur.get("durationInterval")), _str(dur.get("durationUnit"), 20).lower()
    span = f"{di} {du}{'s' if di > 1 else ''}" if di and du else ""
    duration = (f"Concentration, up to {span}" if dt == "Concentration" and span
                else span if dt == "Time" and span else dt or None)
    comps = ", ".join({1: "V", 2: "S", 3: "M"}[x] for x in _l(d.get("components")) if x in (1, 2, 3)) or None
    return {"casting_time": casting, "range_area": range_area, "duration": duration, "components": comps}


def _spells(c: _Ctx) -> None:
    # classi a incantesimi conosciuti (spellPrepareType nullo: bardo, stregone, warlock...): tutto è lanciabile
    known = {_int(_d(cl).get("id")) for cl in _l(c.data.get("classes"))
             if _d(_d(cl).get("definition")).get("spellPrepareType") is None}
    entries = [(s, _int(_d(cs).get("characterClassId")) in known)
               for cs in _l(c.data.get("classSpells")) for s in _l(_d(cs).get("spells"))]
    entries += [(s, True) for src in _d(c.data.get("spells")).values() for s in _l(src)]
    entries += [(s, True) for s in _l(c.data.get("_alwaysPrepared"))]  # aggiunti da fetch_ddb
    out, seen = [], set()
    for sp, always in entries:
        if isinstance(sp, dict) and not sp.get("definition") and not sp.get("id"):
            continue  # segnaposto vuoto DDB (scelta d'incantesimo non ancora fatta)
        d = _d(_d(sp).get("definition"))
        name = _str(d.get("name"))
        if not name:
            c.skip("spells", "", "ddb.reason.invalid")
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        level = _clamp(_int(d.get("level")), 0, 9)
        obj = {"export_key": f"s{len(out)}", "name": name, "level": level,
               "description": _text(d.get("description")), "is_concentration": bool(d.get("concentration")),
               "is_ritual": bool(d.get("ritual")), "school": _str(d.get("school"), 30).lower() or None,
               "srd_index": _slug(name)[:80] or None,
               "is_prepared": bool(always or sp.get("prepared") or sp.get("alwaysPrepared") or level == 0),
               **_spell_fields(d)}
        m = c.model(ExportSpell, obj, "spells", name)
        if m:
            out.append(m)
    c.out["spells"] = out[:500]


def _slots(c: _Ctx) -> None:
    out = []
    for key, pact in (("spellSlots", False), ("pactMagic", True)):
        for s in _l(c.data.get(key)):
            s = _d(s)
            lvl, used = _int(s.get("level")), _int(s.get("used"))
            if 1 <= lvl <= 9 and used > 0:
                out.append(ExportSpellSlot(level=lvl, total=0, used=used, is_pact=pact))
    c.out["spell_slots"] = out


def _max_uses(c: _Ctx, lu: dict) -> int | None:
    total = _int(lu.get("maxUses"))
    stat = _int(lu.get("statModifierUsesId"))
    if 1 <= stat <= 6:
        total += c.mod(ABILITIES[stat - 1])
    if lu.get("useProficiencyBonus"):
        total += c.prof
    return _clamp(total, 1, 1_000_000) if total > 0 else None


DDB_DAMAGE_TYPES = {1: "Bludgeoning", 2: "Piercing", 3: "Slashing", 4: "Necrotic", 5: "Acid", 6: "Cold", 7: "Fire",
                    8: "Lightning", 9: "Thunder", 10: "Poison", 11: "Psychic", 12: "Radiant", 13: "Force"}


def _abilities(c: _Ctx) -> None:
    out: list[ExportAbility] = []
    uses_out: list[dict] = []
    names: set[str] = set()
    raw_classes = c.out.get("_raw_classes", [])
    feature_owner = {_int(_d(f.get("definition")).get("id")): i
                     for i, cl in enumerate(raw_classes) for f in _l(_d(cl).get("classFeatures"))
                     if isinstance(f, dict)}

    def add(obj: dict, section: str) -> None:
        key = _LEVEL_PREFIX_RE.sub("", obj["name"].lower())  # "4: Weapon Mastery" = "Weapon Mastery"
        if key in names or key in SKIP_FEATURES or _STRUCTURAL_RE.match(key):
            return
        m = c.model(ExportAbility, obj, section, obj["name"])
        if m:
            names.add(key)
            out.append(m)

    for src, acts in _d(c.data.get("actions")).items():
        for a in _l(acts):
            a = _d(a)
            name = _str(a.get("name"))
            if not name:
                continue
            lu = _d(a.get("limitedUse"))
            mx = _max_uses(c, lu) if lu else None
            used = max(0, _int(lu.get("numberUsed")))
            if mx is not None and src == "class" and raw_classes:
                uses_out.append({"class_index": feature_owner.get(_int(a.get("componentId")), 0),
                                 "name": name, "used": used, "max": mx})
            add({"name": name, "description": _text(a.get("description") or a.get("snippet")),
                 "max_uses": mx, "uses": _clamp(mx - used, 0, mx) if mx else None, "is_passive": False,
                 "restoration_type": RESET.get(_int(lu.get("resetType")), "manual") if mx else "none"}, "abilities")
    for ca in _l(c.data.get("customActions")):  # azioni "Manage Custom": l'app non ha attacchi liberi
        ca = _d(ca)
        name = _str(ca.get("name"))
        if not name:
            continue
        dice = f"{_int(ca.get('diceCount'))}d{_int(ca.get('diceType'))}" if ca.get("diceCount") and ca.get("diceType") else ""
        stat = _int(ca.get("statId"))
        summary = " ".join(filter(None, (dice, DDB_DAMAGE_TYPES.get(_int(ca.get("damageTypeId")), ""),
                                         f"({ABILITIES[stat - 1][:3].upper()})" if 1 <= stat <= 6 else "")))
        desc = "\n\n".join(filter(None, (summary, _text(ca.get("description") or ca.get("snippet")))))
        add({"name": name, "description": desc, "is_passive": False, "restoration_type": "none"}, "abilities")
        c.approx("abilities", name, "ddb.reason.custom_action")
    passive = []
    for i, cl in enumerate(raw_classes):
        lvl = _int(_d(cl).get("level"), 1)
        passive += [f for f in _l(_d(cl).get("classFeatures"))
                    if _int(_d(_d(f).get("definition")).get("requiredLevel"), 1) <= lvl]
    passive += _l(_d(c.data.get("race")).get("racialTraits")) + _l(c.data.get("feats"))
    for f in passive:
        d = _d(_d(f).get("definition"))
        name = _str(d.get("name"))
        if name:
            add({"name": name, "description": _text(d.get("description") or d.get("snippet")),
                 "is_passive": True}, "abilities")
    c.out["abilities"] = out[:500]
    c.out["_feature_uses"] = uses_out


def _currency(c: _Ctx) -> None:
    cur = _d(c.data.get("currencies"))
    c.out["currency"] = ExportCurrency(**{k: _clamp(_int(cur.get(src)), 0, 1_000_000) for k, src in
                                          (("copper", "cp"), ("silver", "sp"), ("electrum", "ep"),
                                           ("gold", "gp"), ("platinum", "pp"))})
    c.ok("currency")


# id fissi delle condizioni DDB (ordine alfabetico inglese, esaurimento incluso)
DDB_CONDITIONS = {1: "blinded", 2: "charmed", 3: "deafened", 4: "exhaustion", 5: "frightened",
                  6: "grappled", 7: "incapacitated", 8: "invisible", 9: "paralyzed", 10: "petrified",
                  11: "poisoned", 12: "prone", 13: "restrained", 14: "stunned", 15: "unconscious"}


# characterValues del PG che l'app non sa rappresentare (adjustmentTypes della rule-data DDB)
CV_UNSUPPORTED = {5: "Override Passive Perception", 6: "Override Passive Investigation",
                  7: "Override Passive Insight", 23: "Skill Override", 24: "Skill Misc Bonus",
                  25: "Skill Magic Bonus", 27: "Skill Stat Override", 36: "Sense Override",
                  38: "Saving Throw Override", 39: "Saving Throw Misc Bonus", 40: "Saving Throw Magic Bonus"}


# lookup della rule-data DDB (creatureGroups, creatureSizes, monsterTypes)
CREATURE_KIND = {1: "wild_shape", 13: "wild_shape", 2: "familiar", 3: "companion", 5: "companion",
                 4: "mount", 6: "summon"}
CREATURE_SIZE = {2: "tiny", 3: "small", 4: "medium", 5: "large", 6: "huge", 7: "gargantuan", 10: "medium"}
CREATURE_TYPE = {1: "aberration", 2: "beast", 3: "celestial", 4: "construct", 6: "dragon", 7: "elemental",
                 8: "fey", 9: "fiend", 10: "giant", 11: "humanoid", 13: "monstrosity", 14: "ooze", 15: "plant",
                 16: "undead"}
_ENTRY_RE = re.compile(r"^(?P<name>[^.]{1,80})\.\s*(?P<desc>.*)$", re.S)
_TO_HIT_RE = re.compile(r"Attack(?: Roll)?:\s*([+-]\d+)")
_HIT_DICE_RE = re.compile(r"Hit:\s*\d+\s*\((\d+d\d+)(?:\s*([+-])\s*(\d+))?\)\s*([A-Za-z]+) damage")
_HIT_FLAT_RE = re.compile(r"Hit:\s*(\d+)\s+([A-Za-z]+) damage")


def _cr(cr_id: int) -> float:
    """challengeRatingId -> GS: 1..4 = 0, 1/8, 1/4, 1/2; poi interi (l'id 28 non esiste)."""
    return {1: 0, 2: 0.125, 3: 0.25, 4: 0.5}.get(cr_id, float(cr_id - 4 if cr_id < 28 else cr_id - 5))


def _stat_entries(html_text: Any, attacks: bool) -> list[dict]:
    out = []
    for para in _l(re.split(r"</p>", html_text) if isinstance(html_text, str) else []):
        m = _ENTRY_RE.match(_text(para) or "")
        if not m:
            continue
        e: dict = {"name": m["name"].strip(), "desc": m["desc"].strip()}
        if attacks:
            hit, dmg = _TO_HIT_RE.search(e["desc"]), _HIT_DICE_RE.search(e["desc"])
            if hit:
                e["attack_bonus"] = _clamp(int(hit[1]), -20, 30)
            if dmg:
                e["damage_dice"] = dmg[1] + (f"{dmg[2]}{dmg[3]}" if dmg[2] else "")
                e["damage_type"] = dmg[4].lower()
            elif flat := _HIT_FLAT_RE.search(e["desc"]):  # "Hit: 1 Slashing damage": l'app vuole NdX
                e["damage_dice"], e["damage_type"] = f"{flat[1]}d1", flat[2].lower()
        out.append(e)
    return out


def _creatures(c: _Ctx) -> None:
    out = []
    for cr in _l(c.data.get("creatures"))[:30]:
        cr = _d(cr)
        d = _d(cr.get("definition"))
        name = _str(cr.get("name"), 100) or _str(d.get("name"), 100)
        if not name:
            continue
        group = _int(cr.get("groupId"))
        kind = CREATURE_KIND.get(group, "companion")
        if group not in CREATURE_KIND:  # Battle Smith, sidekick, infusione...: generico
            c.approx("creatures", name, "ddb.reason.creature_group")
        elif group == 13:  # 2024: il druido tiene i suoi PF, l'app dà alla forma PF propri (2014)
            c.approx("creatures", name, "ddb.reason.wild_shape_2024")
        stats = {ABILITIES[_int(s.get("statId")) - 1][:3]: _clamp(_int(s.get("value"), 10), 1, 30)
                 for s in map(_d, _l(d.get("stats"))) if 1 <= _int(s.get("statId")) <= 6}
        speed = {f"{MOVEMENT[_int(m.get('movementId'))]}_ft": _clamp(_int(m.get("speed")), 0, 1000)
                 for m in map(_d, _l(d.get("movements"))) if _int(m.get("movementId")) in MOVEMENT}
        traits = _stat_entries(d.get("specialTraitsDescription"), False)
        actions = [a for k in ("actionsDescription", "bonusActionsDescription", "reactionsDescription")
                   for a in _stat_entries(d.get(k), True)]
        mx = _clamp(_int(d.get("averageHitPoints"), 1), 1, 10_000)
        statblock = {"size": CREATURE_SIZE.get(_int(d.get("sizeId"))), "type": CREATURE_TYPE.get(_int(d.get("typeId"))),
                     "speed": speed, "abilities": stats, "challenge_rating": _cr(_int(d.get("challengeRatingId"), 1)),
                     "traits": traits, "actions": actions}
        m = c.model(ExportCompanion, {
            "kind": kind, "name": name, "statblock": {k: v for k, v in statblock.items() if v is not None},
            "max_hp": mx, "current_hp": _clamp(mx - _int(cr.get("removedHitPoints")), 0, mx),
            "temp_hp": _clamp(_int(cr.get("temporaryHitPoints")), 0, 10_000),
            "armor_class": _clamp(_int(d.get("armorClass"), 10), 0, 100),
            "notes": _text(cr.get("description")), "is_active": bool(cr.get("isActive")) and kind == "wild_shape",
        }, "creatures", name)
        if m:
            out.append(m)
    c.out["companions"] = out


def _leftovers(c: _Ctx) -> None:
    for v in _l(c.data.get("characterValues")):
        v = _d(v)
        label, ref = CV_UNSUPPORTED.get(_int(v.get("typeId"))), _int(v.get("valueId"))
        if label and v.get("value") is not None:
            target = (DDB_SKILLS.get(ref) if 23 <= _int(v.get("typeId")) <= 27
                      else ABILITIES[ref - 1] if 38 <= _int(v.get("typeId")) <= 40 and 1 <= ref <= 6 else "")
            val = _int(v.get("value"))
            shown = f"{val:+d}" if "Bonus" in label else str(val)
            c.skip("other", f"{label}: {target + ' ' if target else ''}{shown}", "ddb.reason.not_supported")
    conds: dict = {}
    for cd in _l(c.data.get("conditions")):
        slug = DDB_CONDITIONS.get(_int(_d(cd).get("id")))
        if slug == "exhaustion":
            conds[slug] = _clamp(_int(_d(cd).get("level"), 1), 1, 6)
        elif slug:
            conds[slug] = True
        else:
            c.skip("conditions", str(_d(cd).get("id")), "ddb.reason.not_supported")
    if conds:
        c.out["character"]["conditions"] = conds


# --- recupero ----------------------------------------------------------------

# Endpoint interno non ufficiale di DDB: solo PG pubblici (privati -> 403); può cambiare.
DDB_URL = "https://character-service.dndbeyond.com/character/v5/character/{id}?includeCustomItems=true"
ALWAYS_PREPARED_URL = "https://character-service.dndbeyond.com/character/v5/game-data/always-prepared-spells"
_MAX_BYTES = 2_000_000
_ID_RE = re.compile(r"characters/(\d{1,12})(?:\D|$)")
_transport: httpx.AsyncBaseTransport | None = None  # None = rete reale


def parse_ddb_id(text: str) -> int | None:
    """ID del PG da un link DDB (qualsiasi variante) o da un ID nudo."""
    t = (text or "").strip()
    if t.isdigit() and len(t) <= 12:
        return int(t)
    m = _ID_RE.search(t)
    # ddb.ac = link breve del tasto Share di DDB
    return int(m.group(1)) if m and any(h in t.lower() for h in ("dndbeyond.com", "ddb.ac")) else None


async def _always_prepared(cl: httpx.AsyncClient, data: dict) -> list:
    """Incantesimi sempre preparati di classi/sottoclassi (dominio, giuramento...): le sottoclassi 2024
    non li scrivono nel JSON del PG. Best effort: un errore qui non blocca l'import."""
    out: list = []
    for cl_ in _l(data.get("classes"))[:4]:
        cl_ = _d(cl_)
        lvl = _clamp(_int(cl_.get("level"), 1), 1, 20)
        for d in (_d(cl_.get("definition")), _d(cl_.get("subclassDefinition"))):
            if not _int(d.get("id")):
                continue
            try:
                r = await cl.get(ALWAYS_PREPARED_URL, params={"classId": _int(d["id"]), "classLevel": lvl})
                if r.status_code == 200 and len(r.content) <= _MAX_BYTES:
                    out += [s for s in _l(_d(r.json()).get("data")) if isinstance(s, dict)]
            except (httpx.HTTPError, ValueError):
                log.warning("ddb always-prepared %s non disponibile", d.get("id"))
    return out


async def fetch_ddb(char_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10, transport=_transport, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}) as cl:
            r = await cl.get(DDB_URL.format(id=char_id))
            body = _parse_character(r)
            body["data"]["_alwaysPrepared"] = await _always_prepared(cl, body["data"])
    except httpx.HTTPError:
        raise DdbImportError("ddb_unreachable")
    return body


def _parse_character(r: httpx.Response) -> dict:
    if r.status_code in (401, 403):
        raise DdbImportError("ddb_private")
    if r.status_code == 404:
        raise DdbImportError("ddb_not_found")
    if r.status_code != 200 or len(r.content) > _MAX_BYTES:
        raise DdbImportError("ddb_unreachable")
    try:
        body = r.json()
    except ValueError:
        raise DdbImportError("ddb_unreachable")
    if not isinstance(body, dict) or not body.get("success") or not isinstance(body.get("data"), dict):
        raise DdbImportError("ddb_unreachable")
    return body


# --- entry point --------------------------------------------------------------

def _run(c: _Ctx, section: str, fn: Callable[[_Ctx], Any]) -> Any:
    try:
        return fn(c)
    except Exception:
        log.exception("ddb import: sezione %s fallita", section)
        c.skip(section, "", "ddb.reason.section_failed")
        return None


def convert(ddb: Any, lang: str = "it") -> tuple[CharacterExport, ImportReport, list[dict]]:
    """JSON DDB (involucro {success, data} o `data` nudo) -> (export, report, feature_uses).

    feature_uses: [{class_index, name, used}] cariche usate dei privilegi di classe DDB,
    da riportare sulle feature generate dal nostro motore dopo l'import.
    """
    if not isinstance(ddb, dict):
        raise DdbImportError("ddb_invalid")
    data = ddb["data"] if isinstance(ddb.get("data"), dict) else ddb
    name = _str(data.get("name"), 100)
    c = _Ctx(data, lang)
    _run(c, "classes", _classes)
    if not name or not c.out.get("classes"):
        raise DdbImportError("ddb_invalid")
    _run(c, "ability_scores", _scores)
    char: dict[str, Any] = {"name": name, "spell_slots_mode": "automatic"}
    c.out["character"] = char
    for section, fn in (("hp", _hp), ("identity", _identity), ("proficiencies", _proficiencies)):
        char.update(_run(c, section, fn) or {})
    char["notes"] = _run(c, "notes", _notes) or {}
    for section, fn in (("items", _items), ("spells", _spells), ("spell_slots", _slots),
                        ("abilities", _abilities), ("currency", _currency), ("creatures", _creatures),
                        ("other", _leftovers)):
        _run(c, section, fn)
    try:
        character = ExportCharacter.model_validate(char)
    except Exception:  # un campo inatteso non deve perdere il PG: si tiene solo l'essenziale
        log.exception("ddb import: character non valido")
        c.approx("identity", name, "ddb.reason.identity_partial")
        character = ExportCharacter(name=name, spell_slots_mode="automatic",
                                    **{k: char[k] for k in ("hit_points", "current_hit_points") if k in char})
    export = CharacterExport(
        exported_at=datetime.now(timezone.utc).isoformat(), character=character,
        classes=c.out["classes"], ability_scores=c.out.get("ability_scores", []),
        items=c.out.get("items", []), spells=c.out.get("spells", []),
        spell_slots=c.out.get("spell_slots", []), abilities=c.out.get("abilities", []),
        currency=c.out.get("currency"), companions=c.out.get("companions", []),
    )
    return export, c.report, c.out.get("_feature_uses", [])
