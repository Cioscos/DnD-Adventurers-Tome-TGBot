"""Stili di Combattimento presi come talento 2024: gli effetti dello stile del Guerriero (PR 2 talenti, Task 4)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_barbarian import _armor, _weapon
from tests.integration.rules.test_feats_2024_general import STATS
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _feat_rows, _take


async def _attack_total(client, cid, wid) -> int:
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    return r.json()["to_hit_total"]


async def test_archery_feat_on_a_paladin(client):
    plain = await _char(client, "paladin", 4, **STATS)
    feat = await _char(client, "paladin", 4, **STATS)
    assert (await _take(client, feat["id"], "2024_fs_archery")).status_code == 201
    totals = []
    for ch in (plain, feat):
        wid = await _weapon(client, ch["id"], "Arco lungo", damage_dice="1d8", weapon_type="ranged")
        totals.append(await _attack_total(client, ch["id"], wid))
    assert totals[1] == totals[0] + 2


async def test_defense_feat_on_a_ranger(client):
    plain = await _char(client, "ranger", 4, **STATS)
    feat = await _char(client, "ranger", 4, **STATS)
    assert (await _take(client, feat["id"], "2024_fs_defense")).status_code == 201
    for ch in (plain, feat):
        await _armor(client, ch["id"], "light", 11)
    assert (await _full(client, feat["id"]))["ac"] == (await _full(client, plain["id"]))["ac"] + 1


async def test_interception_feat_is_a_reaction(client):
    ch = await _char(client, "fighter", 4, **STATS)
    r = await _take(client, ch["id"], "2024_fs_interception")
    assert r.status_code == 201, r.text
    row = _feat_rows(r.json(), "2024_fs_interception")[0]
    assert row["action_type"] == "reaction" and row["has_on_use"] and row["name"] == "Intercettazione"
