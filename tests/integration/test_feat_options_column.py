"""Le scelte di un talento stanno sulla sua riga (`Ability.options`) e passano da export e import."""
from __future__ import annotations

from core.db.models import Ability


async def test_feat_options_are_read_and_survive_export(client, test_session_factory):
    r = await client.post("/characters", json={"name": "Talentuosa"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    async with test_session_factory() as s:
        s.add(Ability(character_id=cid, name="Atleta", is_passive=True, feature_key="feat.athlete",
                      options={"ability": "dexterity"}))
        await s.commit()

    abilities = (await client.get(f"/characters/{cid}")).json()["abilities"]
    row = next(a for a in abilities if a["feature_key"] == "feat.athlete")
    assert row["options"] == {"ability": "dexterity"}

    exported = (await client.get(f"/characters/{cid}/export")).json()
    r = await client.post("/characters/import", json=exported)
    assert r.status_code in (200, 201), r.text
    copy = next(a for a in r.json()["abilities"] if a["feature_key"] == "feat.athlete")
    assert copy["options"] == {"ability": "dexterity"}
