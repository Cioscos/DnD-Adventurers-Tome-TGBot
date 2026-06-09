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
