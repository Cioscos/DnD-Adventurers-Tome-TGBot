import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_spell_catalogs as bsc  # noqa: E402
from rules_spells import RuleSpell  # noqa: E402

GLOSSARY = {"casting_times": {"1 action": "1 azione", "1 bonus action": "1 azione bonus"},
            "durations": {"Instantaneous": "Istantanea", "1 hour": "1 ora", "1 minute": "1 minuto", "Up to 1 minute": "Concentrazione, fino a 1 minuto"},
            "official_names": {}}


def _row(it, en, summary="", **kw):
    base = dict(name_it=it, name_en=en, level=1, school="evocation", classes=["warlock"], casting_time="1 azione",
                range_text="Incantatore", range_ft=None, components=["V", "S"], material=None, duration="1 ora",
                concentration=False, ritual=False, summary_it=summary)
    return RuleSpell(**{**base, **kw})


def _doc():
    return {"_meta": {"source": "x"}, "items": [{
        "index": "acid-arrow", "name": {"en": "Acid Arrow", "it": "Freccia acida"}, "level": 2, "school": "evocation",
        "classes": ["wizard"], "desc": {"en": "Arrow.", "it": "Freccia."}}]}


ROWS = [_row("Freccia Acida di Melf", "Melf's Acid Arrow", classes=["wizard"]),
        _row("Malocchio", "Hex", "Bersaglio maledetto: +1d6 necrotici a ogni colpo; TS Sag", classes=["warlock"],
             casting_time="1 azione bonus", duration="Concentrazione, 1 minuto", concentration=True, range_text="27 m",
             range_ft=90, components=["V", "S", "M"], material="l'occhio pietrificato di un tritone")]
EN = {"hex": {"desc": "Cursed target: +1d6 necrotic on each hit.", "material": "the petrified eye of a newt"}}


def test_merge_2014_renames_and_adds_phb():
    out = bsc.merge_2014(_doc(), ROWS, EN, GLOSSARY)
    by = {i["index"]: i for i in out["items"]}
    arrow = by["acid-arrow"]
    assert arrow["name"] == {"en": "Melf's Acid Arrow", "it": "Freccia Acida di Melf"}
    assert arrow["aliases"] == ["Freccia acida"] and arrow["source"] == "srd"
    assert arrow["desc"] == {"en": "Arrow.", "it": "Freccia."}
    hexe = by["hex"]
    assert hexe["source"] == "phb" and hexe["name"] == {"en": "Hex", "it": "Malocchio"}
    assert hexe["desc"] == {"it": "Bersaglio maledetto: +1d6 necrotici a ogni colpo; TS Sag",
                            "en": "Cursed target: +1d6 necrotic on each hit."}
    assert hexe["casting_time"] == {"en": "1 bonus action", "it": "1 azione bonus"}
    assert hexe["duration"] == {"en": "Up to 1 minute", "it": "Concentrazione, fino a 1 minuto"}
    assert hexe["range_text"] == {"en": "90 feet", "it": "90 piedi"} and hexe["range_ft"] == 90
    assert hexe["material"] == {"it": "l'occhio pietrificato di un tritone", "en": "the petrified eye of a newt"}
    assert (hexe["damage_dice"], hexe["damage_type"], hexe["save_ability"]) == ("1d6", "necrotic", "wis")
    assert hexe["classes"] == ["warlock"] and hexe["concentration"] is True


def test_merge_2014_is_idempotent():
    once = bsc.merge_2014(_doc(), ROWS, EN, GLOSSARY)
    assert bsc.merge_2014(copy.deepcopy(once), ROWS, EN, GLOSSARY) == once


def test_merge_2014_fails_on_missing_english():
    try:
        bsc.merge_2014(_doc(), ROWS, {}, GLOSSARY)
    except SystemExit as e:
        assert "hex" in str(e)
    else:
        raise AssertionError("expected SystemExit")


FIREBALL = {"index": "fireball", "name": "Fireball", "level": 3, "school": {"index": "evocation"},
            "casting_time": "Action", "range": "150 feet", "components": ["V", "S", "M"],
            "material": "a ball of bat guano and sulfur", "duration": "Instantaneous", "concentration": False,
            "ritual": False, "classes": [{"index": "sorcerer"}, {"index": "wizard"}],
            "description": "A bright streak flashes. Each creature in a 20-foot-radius Sphere makes a Dexterity saving "
                           "throw, taking 8d6 Fire damage on a failed save.",
            "higher_level": "The damage increases by 1d6 for each spell slot level above 3.",
            "damage": {"damage_type": {"index": "fire"}, "damage_at_slot_level": {"3": "8d6"}}}


def test_build_2024_from_api():
    rows = [_row("Palla di Fuoco", "Fireball", level=3, classes=["sorcerer", "wizard"])]
    doc = bsc.build_2024([FIREBALL], rows, {}, GLOSSARY)
    fb = doc["items"][0]
    assert "SRD 5.2" in doc["_meta"]["source"]
    assert fb["name"] == {"en": "Fireball", "it": "Palla di Fuoco"} and fb["source"] == "srd"
    assert (fb["attack_type"], fb["save_ability"]) == ("SAVE", "dex")
    assert fb["area"] == {"type": "sphere", "size_ft": 20}
    assert (fb["damage_dice"], fb["damage_type"], fb["higher_levels_dice"]) == ("8d6", "fire", "1d6")
    assert fb["casting_time"] == {"en": "1 action", "it": "1 azione"} and fb["range_ft"] == 150
    assert fb["desc"] == {"en": FIREBALL["description"]}  # l'italiano arriva dai lotti di traduzione


def test_build_2024_tolerates_api_glitches():
    s = {**FIREBALL, "range": "60 feet Component: V, S", "duration": "Concentration up to 1 minute"}
    rows = [_row("Palla di Fuoco", "Fireball", level=3)]
    fb = bsc.build_2024([s], rows, {}, GLOSSARY)["items"][0]
    assert fb["range_ft"] == 60 and fb["duration"]["en"] == "Up to 1 minute"


def test_build_2024_healing_is_not_damage_upcast():
    cure = {**FIREBALL, "index": "cure-wounds", "damage": None, "level": 1,
            "description": "A creature regains 2d8 Hit Points.", "higher_level": "The healing increases by 2d8 for each spell slot level above 1."}
    e = bsc.build_2024([cure], [_row("Cura Ferite", "Cure Wounds")], {}, GLOSSARY)["items"][0]
    assert e["higher_levels_dice"] is None


def test_build_2024_concentration_duration_and_line():
    s = {**FIREBALL, "duration": "1 minute", "concentration": True,
         "description": "A 100-foot-long, 5-foot-wide Line blasts out. Dexterity saving throw."}
    e = bsc.build_2024([s], [_row("Palla di Fuoco", "Fireball")], {}, GLOSSARY)["items"][0]
    assert e["duration"]["en"] == "Up to 1 minute"
    assert e["area"] == {"type": "line", "size_ft": 100}


def test_build_2024_falls_back_to_2014_mechanics():
    mm = {**FIREBALL, "index": "magic-missile", "damage": None, "description": "Three darts hit for 1d4 + 1 each.",
          "higher_level": "One more dart (1d4 + 1) for each slot level above 1."}
    prev = {"magic-missile": {"damage_dice": "1d4+1", "damage_type": "force", "higher_levels_dice": "1d4+1",
                              "attack_type": None, "save_ability": None, "area": None}}
    e = bsc.build_2024([mm], [_row("Dardo Incantato", "Magic Missile")], {}, GLOSSARY, prev)["items"][0]
    assert (e["damage_dice"], e["damage_type"], e["higher_levels_dice"]) == ("1d4+1", "force", "1d4+1")


# --- file reali ------------------------------------------------------------------------------------------------------
import json  # noqa: E402

from core.rules.catalog.spells import SPELL_EFFECTS, spell_effect  # noqa: E402

DATA = ROOT / "webapp" / "src" / "data" / "srd"
CATALOGS = {ed: json.loads((DATA / f).read_text(encoding="utf-8"))["items"]
            for ed, f in (("2014", "spells.json"), ("2024", "spells-2024.json"))}
# Effetti di incantesimi che nessuna tabella dei manuali elenca, per edizione (motivo accanto).
KNOWN_MISSING: dict[tuple[str, str], str] = {}


def test_effects_reachable_from_their_edition_catalog():
    missing = []
    for e in SPELL_EFFECTS.values():
        for ed in e.variants:
            idx = {i["index"] for i in CATALOGS[ed]}
            if e.srd_index and not set(e.srd_index) & idx and (e.key, ed) not in KNOWN_MISSING:  # senza indice: effetto interno
                missing.append(f"{ed}:{e.key}{e.srd_index}")
    assert not missing, missing


def test_manual_names_reach_the_same_effect():
    wrong = []
    for ed, items in CATALOGS.items():
        for i in items:
            found = spell_effect(ed, i["index"])
            if not found:
                continue
            for lang in ("it", "en"):
                by_name = spell_effect(ed, None, i["name"][lang])
                if not by_name or by_name[0] is not found[0]:
                    wrong.append(f"{ed}:{i['index']}:{i['name'][lang]}")
    assert not wrong, wrong


def test_catalog_shape():
    for ed, items in CATALOGS.items():
        assert len(items) >= (355 if ed == "2014" else 385)
        assert len({i["index"] for i in items}) == len(items)
        for i in items:
            assert i["name"].get("it") and i["name"].get("en"), i["index"]
            assert i["desc"].get("it") and i["desc"].get("en"), i["index"]
            assert i["classes"] and i["source"] in ("srd", "phb"), i["index"]


_DMG_EN = r"(\d+d\d+(?:\s*\+\s*\d+)?) (?:Acid|Bludgeoning|Cold|Fire|Force|Lightning|Necrotic|Piercing|Poison|Psychic|Radiant|Slashing|Thunder) damage"


def test_2024_roll_fields_come_from_the_2024_text():
    """Niente dadi o TS ereditati dal 2014 che il testo 2024 non ha (Sonno, Spada di Mordenkainen, Luce)."""
    import re
    wrong = []
    for i in CATALOGS["2024"]:
        if i["source"] != "srd":
            continue
        text = i["desc"]["en"] + " " + ((i.get("higher_level") or {}).get("en") or "")
        flat = re.sub(r"\s+", "", text)
        if i["damage_dice"] and i["damage_dice"] not in flat:
            wrong.append(f"{i['index']}: dadi {i['damage_dice']}")
        if i["higher_levels_dice"] and i["higher_levels_dice"] not in flat:
            wrong.append(f"{i['index']}: slot superiori {i['higher_levels_dice']}")
        if i["save_ability"] and "saving throw" not in text:
            wrong.append(f"{i['index']}: TS {i['save_ability']}")
    assert not wrong, wrong


def test_2024_known_roll_fields():
    by = {i["index"]: i for i in CATALOGS["2024"]}
    assert by["sleep"]["damage_dice"] is None
    assert by["arcane-sword"]["damage_dice"] == "4d12"
    assert by["wall-of-ice"]["higher_levels_dice"] == "2d6"
    assert by["spiritual-weapon"]["higher_levels_dice"] == "1d8"
    assert by["magic-missile"]["damage_dice"] == "1d4+1"


def test_phb_summaries_keep_their_dice():
    import re
    stems = r"(?:danni|acid|contundent|fredd|fuoc|forza|fulmin|necrotic|perforant|velen|psichic|radios|radiant|taglient|tuon)"
    lost = [f"{ed}:{i['index']}" for ed, items in CATALOGS.items() for i in items
            if i["source"] == "phb" and re.search(r"\d+d\d+\s+(?:danni\s+)?(?:extra\s+)?(?:da\s+|di\s+)?" + stems, i["desc"]["it"], re.I)
            and not i["damage_dice"]]
    assert not lost, lost


def test_phb_known_roll_fields():
    by14 = {i["index"]: i for i in CATALOGS["2014"]}
    by24 = {i["index"]: i for i in CATALOGS["2024"]}
    assert (by14["chromatic-orb"]["damage_dice"], by14["chromatic-orb"]["attack_type"]) == ("3d8", "ATK")
    assert by24["grasping-vine"]["attack_type"] == "ATK"
    assert by24["blinding-smite"]["damage_type"] == "radiant"
    assert by14["silence"]["classes"] == ["bard", "cleric", "ranger"]


def test_build_2024_no_fallback_when_2024_text_lacks_the_dice():
    sl = {**FIREBALL, "index": "sleep", "damage": None, "description": "Wisdom saving throw or Incapacitated.", "higher_level": None}
    prev = {"sleep": {"damage_dice": "5d8", "damage_type": None, "higher_levels_dice": "2d8"}}
    e = bsc.build_2024([sl], [_row("Sonno", "Sleep")], {}, GLOSSARY, prev)["items"][0]
    assert (e["damage_dice"], e["higher_levels_dice"], e["save_ability"]) == (None, None, "wis")


def test_build_2024_ignores_saves_inside_the_stat_block():
    s = {**FIREBALL, "index": "summon-elemental", "damage": None, "description": "Summons a spirit with the Elemental Spirit stat block: AC 11, "
                                                    "Breath 2d6 (Dexterity saving throw), Slam 1d10+4"}
    e = bsc.build_2024([s], [_row("Evoca Elementale", "Summon Elemental")], {}, GLOSSARY)["items"][0]
    assert (e["attack_type"], e["save_ability"]) == (None, None)


def test_area_from_italian_summary_in_feet():
    assert bsc.area_from_it("Emanazione 10 ft: ogni creatura fa TS For") == {"type": "emanation", "size_ft": 10}
    assert bsc.area_from_it("Sfera di 20 piedi di raggio: TS Intelligenza") == {"type": "sphere", "size_ft": 20}
    assert bsc.area_from_it("Cubo di 1,5 m di pugnali") == {"type": "cube", "size_ft": 5}
    assert bsc.area_from_it("creature entro 3 m") is None


def test_phb_entry_area_falls_back_to_summary():
    row = _row("Braccia di Hadar", "Arms of Hadar", "Emanazione 10 ft: ogni creatura fa TS For o 2d6 necrotico")
    e = bsc.phb_entry(row, "arms-of-hadar", {"desc": "x"}, GLOSSARY)
    assert e["area"] == {"type": "emanation", "size_ft": 10}


def test_keep_meta_when_items_unchanged():
    old = {"_meta": {"generated_at": "2026-11-12"}, "items": [{"index": "a"}]}
    same = {"_meta": {"generated_at": "2026-11-13"}, "items": [{"index": "a"}]}
    changed = {"_meta": {"generated_at": "2026-11-13"}, "items": [{"index": "b"}]}
    assert bsc.keep_meta(old, same)["_meta"]["generated_at"] == "2026-11-12"
    assert bsc.keep_meta(old, changed)["_meta"]["generated_at"] == "2026-11-13"
