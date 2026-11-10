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


# --- Giro 1 della revisione ------------------------------------------------------------------------------------------------------
BLAST = dict(name="Deflagrazione Occulta", srd_index="eldritch-blast", attack_save="ATK", damage_dice="1d10", damage_type="force")


async def _blast(client, cid) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"level": 0, "casting_time": "1 azione", **BLAST})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _spell_attack(client, cid, blast, die=12, options=()):
    r = await client.post(f"/characters/{cid}/spells/{blast}/attack", json={"die": die, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


async def _roll_damage(client, cid, blast, **body):
    r = await client.post(f"/characters/{cid}/spells/{blast}/roll_damage", json={"casting_level": 0, **body})
    assert r.status_code == 200, r.text
    return r.json()


# I-1: i marchi valgono anche sugli attacchi con incantesimo, il dado confermato arriva al danno
@pytest.mark.parametrize("edition,srd,name,key", [("2014", "hex", "Sortilegio", HEX), ("2024", "hex", "Sortilegio", HEX),
                                                  ("2024", "hunters-mark", "Marchio del Cacciatore", HM)])
async def test_a_mark_confirmed_on_a_spell_attack_adds_its_die_to_the_spell_damage(client, edition, srd, name, key):
    cid, spell = await _caster(client, name, srd, 1, edition=edition)
    blast = await _blast(client, cid)
    await _cast(client, cid, spell, **({"choices": {"ability": "wisdom"}} if srd == "hex" else {}))
    assert key in await _roll_keys(client, cid, "attack", spell_id=blast)
    attack = await _spell_attack(client, cid, blast, options=[key])
    carried = attack["option_result"]["extra_rolls"]
    assert len(carried) == 1 and 1 <= carried[0] <= 6
    damage = await _roll_damage(client, cid, blast)
    assert damage["total"] == sum(damage["main_rolls"]) + carried[0]
    assert damage["option_result"]["extra_rolls"] == carried and damage["option_result"]["keys"] == [key]
    assert len(damage["reroll_dice"]) == 2 and damage["reroll_dice"][1] == [6, carried[0]]
    again = await _roll_damage(client, cid, blast)  # il dado vale per un solo tiro di danno
    assert again["total"] == sum(again["main_rolls"]) and again.get("option_result") is None


async def test_the_die_of_a_mark_on_a_critical_spell_attack_doubles(client):
    cid, spell = await _caster(client, "Sortilegio", "hex", 1)
    blast = await _blast(client, cid)
    await _cast(client, cid, spell, choices={"ability": "wisdom"})
    attack = await _spell_attack(client, cid, blast, die=20, options=[HEX])
    assert len(attack["option_result"]["extra_rolls"]) == 2
    damage = await _roll_damage(client, cid, blast, is_critical=True)
    assert damage["total"] == sum(damage["main_rolls"]) + sum(attack["option_result"]["extra_rolls"])


async def test_the_die_confirmed_for_one_spell_attack_is_not_paid_out_by_another_spells_damage(client):
    cid, spell = await _caster(client, "Sortilegio", "hex", 1)
    blast = await _blast(client, cid)
    other = await client.post(f"/characters/{cid}/spells", json={**BLAST, "name": "Raggio di Gelo", "srd_index": "ray-of-frost", "level": 0})
    await _cast(client, cid, spell, choices={"ability": "wisdom"})
    await _spell_attack(client, cid, blast, options=[HEX])
    damage = await _roll_damage(client, cid, other.json()["id"])
    assert damage["total"] == sum(damage["main_rolls"])


async def test_the_weapon_only_options_are_not_offered_on_a_spell_attack(client):
    cid, spell = await _caster(client, "Marchio del Cacciatore", "hunters-mark", 1)  # 2014: «ogni attacco con arma»
    blast = await _blast(client, cid)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell)
    assert HM not in await _roll_keys(client, cid, "attack", spell_id=blast) and HM in await _roll_keys(client, cid, "attack", item_id=wid)
    cid, spell = await _caster(client, "Colpo Accurato", "true-strike", 0, edition="2024")
    blast = await _blast(client, cid)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell, level=0)
    key = "spell:true_strike:damage"
    assert key not in await _roll_keys(client, cid, "attack", spell_id=blast) and key in await _roll_keys(client, cid, "attack", item_id=wid)


# I-2: la concentrazione di ogni voce segue la colonna del manuale (2014/spells.md e 2024/spells.md)
CONCENTRATION = {
    "2014": {"hex": True, "hunters-mark": True, "blinding-smite": True, "branding-smite": True, "searing-smite": True, "wrathful-smite": True,
             "thunderous-smite": True, "staggering-smite": True, "banishing-smite": True, "ensnaring-strike": True, "hail-of-thorns": True,
             "lightning-arrow": True, "true-strike": True},
    "2024": {"hex": True, "hunters-mark": True, "blinding-smite": False, "searing-smite": False, "shining-smite": True, "wrathful-smite": True,
             "thunderous-smite": False, "staggering-smite": False, "banishing-smite": True, "ensnaring-strike": True, "hail-of-thorns": False,
             "lightning-arrow": False, "true-strike": False},
}


@pytest.mark.parametrize("edition,srd,expected", [(e, s, c) for e, row in CONCENTRATION.items() for s, c in row.items()])
def test_the_concentration_of_every_entry_follows_the_manual_column(edition, srd, expected):
    assert spell_effect(edition, srd)[1].concentration is expected


# I-3: i dadi extra portano il loro tipo
async def test_the_extra_dice_of_a_mark_and_of_a_smite_carry_their_damage_type(client):
    cid, spell = await _caster(client, "Sortilegio", "hex", 1)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell, choices={"ability": "wisdom"})
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "confirm_extra_attack": True, "options": [HEX]})
    assert r.json()["option_result"]["extra_types"] == ["necrotic"]
    cid, spell = await _caster(client, "Punizione Collerica", "wrathful-smite", 1)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell)
    block = (await _confirm(client, cid, wid, WRATHFUL)).json()["option_result"]
    assert block["extra_types"] == ["psychic"]


async def test_the_type_of_the_mark_die_reaches_the_spell_damage_result(client):
    cid, spell = await _caster(client, "Sortilegio", "hex", 1)
    blast = await _blast(client, cid)
    await _cast(client, cid, spell, choices={"ability": "wisdom"})
    await _spell_attack(client, cid, blast, options=[HEX])
    assert (await _roll_damage(client, cid, blast))["option_result"]["extra_types"] == ["necrotic"]


def test_divine_smite_and_the_rangers_mark_declare_their_type_without_changing_their_dice():
    from core.rules.catalog.y2014 import paladin as p14
    from core.rules.catalog.y2024 import paladin as p24, ranger as r24
    for spec in (p14.DIVINE_SMITE, p14.DIVINE_SMITE_FIEND, p14.IMPROVED_SMITE, p24.DIVINE_SMITE, p24.DIVINE_SMITE_FREE,
                 p24.DIVINE_SMITE_FIEND, p24.DIVINE_SMITE_FIEND_FREE, p24.RADIANT_STRIKES):
        assert spec.extra_damage_type == "radiant", spec.key
    assert r24.MARK_DAMAGE.extra_damage_type == "force"


# I-4: ogni voce del catalogo ha il nome nelle note del tiro (it/en)
def test_every_catalog_spell_has_its_roll_note_name_in_both_locales():
    import json
    from pathlib import Path
    from core.rules.catalog.spells import SPELL_EFFECTS
    for lang in ("it", "en"):
        names = json.loads(Path(f"webapp/src/locales/{lang}.json").read_text(encoding="utf-8"))["character"]["roll_notes"]["spell"]
        assert [k for k in SPELL_EFFECTS if not names.get(k)] == [], lang


# M-1: le etichette delle punizioni nominano l'incantesimo
def test_every_smite_label_names_its_spell():
    from core.rules.catalog.spells import marks
    for effect in marks.SPELLS:
        for edition, variant in effect.variants.items():
            for option in variant.options:
                if option.key.endswith(":hit") or option.key.endswith(":miss"):
                    for lang in ("it", "en"):
                        assert any(option.label[lang].startswith(f"{n}:") for n in effect.names), (effect.key, edition, lang, option.label[lang])


# M-4: la durata dei marchi segue lo slot
@pytest.mark.parametrize("edition,srd,slot,hours", [("2014", "hex", 1, 1), ("2014", "hex", 3, 8), ("2014", "hex", 5, 24),
                                                    ("2024", "hex", 2, 4), ("2024", "hex", 4, 8), ("2024", "hex", 6, 24),
                                                    ("2014", "hunters-mark", 2, 1), ("2014", "hunters-mark", 4, 8), ("2024", "hunters-mark", 5, 24)])
def test_the_duration_of_a_mark_follows_the_slot(edition, srd, slot, hours):
    assert spell_effect(edition, srd)[1].duration(slot) == hours * 600


async def test_the_clock_of_a_mark_cast_with_a_high_slot_lasts_longer(client):
    cid, spell = await _caster(client, "Sortilegio", "hex", 1, slots=2)
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 1})
    await _cast(client, cid, spell, level=3, choices={"ability": "wisdom"})
    states = await _states(client, cid)
    assert states["spell_cast:hex"]["rounds_left"] == 4800 and states["spell:hex"]["data"]["duration"]["rounds"] == 4800


# M-5: Freccia Folgorante mancata: la metà del danno
async def test_lightning_arrow_on_a_miss_deals_half_and_closes_the_spell(client):
    cid, spell = await _caster(client, "Freccia Folgorante", "lightning-arrow", 3)
    bow = await _sword(client, cid, weapon_type="ranged")
    await _cast(client, cid, spell, level=3)
    key = "spell:lightning_arrow:miss"
    first = await client.post(f"/characters/{cid}/items/{bow}/attack", json={"die": 5, "defer_damage": True, "confirm_extra_attack": True})
    assert first.status_code == 200, first.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [key]})
    assert r.status_code == 200, r.text
    assert r.json()["attack"]["grazed"] is True and 2 <= r.json()["attack"]["damage_total"] <= 16
    assert "spell:lightning_arrow" not in await _states(client, cid)
    assert (await _full(client, cid))["concentrating_spell_id"] is None


# M-7: il TS ripetuto toglie l'effetto al bersaglio, non chiude l'incantesimo: lo dice il testo
@pytest.mark.parametrize("edition,srd,name,level,conc", [("2024", "wrathful-smite", "Punizione Collerica", 1, True),
                                                         ("2024", "blinding-smite", "Colpo Accecante", 3, False),
                                                         ("2014", "blinding-smite", "Punizione Accecante", 3, True)])
async def test_the_text_says_a_passed_repeated_save_frees_only_the_target(client, edition, srd, name, level, conc):
    cid, spell = await _caster(client, name, srd, level, edition=edition, concentration=conc)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell, level=level)
    block = (await _confirm(client, cid, wid, f"spell:{srd.replace('-', '_')}:hit")).json()["option_result"]
    assert "l'incantesimo resta" in block["effects"][0]["it"] and "the spell stays" in block["effects"][0]["en"]


# M-8: senza concentrazione
async def test_a_2024_smite_without_concentration_lasts_after_the_hit_and_never_holds_the_concentration(client):
    cid, spell = await _caster(client, "Colpo Accecante", "blinding-smite", 3, edition="2024", concentration=False)
    wid = await _sword(client, cid)
    await _cast(client, cid, spell, level=3)
    assert (await _full(client, cid))["concentrating_spell_id"] is None
    assert (await _states(client, cid))["spell_cast:blinding_smite"]["rounds_left"] == 10
    r = await _confirm(client, cid, wid, "spell:blinding_smite:hit")
    assert r.status_code == 200 and len(r.json()["option_result"]["extra_rolls"]) == 3
    assert "spell:blinding_smite" in await _states(client, cid)
    assert (await _full(client, cid))["concentrating_spell_id"] is None
