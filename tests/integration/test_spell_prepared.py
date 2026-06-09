"""Incantesimi preparati: blocco ``spellcasting`` in CharacterFull e
validazione del tetto su PATCH/POST /spells.

Regole pinnate (spec 2026-06-10):
- has_preparing_class auto-rilevato dalla classe (Chierico/Druido/Paladino lv2+/Mago).
- prepared_cap auto = somma per classe di max(1, mod + livello [o // 2 Paladino]).
- Override manuale via settings.prepared_cap_mode / prepared_cap_value.
- PATCH is_prepared=true oltre il tetto -> 400; spreparare sempre permesso.
- I trucchetti (level 0) non contano e non sono validati.
- Known caster (Bardo): has_preparing_class False, nessuna validazione.
"""
from __future__ import annotations


async def _cleric(client, level: int = 4) -> int:
    """Chierico SAG 10 (mod 0) -> cap auto = level."""
    r = await client.post(
        "/characters",
        json={"name": "Prep", "initial_class": {
            "class_name": "Chierico", "level": level, "hit_die": 8,
            "spellcasting_ability": "wisdom",
        }},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _bard(client) -> int:
    r = await client.post(
        "/characters",
        json={"name": "Known", "initial_class": {
            "class_name": "Bardo", "level": 5, "hit_die": 8,
            "spellcasting_ability": "charisma",
        }},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_spell(client, cid: int, *, name: str, level: int = 1,
                     is_prepared: bool = False, is_ritual: bool = False) -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": name, "level": level,
              "is_prepared": is_prepared, "is_ritual": is_ritual},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _get(client, cid: int) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def test_cleric_spellcasting_block(client):
    cid = await _cleric(client, level=4)
    sc = (await _get(client, cid))["spellcasting"]
    assert sc["has_preparing_class"] is True
    assert sc["prepared_cap"] == 4          # SAG mod 0 + livello 4
    assert sc["prepared_count"] == 0
    assert sc["cap_mode"] == "auto"
    assert sc["has_ritual_caster"] is True  # il Chierico ha Ritual Casting
    assert sc["has_wizard"] is False


async def test_bard_has_no_preparing_class(client):
    cid = await _bard(client)
    sc = (await _get(client, cid))["spellcasting"]
    assert sc["has_preparing_class"] is False
    assert sc["prepared_cap"] is None
    assert sc["has_ritual_caster"] is True


async def test_new_spell_defaults_to_unprepared(client):
    cid = await _cleric(client)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Cura", "level": 1})
    assert r.status_code == 201, r.text
    assert r.json()["is_prepared"] is False


async def test_prepared_count_ignores_cantrips(client):
    cid = await _cleric(client)
    await _add_spell(client, cid, name="Luce", level=0, is_prepared=True)
    await _add_spell(client, cid, name="Cura", level=1, is_prepared=True)
    sc = (await _get(client, cid))["spellcasting"]
    assert sc["prepared_count"] == 1


async def test_manual_cap_override(client):
    cid = await _cleric(client, level=4)
    r = await client.patch(f"/characters/{cid}", json={
        "settings": {"prepared_cap_mode": "manual", "prepared_cap_value": 10},
    })
    assert r.status_code == 200, r.text
    sc = (await _get(client, cid))["spellcasting"]
    assert sc["cap_mode"] == "manual"
    assert sc["prepared_cap"] == 10


async def _prepare(client, cid: int, spell_id: int, prepared: bool = True):
    return await client.patch(
        f"/characters/{cid}/spells/{spell_id}",
        json={"is_prepared": prepared},
    )


async def test_prepare_up_to_cap_then_400(client):
    cid = await _cleric(client, level=2)  # cap = 2
    ids = [await _add_spell(client, cid, name=f"S{i}", level=1) for i in range(3)]

    assert (await _prepare(client, cid, ids[0])).status_code == 200
    assert (await _prepare(client, cid, ids[1])).status_code == 200
    r = await _prepare(client, cid, ids[2])
    assert r.status_code == 400, r.text
    assert "cap" in r.json()["detail"].lower()


async def test_unprepare_always_allowed_even_over_cap(client):
    cid = await _cleric(client, level=2)  # cap auto = 2
    # Porta il PG oltre il tetto abbassando il cap manuale sotto il conteggio.
    ids = [await _add_spell(client, cid, name=f"S{i}", level=1) for i in range(2)]
    for sid in ids:
        assert (await _prepare(client, cid, sid)).status_code == 200
    r = await client.patch(f"/characters/{cid}", json={
        "settings": {"prepared_cap_mode": "manual", "prepared_cap_value": 1},
    })
    assert r.status_code == 200, r.text
    # Over-cap (2/1): spreparare è permesso, preparare no.
    assert (await _prepare(client, cid, ids[0], prepared=False)).status_code == 200
    sc = (await _get(client, cid))["spellcasting"]
    assert sc["prepared_count"] == 1 and sc["prepared_cap"] == 1


async def test_post_with_is_prepared_at_cap_is_400(client):
    cid = await _cleric(client, level=1)  # cap = 1
    sid = await _add_spell(client, cid, name="Uno", level=1)
    assert (await _prepare(client, cid, sid)).status_code == 200
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Due", "level": 1, "is_prepared": True},
    )
    assert r.status_code == 400, r.text


async def test_cantrip_toggle_skips_validation(client):
    cid = await _cleric(client, level=1)  # cap = 1, già pieno
    sid = await _add_spell(client, cid, name="Pieno", level=1)
    assert (await _prepare(client, cid, sid)).status_code == 200
    cantrip = await _add_spell(client, cid, name="Luce", level=0)
    assert (await _prepare(client, cid, cantrip)).status_code == 200


async def test_known_caster_toggle_has_no_cap(client):
    cid = await _bard(client)
    ids = [await _add_spell(client, cid, name=f"B{i}", level=1) for i in range(30)]
    for sid in ids:
        assert (await _prepare(client, cid, sid)).status_code == 200
