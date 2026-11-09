"""«Usa» acceso a 0 usi lo decide il server (Task 31, I4): vale solo se l'uso non costa nulla e si può fare ora."""
from __future__ import annotations

from tests.integration.rules import test_2014_barbarian as old
from tests.integration.rules import test_2024_barbarian as new

RAGE = "barbarian.rage"


async def _spend_all_and_rage(client, cid, module) -> dict:
    assert (await module._rage(client, cid)).status_code == 200
    row = await old._ability(client, cid, RAGE)
    assert (await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 0})).status_code == 200
    return await old._ability(client, cid, RAGE)


async def test_a_2014_rage_at_zero_uses_is_not_a_free_use(client):
    row = await _spend_all_and_rage(client, await old._barbarian(client, 5), old)
    assert row["uses"] == 0 and row["free_use"] is False  # il «Usa» resterebbe un rifiuto


async def test_a_2024_rage_that_can_still_be_extended_is_a_free_use_at_zero_uses(client):
    row = await _spend_all_and_rage(client, await new._barbarian(client, 14, "Cammino del Berserker"), new)
    assert row["uses"] == 0 and row["free_use"] is True  # prolungare non costa un uso


async def test_from_level_15_there_is_nothing_to_extend_so_it_is_not_a_free_use(client):
    row = await _spend_all_and_rage(client, await new._barbarian(client, 15, "Cammino del Berserker"), new)
    assert row["free_use"] is False


async def test_an_ordinary_ability_is_never_a_free_use(client):
    cid = await new._barbarian(client, 14, "Cammino del Berserker")
    assert (await old._ability(client, cid, RAGE))["free_use"] is False  # nessuna Ira in corso: costa un uso
