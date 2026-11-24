"""Controlli scritti dai correttori del gruppo pf-personaggio per i dubbi «Q-…» risolti come difetti."""
import pytest


async def _pg(client, classe, livello, edizione="2014") -> int:
    r = await client.post("/characters", json={"name": "P", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _pf(client, cid, pf) -> None:
    for op in ("set_max", "set_current"):
        r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": pf})
        assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-4311", fonte="2014 · Ladro · Schivata Prodigiosa / Uncanny Dodge · pag. 78 (dimezza i danni di quell'attacco: un solo arrotondamento)",
                    zona="regola:2014/rogue", voce="regola",
                    copre=["carta:2014/classes/rogue.md#Schivata Prodigiosa / Uncanny Dodge (Ladro 5, pag. 78)",
                           "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("principale,extra,danno", [
    (7, [7], 7),            # 7 taglienti + 7 fuoco: metà di 14
    (9, [7], 8),            # Lingua di Fuoco 1d8+3 + 2d6: metà di 16
    (5, [3, 3, 3], 7),      # quattro tipi, totale 14
])
async def test_schivata_prodigiosa_dimezza_il_totale_di_un_attacco_con_piu_tipi_di_danno(client, principale, extra, danno):
    cid = await _pg(client, "rogue", 5)
    await _pf(client, cid, 60)
    tipi = ["fire", "cold", "acid"]
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": principale, "damage_type": "slashing", "options": ["rogue.uncanny_dodge"],
        "extra_damage": [{"amount": a, "damage_type": tipi[i]} for i, a in enumerate(extra)]})
    assert r.status_code == 200, r.text
    # nessuna resistenza: dividere lo stesso colpo in più tipi non cambia la metà
    assert r.json()["current_hit_points"] == 60 - danno
