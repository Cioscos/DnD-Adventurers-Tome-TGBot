"""Audit TRB: Esperto di abilità 2024 (PHB 2024 p.207): la Maestria va in un'abilità in cui non se ne ha già una."""
from __future__ import annotations

from tests.integration.rules.test_feats_2024_choices import _row
from tests.integration.rules.test_feats_2024_general import STATS
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _complete


async def test_skill_expert_refuses_expertise_in_already_expert_skill(client):
    ch = await _char(client, "fighter", 4, **STATS)
    await client.patch(f"/characters/{ch['id']}/skills", json={"skills": {"stealth": "expert"}})
    row = await _row(client, ch["id"], "skill_expert", "strength")
    r = await _complete(client, ch["id"], row["id"], {"skill": "athletics", "expertise": "stealth"})
    assert r.status_code == 422, r.text
