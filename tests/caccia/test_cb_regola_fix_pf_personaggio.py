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


@pytest.mark.caccia(id="CB-4312", fonte="2014 · Druido · Forma Selvatica · pag. 66; Concentrazione · pag. 203 (CD: 10 o metà del danno subito, un TS per fonte)",
                    zona="regola:2014/druid", voce="interazione",
                    copre=["carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)",
                           "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/companions/{companion_id}/activate"])
async def test_la_cd_di_concentrazione_usa_il_colpo_intero_quando_la_forma_selvatica_cede(client, dadi):
    cid = await _pg(client, "druid", 4)
    await _pf(client, cid, 40)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Intralciare", "level": 1, "is_concentration": True})
    assert r.status_code == 201, r.text
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": r.json()["id"]})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Lupo", "max_hp": 10, "armor_class": 13,
        "statblock": {"size": "Medium", "type": "beast", "challenge_rating": 0.25, "actions": []}})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/companions/{r.json()['id']}/activate", json={"force": True})
    assert r.status_code == 200, r.text
    dadi(20)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 30})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 20  # la forma prende 10, l'eccesso di 20 passa al druido
    # un solo colpo subito dalla stessa creatura: CD metà di 30, non dell'eccesso
    assert r.json()["concentration_save"]["dc"] == 15


@pytest.mark.caccia(id="CB-4313", fonte="2024 · Mago · Recupero Arcano · pag. 166; Glossario · Riposo Lungo, interrotto dopo almeno un'ora: benefici di un Riposo Breve · pag. 370-371",
                    zona="regola:2024/wizard", voce="interazione",
                    copre=["carta:2024/classes/wizard.md#Recupero Arcano / Arcane Recovery (Mago 1, pag. 166)",
                           "POST /characters/{char_id}/rest"])
async def test_recupero_arcano_vale_nel_riposo_lungo_2024_interrotto(client):
    cid = await _pg(client, "wizard", 5, "2024")
    slot = next(s for s in (await client.get(f"/characters/{cid}")).json()["spell_slots"] if s["level"] == 1)
    r = await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 2})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "interrupted": True, "arcane_recovery": {"1": 2}})
    # il lungo interrotto dopo almeno un'ora vale un riposo breve: il Recupero Arcano si fa
    assert r.status_code == 200, r.text
    assert next(s for s in r.json()["spell_slots"] if s["level"] == 1)["used"] == 0
