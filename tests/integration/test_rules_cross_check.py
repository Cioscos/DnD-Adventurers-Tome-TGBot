"""Task 43: Review Focus 4 e 5 col catalogo vero (nessun `rules_catalog`), via API."""
from __future__ import annotations


async def _make(client, class_name, level, edition="2014", subclass=None) -> tuple[int, dict]:
    r = await client.post("/characters", json={"name": "Prova", "initial_class": {"class_name": class_name, "level": level, "subclass": subclass}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    if edition != "2014":
        r = await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
        assert r.status_code == 200, r.text
    return cid, (await client.get(f"/characters/{cid}")).json()


def _class_rows(body: dict) -> dict[str, tuple]:
    return {a["feature_key"]: (a["max_uses"], a["restoration_type"]) for a in body["abilities"] if a["feature_key"]}


async def test_mixed_class_names_give_the_same_privileges_and_a_custom_class_is_harmless(client):
    seen = [_class_rows((await _make(client, name, 5))[1]) for name in ("Mago", "wizard", "Wizard")]
    assert seen[0] and seen[0] == seen[1] == seen[2]
    _cid, custom = await _make(client, "Pasticcere Errante", 5)
    assert not [a for a in custom["abilities"] if a["feature_key"]]


async def test_edition_round_trip_with_the_real_catalog_loses_nothing(client):
    cid, body = await _make(client, "fighter", 3, subclass="Campione")
    key = next(k for k, (mx, _r) in _class_rows(body).items() if mx and k.startswith("fighter."))
    row = next(a for a in body["abilities"] if a["feature_key"] == key)
    assert (await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": row["max_uses"] - 1, "description": "mia"})).status_code == 200
    mid = (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).json()
    assert mid["classes"][0]["subclass"] == "Campione"  # resta testo anche se il nome differisce
    back = (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).json()
    again = next(a for a in back["abilities"] if a["feature_key"] == key)
    assert (again["max_uses"], again["uses"], again["description"]) == (row["max_uses"], row["max_uses"] - 1, "mia")
    assert back["classes"][0]["subclass"] == "Campione" and back["classes"][0]["subclass_key"] == "champion"
    assert back["ac_breakdown"] == body["ac_breakdown"]
