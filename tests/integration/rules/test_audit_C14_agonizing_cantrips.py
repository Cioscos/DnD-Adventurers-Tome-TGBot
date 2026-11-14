"""Audit C14-I: Deflagrazione Agonizzante 2024 (Warlock, p.155): +mod. CAR ai tiri per i danni di un trucchetto idoneo.
Solo Deflagrazione Occulta tira un danno per raggio; un altro trucchetto (Tocco Gelido) ha un solo tiro: il bonus si somma una volta."""
from __future__ import annotations

from tests.integration.rules.test_2024_warlock import _caster24, _cantrip, _damage


async def test_agonizing_blast_on_another_cantrip_adds_charisma_once_p155(client):
    cid = await _caster24(client, 5, "agonizing_blast__chill_touch", cantrips=["chill-touch"], charisma=18)
    chill = await _cantrip(client, cid, "chill-touch")
    # 5° livello: 2 dadi del trucchetto in un solo tiro di danno; CAR 18 = +4 una volta
    assert (await _damage(client, cid, chill, main_rolls=[4, 4]))["total"] == 8 + 4
