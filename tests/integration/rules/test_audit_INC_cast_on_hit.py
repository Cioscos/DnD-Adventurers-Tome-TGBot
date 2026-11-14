"""Audit incantesimi: le tre punizioni del Ranger 2024 si lanciano DOPO il colpo (azione bonus), non prima.
Colpo Intrappolante p.268 e Grandine di Spine p.283 «subito dopo aver colpito con arma»; Freccia Fulminea p.292 «subito dopo aver colpito o mancato»."""
from __future__ import annotations

from tests.integration.rules.test_2014_fighter_eldritch_knight import _sword
from tests.integration.rules.test_2014_paladin_combat import _damage, _deferred, _listed
from tests.integration.rules.test_spell_effects_marks import _caster, _full, _slots24

ENSNARE, HAIL = "spell:ensnaring_strike:hit", "spell:hail_of_thorns:hit"
ARROW, ARROW_MISS = "spell:lightning_arrow:hit", "spell:lightning_arrow:miss"


async def _with_slots(client, name, srd, level, edition):
    cid, spell = await _caster(client, name, srd, level, edition=edition, concentration=srd == "ensnaring-strike", slots=2)
    await client.post(f"/characters/{cid}/spell_slots", json={"level": level + 1, "total": 1})
    return cid


async def _keys(client, cid, item):
    return [o["key"] for o in await _listed(client, cid, item)]


async def test_ensnaring_strike_2024_p268_is_offered_after_a_weapon_hit_without_casting_first(client):
    cid = await _with_slots(client, "Colpo Intrappolante", "ensnaring-strike", 1, "2024")
    melee, bow = await _sword(client, cid), await _sword(client, cid, weapon_type="ranged")
    assert ENSNARE in await _keys(client, cid, melee) and ENSNARE in await _keys(client, cid, bow)
    before = await _slots24(client, cid)
    r = await _damage(client, cid, await _deferred(client, cid, melee), [ENSNARE], **{ENSNARE: {"slot_level": 2}})
    assert r.status_code == 200, r.text
    assert (await _slots24(client, cid))[2] == before[2] - 1
    assert (await _full(client, cid))["concentrating_spell_id"] is not None  # il 2024 resta a concentrazione


async def test_ensnaring_strike_2014_p222_still_needs_the_cast_first(client):
    cid = await _with_slots(client, "Colpo Intrappolante", "ensnaring-strike", 1, "2014")
    assert ENSNARE not in await _keys(client, cid, await _sword(client, cid))


async def test_hail_of_thorns_2024_p283_is_offered_after_a_ranged_hit_only(client):
    cid = await _with_slots(client, "Grandine di Spine", "hail-of-thorns", 1, "2024")
    melee, bow = await _sword(client, cid), await _sword(client, cid, weapon_type="ranged")
    assert HAIL not in await _keys(client, cid, melee) and HAIL in await _keys(client, cid, bow)
    before = await _slots24(client, cid)
    r = await _damage(client, cid, await _deferred(client, cid, bow), [HAIL], **{HAIL: {"slot_level": 2}})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["separate_rolls"]) == 2 and (await _slots24(client, cid))[2] == before[2] - 1
    assert (await _full(client, cid))["concentrating_spell_id"] is None


async def test_lightning_arrow_2024_p292_is_offered_after_a_ranged_hit_without_casting_first(client):
    cid = await _with_slots(client, "Freccia Fulminea", "lightning-arrow", 3, "2024")
    melee, bow = await _sword(client, cid), await _sword(client, cid, weapon_type="ranged")
    assert ARROW not in await _keys(client, cid, melee) and ARROW in await _keys(client, cid, bow)
    before = await _slots24(client, cid)
    r = await _damage(client, cid, await _deferred(client, cid, bow), [ARROW], **{ARROW: {"slot_level": 4}})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["separate_rolls"]) == 5 and (await _slots24(client, cid))[4] == before[4] - 1  # 4d8 + 1d8 allo slot 4
