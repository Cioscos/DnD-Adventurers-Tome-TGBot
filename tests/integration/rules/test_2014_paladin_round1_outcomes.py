"""Paladino 2014, giro di correzione 1 (I10): esiti completi per mappatura e manuale, tradotti in entrambe le lingue."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.rules.catalog import features_for
from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2014_paladin import DS, _paladin
from tests.integration.rules.test_2014_paladin_oaths import EC, _effect

ROOT = Path(__file__).resolve().parents[3]
LOCALES = {lang: json.loads((ROOT / "webapp" / "src" / "locales" / f"{lang}.json").read_text(encoding="utf-8")) for lang in ("it", "en")}


def _summary(key: str) -> dict:
    return next(f.summary for f in features_for("2014", "paladin") if f.key == key)


async def _effect_of(client, cid, key, **params):
    r = await _use(client, cid, key, params=params or None)
    assert r.status_code == 200, r.text
    return await _effect(client, cid, key)


# Effetti sul bersaglio: ogni uno porta una nota che il foglio traduce
@pytest.mark.parametrize("oath,level,key,note", [
    ("vengeance", 5, "paladin.abjure_enemy", "abjure_enemy"),
    ("devotion", 5, "paladin.turn_the_unholy", "turn_the_unholy"),
    ("ancients", 5, "paladin.turn_the_faithless", "turn_the_faithless"),
    ("vengeance", 20, "paladin.avenging_angel", "avenging_angel"),
])
async def test_each_effect_on_others_carries_a_note_the_sheet_can_translate(client, oath, level, key, note):
    cid = await _paladin(client, level, oath, charisma=16)
    fx = await _effect_of(client, cid, key)
    assert fx["note"] == note
    for lang in ("it", "en"):
        assert LOCALES[lang]["character"]["target_effect"]["notes"][note].strip()


async def test_the_avenging_angel_frightens_with_the_spell_dc_and_can_be_applied_from_the_flow(client):
    cid = await _paladin(client, 20, "vengeance", charisma=16)  # competenza +6, Carisma +3: CD 17
    fx = await _effect_of(client, cid, "paladin.avenging_angel")
    assert (fx["condition"], fx["save_ability"], fx["save_dc"], fx["rounds"]) == ("frightened", "wisdom", 17, 10)
    assert "avenging_angel" in [s["key"] for s in (await _full(client, cid))["active_states"]]


async def test_the_abjure_note_says_what_the_manual_adds_to_the_condition(client):
    notes = LOCALES["it"]["character"]["target_effect"]["notes"]["abjure_enemy"]
    for word in ("velocità", "dimezzata", "svantaggio", "immune", "danno"):
        assert word in notes


async def test_the_turn_notes_say_until_damage(client):
    notes = LOCALES["it"]["character"]["target_effect"]["notes"]
    assert "danno" in notes["turn_the_unholy"] and "danno" in notes["turn_the_faithless"]


@pytest.mark.parametrize("key,words_it,words_en", [
    ("paladin.turn_the_faithless", ("fino al danno",), ("until damaged",)),
    ("paladin.abjure_enemy", ("fino al danno", "svantaggio"), ("until damaged", "disadvantage")),
    ("paladin.vow_of_enmity", ("priva di sensi",), ("unconscious",)),
    ("paladin.elder_champion", ("3 m", "incantesimi da paladino", "Incanalare Divinità"), ("10 ft", "paladin spells", "Channel Divinity")),
    ("paladin.avenging_angel", ("vi inizia il turno", "1 minuto", "vantaggio"), ("starts its turn", "1 minute", "advantage")),
])
def test_the_summaries_carry_the_clauses_the_review_found_missing(key, words_it, words_en):
    summary = _summary(key)
    assert all(w in summary["it"] for w in words_it), summary["it"]
    assert all(w in summary["en"] for w in words_en), summary["en"]
    assert len(summary["it"]) <= 200 and len(summary["en"]) <= 200


async def test_divine_sense_says_how_long_it_lasts_and_how_far(client):
    cid = await _paladin(client, 1, charisma=14)
    data = (await _use(client, cid, DS)).json()["state"]["data"]
    assert data["range_m"] == 18 and data["until"] == "next_turn_end"


async def test_every_fact_the_states_carry_has_a_reader_in_the_bar():
    source = (ROOT / "webapp" / "src" / "components" / "rules" / "ActiveStatesBar.tsx").read_text(encoding="utf-8")
    for field in ("range_m", "radius_m", "fly_ft", "start_heal", "start_damage", "until"):
        assert f"d.{field}" in source, field
    for lang in ("it", "en"):
        turn = LOCALES[lang]["character"]["turn"]
        for key in ("state_radius", "state_fly", "state_start_heal", "state_start_damage", "state_until_next_turn_end"):
            assert turn[key].strip(), (lang, key)
