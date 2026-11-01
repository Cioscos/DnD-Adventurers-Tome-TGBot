"""Import da D&D Beyond: JSON del character-service -> CharacterExport + report.

Il JSON DDB contiene dati grezzi (non i valori calcolati dalla scheda): qui si ricavano
solo gli input che la nostra app usa (caratteristiche finali, PF max, oggetti, ...);
TS, abilità, CA e slot li ricalcola l'app. Ogni sezione è isolata: un dato inatteso
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
    ExportCurrency, ExportItem, ExportSpell, ExportSpellSlot,
)
from core.data.damage_types import canonical_damage_type
from core.data.skills import SKILL_ABILITY_MAP
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
# activationType DDB
ACTIVATION = {1: "action", 3: "bonus action", 4: "reaction", 6: "minute", 7: "hour"}
SKIP_FEATURES = {"hit points", "proficiencies", "equipment", "ability score improvement",
                 "ability score increase", "languages", "age", "size", "speed", "alignment"}
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


def _modifiers(data: dict, sources: tuple[str, ...] | None = None) -> list[dict]:
    mods = _d(data.get("modifiers"))
    return [(m | {"_src": src}) for src, ms in mods.items()
            if sources is None or src in sources for m in _l(ms) if isinstance(m, dict)]


class _Ctx:
    def __init__(self, data: dict):
        self.data = data
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
        obj = {"class_name": key or raw, "level": _clamp(_int(cl.get("level"), 1), 1, 20),
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


def _identity(c: _Ctx) -> dict:
    d = c.data
    bg = _d(d.get("background"))
    race = _d(d.get("race"))
    traits = _d(d.get("traits"))
    speed = _int(_d(_d(race.get("weightSpeeds")).get("normal")).get("walk"), 30)
    ds = _d(d.get("deathSaves"))
    out = {
        "race": _str(race.get("fullName"), 100) or None,
        "gender": _str(d.get("gender"), 50) or None,
        "experience_points": _clamp(_int(d.get("currentXp")), 0, 1_000_000),
        "heroic_inspiration": bool(d.get("inspiration")),
        "background": (_str(_d(bg.get("definition")).get("name"), 100)
                       or _str(_d(bg.get("customBackground")).get("name"), 100) or None),
        "alignment": ALIGNMENTS.get(_int(d.get("alignmentId"))),
        "speed": _clamp(speed, 0, 1000) or 30,
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
                c.skip("defenses", label, "ddb.reason.unknown_damage_type")
            elif slug not in dmg[key]:
                dmg[key].append(slug)
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
    out, taken, attuned = [], set(), [0]
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
        slot = _pick_slot(item_type, name, taken) if equipped else None
        if slot:
            taken.add(slot)
        bundle = max(1, _int(d.get("bundleSize"), 1))
        obj = {"name": name, "description": _text(d.get("description")),
               "weight": round(max(0.0, float(d.get("weight") or 0) if isinstance(d.get("weight"), (int, float)) else 0.0) / bundle, 3),
               "quantity": _clamp(_int(it.get("quantity"), 1), 0, 1_000_000), "item_type": item_type,
               "item_metadata": meta, "is_equipped": equipped, "equipment_slot": slot}
        m = c.model(ExportItem, obj, "items", name)
        if m:
            out.append(m)
    for ci in _l(c.data.get("customItems")):
        ci = _d(ci)
        name = _str(ci.get("name"))
        if not name:
            continue
        obj = {"name": name, "description": _text(ci.get("description")) or _str(ci.get("notes"), 2000) or None,
               "weight": max(0.0, float(ci["weight"])) if isinstance(ci.get("weight"), (int, float)) else 0.0,
               "quantity": _clamp(_int(ci.get("quantity"), 1), 0, 1_000_000)}
        m = c.model(ExportItem, obj, "items", name)
        if m:
            out.append(m)
    c.out["items"] = out[:500]
    char = c.out["character"]
    armor = next((i for i in out if i.item_type == "armor" and i.equipment_slot == EquipmentSlot.BODY), None)
    shield = next((i for i in out if i.item_type == "shield" and i.equipment_slot is not None), None)
    char["base_armor_class"] = armor.item_metadata.get("ac_value", 10) if armor else 10
    char["shield_armor_class"] = shield.item_metadata.get("ac_bonus", 2) if shield else 0
    char["magic_armor"] = sum(_int(v.get("value")) for v in _l(c.data.get("characterValues"))
                              if isinstance(v, dict) and _int(v.get("typeId")) in CV_AC_BONUS)


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
    entries = [s for cs in _l(c.data.get("classSpells")) for s in _l(_d(cs).get("spells"))]
    entries += [s for src in _d(c.data.get("spells")).values() for s in _l(src)]
    out, seen = [], set()
    for sp in entries:
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
               "is_prepared": bool(sp.get("prepared") or sp.get("alwaysPrepared") or level == 0),
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


def _abilities(c: _Ctx) -> None:
    out: list[ExportAbility] = []
    uses_out: list[dict] = []
    names: set[str] = set()
    raw_classes = c.out.get("_raw_classes", [])
    feature_owner = {_int(_d(f.get("definition")).get("id")): i
                     for i, cl in enumerate(raw_classes) for f in _l(_d(cl).get("classFeatures"))
                     if isinstance(f, dict)}

    def add(obj: dict, section: str) -> None:
        key = obj["name"].lower()
        if key in names or key in SKIP_FEATURES:
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
                                 "name": name, "used": used})
            add({"name": name, "description": _text(a.get("description") or a.get("snippet")),
                 "max_uses": mx, "uses": _clamp(mx - used, 0, mx) if mx else None, "is_passive": False,
                 "restoration_type": RESET.get(_int(lu.get("resetType")), "manual") if mx else "none"}, "abilities")
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


def _leftovers(c: _Ctx) -> None:
    for cr in _l(c.data.get("creatures")):
        c.skip("creatures", _str(_d(cr).get("name")) or _str(_d(_d(cr).get("definition")).get("name")),
               "ddb.reason.not_supported")
    if _l(c.data.get("conditions")):
        c.skip("conditions", "", "ddb.reason.not_supported")


# --- recupero ----------------------------------------------------------------

# Endpoint interno non ufficiale di DDB: solo PG pubblici (privati -> 403); può cambiare.
DDB_URL = "https://character-service.dndbeyond.com/character/v5/character/{id}?includeCustomItems=true"
_MAX_BYTES = 2_000_000
_ID_RE = re.compile(r"characters/(\d{1,12})(?:\D|$)")
_transport: httpx.AsyncBaseTransport | None = None  # None = rete reale


def parse_ddb_id(text: str) -> int | None:
    """ID del PG da un link DDB (qualsiasi variante) o da un ID nudo."""
    t = (text or "").strip()
    if t.isdigit() and len(t) <= 12:
        return int(t)
    m = _ID_RE.search(t)
    return int(m.group(1)) if m and "dndbeyond.com" in t.lower() else None


async def fetch_ddb(char_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10, transport=_transport, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}) as cl:
            r = await cl.get(DDB_URL.format(id=char_id))
    except httpx.HTTPError:
        raise DdbImportError("ddb_unreachable")
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


def convert(ddb: Any) -> tuple[CharacterExport, ImportReport, list[dict]]:
    """JSON DDB (involucro {success, data} o `data` nudo) -> (export, report, feature_uses).

    feature_uses: [{class_index, name, used}] cariche usate dei privilegi di classe DDB,
    da riportare sulle feature generate dal nostro motore dopo l'import.
    """
    if not isinstance(ddb, dict):
        raise DdbImportError("ddb_invalid")
    data = ddb["data"] if isinstance(ddb.get("data"), dict) else ddb
    name = _str(data.get("name"), 100)
    c = _Ctx(data)
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
                        ("abilities", _abilities), ("currency", _currency), ("other", _leftovers)):
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
        currency=c.out.get("currency"),
    )
    return export, c.report, c.out.get("_feature_uses", [])
