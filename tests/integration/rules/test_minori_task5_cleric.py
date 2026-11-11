"""Minori rinviati, Task 5 (punto 22): Chierico."""
from __future__ import annotations

from tests.integration.rules.test_2024_cleric_domains import _dom, _spell_rows


async def test_cleric_22_spiritual_weapon_needs_concentration_only_in_2024(client):
    war24 = await _dom(client, 5, "war")
    assert (await _spell_rows(client, war24))["spiritual-weapon"]["is_concentration"] is True
    r = await client.post("/characters", json={"name": "Vecchio", "initial_class": {
        "class_name": "cleric", "level": 5, "subclass": "Dominio della Vita"}})
    life14 = r.json()["id"]
    assert (await client.patch(f"/characters/{life14}", json={"rules_edition": "2014"})).status_code == 200
    # Vita 2014 ha Arma Spirituale fra gli incantesimi di dominio: senza Concentrazione
    assert (await _spell_rows(client, life14))["spiritual-weapon"]["is_concentration"] is False
    # il passaggio di edizione aggiorna la riga creata dal privilegio
    assert (await client.patch(f"/characters/{life14}", json={"rules_edition": "2024"})).status_code == 200
    assert (await _spell_rows(client, war24))["spiritual-weapon"]["is_concentration"] is True


async def test_cleric_22_switching_to_2024_drops_the_2014_domain_proficiencies(client):
    r = await client.post("/characters", json={"name": "Guerra", "initial_class": {
        "class_name": "cleric", "level": 3, "subclass": "Dominio della Guerra"}})
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    got = (await client.get(f"/characters/{cid}")).json()["general_proficiencies"]
    assert "Armature pesanti" in got["armor"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    got = (await client.get(f"/characters/{cid}")).json()["general_proficiencies"]
    assert "Armature pesanti" not in got["armor"]
    assert "Armi da guerra" not in got["weapons"]
    # le armature del Chierico base restano
    assert "Armature medie" in got["armor"]
