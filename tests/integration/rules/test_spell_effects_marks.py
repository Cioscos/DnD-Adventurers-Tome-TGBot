"""Effetti degli incantesimi, marchi e punizioni (tabella B): Sortilegio, Marchio del Cacciatore, le punizioni, Colpo Intrappolante,
Raffica di Spine, Freccia Folgorante, Colpo Accurato."""
from __future__ import annotations

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_2014_fighter_eldritch_knight import _sword
from tests.integration.rules.test_2014_paladin_combat import _damage, _deferred, _listed
from tests.integration.rules.test_2024_ranger import MARK as RANGER_MARK, _cast_mark, _ranger24

HEX, HM = "spell:hex:damage", "spell:hunters_mark:damage"
WRATHFUL = "spell:wrathful_smite:hit"

# (edizione, srd_index) di ogni voce della tabella B nel catalogo; Punizione Divina 2024 resta un privilegio del Paladino
ENTRIES = [("2014", s) for s in ("hex", "hunters-mark", "blinding-smite", "branding-smite", "searing-smite", "wrathful-smite", "thunderous-smite",
                                 "banishing-smite", "staggering-smite", "ensnaring-strike", "hail-of-thorns", "lightning-arrow", "true-strike")] + \
          [("2024", s) for s in ("hex", "hunters-mark", "blinding-smite", "searing-smite", "shining-smite", "wrathful-smite", "thunderous-smite",
                                 "banishing-smite", "staggering-smite", "ensnaring-strike", "hail-of-thorns", "lightning-arrow", "true-strike")]


@pytest.mark.parametrize("edition,srd", ENTRIES)
def test_every_row_of_table_b_is_in_the_catalog_for_its_edition(edition, srd):
    assert spell_effect(edition, srd) is not None


@pytest.mark.parametrize("edition,srd", [("2014", "shining-smite"), ("2024", "branding-smite"), ("2024", "divine-smite"), ("2014", "divine-smite")])
def test_rows_that_do_not_exist_in_the_edition_or_stay_class_features_have_no_entry(edition, srd):
    assert spell_effect(edition, srd) is None


def test_hex_asks_for_the_ability_and_the_smites_with_a_condition_ask_for_nothing_else():
    _, hex_ = spell_effect("2014", "hex")
    assert [c.key for c in hex_.choices] == ["ability"] and "wisdom" in hex_.choices[0].options("2014")
    assert not spell_effect("2024", "wrathful-smite")[1].choices


# --- Lanciatore -----------------------------------------------------------------------------------------------------------------
async def _caster(client, name, srd, level, *, edition="2014", concentration=True, slots=2):
    cid = (await client.post("/characters", json={"name": "Lanciatore"})).json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edition})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "srd_index": srd, "level": level, "is_concentration": concentration})
    assert r.status_code == 201, r.text
    for lvl in range(1, level + 1):
        await client.post(f"/characters/{cid}/spell_slots", json={"level": lvl, "total": slots})
    return cid, r.json()["id"]


async def _cast(client, cid, spell, level=1, **extra):
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": level, **extra})
    assert r.status_code == 200, r.text
    return r


async def _states(client, cid) -> dict[str, dict]:
    return {s["key"]: s for s in (await _full(client, cid))["active_states"]}


async def _confirm(client, cid, wid, key, die=15):
    """Un colpo con il danno rinviato e l'opzione ``key`` dopo il colpo."""
    hit = await _deferred(client, cid, wid, die)
    return await _damage(client, cid, hit, [key])


# --- Marchi -----------------------------------------------------------------------------------------------------------------------
async def test_hex_adds_a_d6_only_when_confirmed_and_asks_for_the_ability(client):
    cid, spell = await _caster(client, "Sortilegio", "hex", 1)
    wid = await _sword(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    await _cast(client, cid, spell, choices={"ability": "wisdom"})
    assert "spell:hex" in await _states(client, cid)
    assert next(o for o in await _listed(client, cid, wid) if o["key"] == HEX)["dice"] == "1d6"
    plain = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "confirm_extra_attack": True})
    assert plain.json().get("option_result") is None
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "confirm_extra_attack": True, "options": [HEX]})
    block = r.json()["option_result"]
    assert len(block["extra_rolls"]) == 1 and 1 <= block["extra_rolls"][0] <= 6
    assert "necrotic" in block["effects"][0]["en"]
    assert "spell:hex" in await _states(client, cid)  # un marchio dura: non si consuma


async def test_hunters_mark_gives_a_non_ranger_the_same_option_in_both_editions(client):
    for edition, word in (("2014", "damage"), ("2024", "force")):
        cid, spell = await _caster(client, "Marchio del Cacciatore", "hunters-mark", 1, edition=edition)
        wid = await _sword(client, cid)
        assert HM not in await _roll_keys(client, cid, "attack", item_id=wid)
        await _cast(client, cid, spell)
        assert HM in await _roll_keys(client, cid, "attack", item_id=wid)
        r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "confirm_extra_attack": True, "options": [HM]})
        block = r.json()["option_result"]
        assert len(block["extra_rolls"]) == 1 and word in block["effects"][0]["en"]


async def test_the_ranger_keeps_only_its_own_mark_option_so_the_damage_is_not_counted_twice(client):
    cid = await _ranger24(client, 5)
    wid = await _sword(client, cid)
    await _cast_mark(client, cid)
    assert "spell:hunters_mark" in await _states(client, cid)
    keys = await _roll_keys(client, cid, "attack", item_id=wid)
    assert RANGER_MARK in keys and HM not in keys


# --- Punizioni --------------------------------------------------------------------------------------------------------------------
async def test_a_2014_smite_with_a_lasting_effect_adds_its_dice_once_and_keeps_the_concentration(client):
    cid, spell = await _caster(client, "Punizione Collerica", "wrathful-smite", 1)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell)
    r = await _confirm(client, cid, wid, WRATHFUL)
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert len(block["extra_rolls"]) == 1 and block["targets"] == [WRATHFUL]  # 1d6 e la condizione da applicare
    assert "spell:wrathful_smite" in await _states(client, cid)  # l'incantesimo dura: la paura lo richiede
    assert (await _full(client, cid))["concentrating_spell_id"] == spell
    hit = await _deferred(client, cid, wid)
    assert (await _damage(client, cid, hit, [WRATHFUL])).status_code == 409  # già scaricata


async def test_a_one_shot_smite_ends_the_spell_and_the_concentration_on_the_hit(client):
    cid, spell = await _caster(client, "Punizione Tonante", "thunderous-smite", 1)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell)
    assert (await _full(client, cid))["concentrating_spell_id"] == spell
    r = await _confirm(client, cid, wid, "spell:thunderous_smite:hit")
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 2
    assert "spell:thunderous_smite" not in await _states(client, cid)
    assert (await _full(client, cid))["concentrating_spell_id"] is None


async def test_the_damage_type_and_the_dice_follow_the_edition_and_the_slot(client):
    cid, spell = await _caster(client, "Punizione Collerica", "wrathful-smite", 1, edition="2024", slots=2)
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 2, "total": 1})
    wid = await _sword(client, cid)
    await _cast(client, cid, spell, level=2)
    option = next(o for o in await _listed(client, cid, wid) if o["key"] == WRATHFUL)
    assert "necrotic" in option["label"].lower() or "necrotic" in option["label"]
    r = await _confirm(client, cid, wid, WRATHFUL)
    assert len(r.json()["option_result"]["extra_rolls"]) == 2  # 1d6 + 1d6 per il secondo slot
    old, old_spell = await _caster(client, "Punizione Collerica", "wrathful-smite", 1)
    await _cast(client, old, old_spell)
    r = await _confirm(client, old, await _sword(client, old), WRATHFUL)
    assert "psichici" in r.json()["option_result"]["effects"][0]["it"] and len(r.json()["option_result"]["extra_rolls"]) == 1


async def test_a_ranged_smite_is_not_offered_on_a_melee_attack_and_a_melee_one_not_on_a_ranged_attack(client):
    cid, spell = await _caster(client, "Raffica di Spine", "hail-of-thorns", 1)
    wid = await _sword(client, cid)
    bow = await _sword(client, cid, weapon_type="ranged")
    await _cast(client, cid, spell)
    assert "spell:hail_of_thorns:hit" not in [o["key"] for o in await _listed(client, cid, wid)]
    assert "spell:hail_of_thorns:hit" in [o["key"] for o in await _listed(client, cid, bow)]
    melee, melee_spell = await _caster(client, "Punizione Tonante", "thunderous-smite", 1)
    arrow = await _sword(client, melee, weapon_type="ranged")
    await _cast(client, melee, melee_spell)
    assert "spell:thunderous_smite:hit" not in [o["key"] for o in await _listed(client, melee, arrow)]


async def test_true_strike_2014_gives_advantage_once(client):
    cid, spell = await _caster(client, "Colpo Accurato", "true-strike", 0)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell, level=0)
    key = "spell:true_strike:advantage"
    assert key in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 5, "options": [key], "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "advantage" and len(r.json()["dice"]) == 2
    assert key not in await _roll_keys(client, cid, "attack", item_id=wid)


# --- Condizioni sul nemico ------------------------------------------------------------------------------------------------------
async def _in_encounter(client, factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, factory)
    pc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    as_user(PLAYER_ID)
    return sid, pc["character_id"]


async def _hero_smite(client, cid, name, srd, level, edition="2014", concentration=True):
    await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": name, "srd_index": srd, "level": level, "is_concentration": concentration})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": level, "total": 2})
    await _cast(client, cid, spell, level=level)
    return spell


async def test_wrathful_smite_on_a_combatant_frightens_it_until_the_concentration_ends(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    spell = await _hero_smite(client, cid, "Punizione Collerica", "wrathful-smite", 1)
    wid = await _sword(client, cid)
    r = await _confirm(client, cid, wid, WRATHFUL)
    assert r.status_code == 200, r.text
    effect = (await client.get(f"/characters/{cid}/target-effects/{WRATHFUL}")).json()
    assert effect["result"]["condition"] == "frightened" and effect["result"]["ends_with_concentration"] is True
    assert effect["result"]["save_ability"] == "wisdom" and effect["result"]["save_dc"] >= 8
    goblin = next(c["id"] for c in effect["combatants"] if c["kind"] == "monster")
    r = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": goblin, "effect_key": WRATHFUL})
    assert r.status_code == 200 and r.json()["applied"] is True and r.json()["pending_save_id"] is not None
    from sqlalchemy import select
    from core.db.models import ConditionEffect
    async with test_session_factory() as s:
        eff = (await s.execute(select(ConditionEffect).where(ConditionEffect.combatant_id == goblin))).scalar_one()
        assert eff.ends_with_concentration is True and eff.source_spell_id == spell and eff.slug == "frightened"


async def test_a_smite_outside_an_encounter_leaves_only_the_text_for_the_gm(client):
    cid, spell = await _caster(client, "Punizione Collerica", "wrathful-smite", 1)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell)
    r = await _confirm(client, cid, wid, WRATHFUL)
    block = r.json()["option_result"]
    assert "Saggezza" in block["effects"][0]["it"] and block["targets"] == [WRATHFUL]
    result = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": 1, "effect_key": WRATHFUL})
    assert result.status_code == 200 and result.json()["applied"] is False


async def test_a_smite_without_a_condition_offers_no_target_effect(client):
    cid, spell = await _caster(client, "Punizione Marchiante", "branding-smite", 2)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell, level=2)
    r = await _confirm(client, cid, wid, "spell:branding_smite:hit")
    block = r.json()["option_result"]
    assert block["targets"] == [] and len(block["extra_rolls"]) == 2


def test_divine_smite_2024_stays_the_paladin_feature_and_not_a_catalog_spell():
    assert spell_effect("2024", "divine-smite") is None
