import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_srd_translation as chk  # noqa: E402
import srd_translation_batches as batches  # noqa: E402


def _en(s):
    return {"en": s}


SPELL = {"index": "fireball", "name": _en("Fireball"), "casting_time": _en("1 action"),
         "duration": _en("Instantaneous"), "desc": _en("Boom."), "material": None}
BEAST = {"index": "wolf", "type": "beast", "challenge_rating": 0.25, "name": _en("Wolf"),
         "traits": [{"name": _en("Keen Smell"), "desc": _en("Sniffs.")}], "actions": []}
BIG = {"index": "lich", "type": "undead", "challenge_rating": 21, "name": _en("Lich"),
       "traits": [{"name": _en("Magic Resistance"), "desc": _en("Resists.")}], "actions": []}
GLOSSARY = {"official_names": {"Fireball": "Palla di fuoco", "Wolf": "Lupo"},
            "casting_times": {"1 action": "1 azione"},
            "durations": {"Instantaneous": "Istantanea"}}


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "srd"
    d.mkdir()
    for kind in batches.KINDS:
        items = {"spells": [SPELL], "monsters": [BEAST, BIG]}.get(kind, [])
        batches.save(kind, {"_meta": {}, "items": json.loads(json.dumps(items))}, d)
    (d / "glossary-it.json").write_text(json.dumps(GLOSSARY), encoding="utf-8")
    return d


def _translate_all(data, tmp_path):
    out = tmp_path / "b"
    batches.split(out, 40, data)
    for f in out.glob("*.json"):
        entries = json.loads(f.read_text(encoding="utf-8"))
        tr = {"Fireball": "Palla di fuoco", "1 action": "1 azione", "Instantaneous": "Istantanea",
              "Wolf": "Lupo"}
        for e in entries:
            e["fields"] = {p: tr.get(v, "IT " + v) for p, v in e["fields"].items()}
        (out / f.name.replace(".json", ".it.json")).write_text(json.dumps(entries), encoding="utf-8")
    return out


def test_split_scope_and_size(data, tmp_path):
    out = tmp_path / "b"
    stats = batches.split(out, 1, data)
    assert stats["spells"][0] == 1 and stats["monsters"][0] == 2
    wolf = json.loads((out / "monsters-001.json").read_text(encoding="utf-8"))[0]
    assert set(wolf["fields"]) == {"name", "traits.0.name", "traits.0.desc"}
    lich = json.loads((out / "monsters-002.json").read_text(encoding="utf-8"))[0]
    assert set(lich["fields"]) == {"name", "traits.0.name"}  # desc out of scope for CR 21 non-beast


def test_split_skips_translated(data):
    doc = batches.load("spells", data)
    doc["items"][0]["name"]["it"] = "Palla di fuoco"
    batches.save("spells", doc, data)
    batches.split(data / "o", 40, data)
    entry = json.loads((data / "o" / "spells-001.json").read_text(encoding="utf-8"))[0]
    assert "name" not in entry["fields"]


def test_merge_round_trip_idempotent_and_checker(data, tmp_path):
    assert chk.check(data)  # nothing translated yet
    out = _translate_all(data, tmp_path)
    n = batches.merge(out, data)
    assert n > 0
    before = (data / "spells.json").read_text(encoding="utf-8")
    assert batches.merge(out, data) == n
    assert (data / "spells.json").read_text(encoding="utf-8") == before
    assert batches.load("spells", data)["items"][0]["name"] == {"en": "Fireball", "it": "Palla di fuoco"}
    lich = batches.load("monsters", data)["items"][1]
    assert "it" not in lich["traits"][0]["desc"]
    assert chk.check(data) == []


def test_merge_fails_on_unknown_index_or_path(data, tmp_path):
    out = tmp_path / "x"
    out.mkdir()
    f = out / "spells-001.it.json"
    f.write_text(json.dumps([{"index": "nope", "fields": {"name": "x"}}]), encoding="utf-8")
    with pytest.raises(SystemExit):
        batches.merge(out, data)
    f.write_text(json.dumps([{"index": "fireball", "fields": {"bogus": "x"}}]), encoding="utf-8")
    with pytest.raises(SystemExit):
        batches.merge(out, data)
    f.write_text(json.dumps([{"index": "lich", "fields": {"traits.0.desc": "x"}}]), encoding="utf-8")
    (out / "monsters-001.it.json").write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    f.unlink()
    with pytest.raises(SystemExit):
        batches.merge(out, data)


def test_checker_flags_glossary_violations(data, tmp_path):
    batches.merge(_translate_all(data, tmp_path), data)
    doc = batches.load("spells", data)
    s = doc["items"][0]
    s["name"]["it"] = "Fireball!"
    s["duration"]["it"] = "Boh"
    s["casting_time"]["it"] = "1 azione bonus"
    batches.save("spells", doc, data)
    assert len(chk.check(data)) == 3


_real = batches.load("spells")["items"]
_has_it = any("it" in s["name"] for s in _real)


@pytest.mark.skipif(not _has_it, reason="catalogue not translated yet")
def test_real_catalogue_translated():
    by_index = {s["index"]: s for s in _real}
    assert by_index["fireball"]["name"]["it"] == "Palla di fuoco"
    assert by_index["cure-wounds"]["name"]["it"] == "Cura ferite"
    races = batches.load("races")["items"]
    traits = [t for r in races for t in r["traits"] if t["index"] == "darkvision"]
    assert traits and all(t["name"]["it"] == "Scurovisione" for t in traits)
    assert chk.check() == []
