"""Audit TRB: Ladro di Incantesimi 2024 (PHB 2024 p.133): l'uso si consuma solo se il furto riesce.

A differenza del 2014 (un uso per ogni tentativo), il 2024 dice che dopo aver rubato un incantesimo non si può rifare fino al
riposo lungo: un TS superato dal lanciatore non spende l'uso."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _ability, _use
from tests.integration.rules.test_2024_rogue_subclasses import _k, _sub


async def test_spell_thief_2024_failed_attempt_keeps_the_use(client):
    cid = await _sub(client, "arcane_trickster", 17, intelligence=16)
    r = await _use(client, cid, _k("spell_thief"), params={"stolen": False})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, _k("spell_thief")))["uses"] == 1


async def test_spell_thief_2024_successful_theft_spends_the_use(client):
    cid = await _sub(client, "arcane_trickster", 17, intelligence=16)
    r = await _use(client, cid, _k("spell_thief"), params={"stolen": True, "spell_level": "1", "spell": "Dardo Incantato"})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, _k("spell_thief")))["uses"] == 0
