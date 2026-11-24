"""Controlli della zona regola:2014/cleric."""
import pytest

DOMINI = {
    "knowledge": "Dominio della Conoscenza", "war": "Dominio della Guerra", "trickery": "Dominio dell'Inganno",
    "light": "Dominio della Luce", "nature": "Dominio della Natura", "tempest": "Dominio della Tempesta",
    "life": "Dominio della Vita",
}
RISERVA = "cleric.channel_divinity"


async def _chierico(client, livello, dominio=None, **punteggi) -> int:
    r = await client.post("/characters", json={"name": "Chierico", "rules_edition": "2014", "initial_class": {
        "class_name": "cleric", "level": livello, "subclass": DOMINI.get(dominio)}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _classe(client, cid, nome, livello, dado, sottoclasse=None) -> None:
    r = await client.post(f"/characters/{cid}/classes", json={
        "class_name": nome, "level": livello, "hit_die": dado, "subclass": sottoclasse})
    assert r.status_code == 201, r.text


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _riga(client, cid, chiave) -> dict | None:
    return next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == chiave), None)


async def _usa(client, cid, chiave, **parametri):
    return await client.post(f"/characters/{cid}/features/{chiave}/use", json={"params": parametri})


async def _arma(client, cid) -> int:
    meta = {"damage_dice": "1d6", "damage_type": "bludgeoning", "weapon_type": "melee", "properties": []}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Mazza", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == "Mazza")
    r = await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    return wid


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1661", fonte="2014 · Chierico · Avatar della Battaglia · pag. 61", zona="regola:2014/cleric",
                    voce="interazione",
                    copre=["carta:2014/classes/cleric.md#Avatar della Battaglia / Avatar of Battle (Guerra 17, pag. 61)",
                           "PATCH /characters/{char_id}/hp"])
@pytest.mark.xfail(strict=True, reason="CB-1661: difforme dal manuale, confermato")
async def test_avatar_della_battaglia_non_si_somma_a_una_resistenza_gia_presente(client):
    cid = await _chierico(client, 17, "war")
    r = await client.patch(f"/characters/{cid}", json={"damage_modifiers": {"resistances": ["slashing"]}})
    assert r.status_code == 200, r.text
    prima = (await _scheda(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 20, "damage_type": "slashing", "options": ["cleric.avatar_of_battle"]})
    assert r.status_code == 200, r.text
    # resistenza: il danno si dimezza una volta sola, anche con due fonti
    assert (await _scheda(client, cid))["current_hit_points"] == prima - 10


@pytest.mark.caccia(id="CB-1662", fonte="2014 · Chierico · Mitigare Elementi · pag. 62", zona="regola:2014/cleric",
                    voce="interazione",
                    copre=["carta:2014/classes/cleric.md#Mitigare Elementi / Dampen Elements (Natura 6, pag. 62)",
                           "PATCH /characters/{char_id}/hp"])
@pytest.mark.xfail(strict=True, reason="CB-1662: difforme dal manuale, confermato")
async def test_mitigare_elementi_non_si_somma_a_una_resistenza_gia_presente(client):
    cid = await _chierico(client, 6, "nature")
    r = await client.patch(f"/characters/{cid}", json={"damage_modifiers": {"resistances": ["fire"]}})
    assert r.status_code == 200, r.text
    prima = (await _scheda(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 20, "damage_type": "fire", "options": ["cleric.dampen_elements"]})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["current_hit_points"] == prima - 10


@pytest.mark.caccia(id="CB-1663", fonte="2014 · Chierico · Incanalare Divinità: Conoscenze Secolari · pag. 60",
                    zona="regola:2014/cleric", voce="interazione",
                    copre=["carta:2014/classes/cleric.md#Incanalare Divinità: Conoscenze Secolari / Channel Divinity: Knowledge of the Ages (Conoscenza 2, pag. 60)",
                           "POST /characters/{char_id}/features/{feature_key}/use",
                           "POST /characters/{char_id}/skills/{skill_name}/roll"])
@pytest.mark.xfail(strict=True, reason="CB-1663: difforme dal manuale, confermato")
async def test_conoscenze_secolari_sostituisce_il_factotum_invece_di_sommarsi(client):
    r = await client.post("/characters", json={"name": "Bardo", "rules_edition": "2014",
                                               "initial_class": {"class_name": "bard", "level": 2}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    await _classe(client, cid, "cleric", 2, 8, "Dominio della Conoscenza")  # livello 4: competenza +2, Destrezza 10
    tiro = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})
    assert tiro.json()["total"] == 11  # Factotum: metà competenza senza competenza
    assert (await _usa(client, cid, "cleric.knowledge_of_the_ages", skill="stealth")).status_code == 200
    tiro = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})
    assert tiro.json()["total"] == 12  # ora competente: +2, il Factotum non vale più


@pytest.mark.caccia(id="CB-1664", fonte="2014 · Chierico · Colpo Divino (Vita, Inganno, Tempesta, Natura) · pag. 61-63",
                    zona="regola:2014/cleric", voce="regola",
                    copre=["carta:2014/classes/cleric.md#Colpo Divino / Divine Strike (Vita 8, pag. 63)",
                           "carta:2014/classes/cleric.md#Colpo Divino / Divine Strike (Inganno 8, pag. 61)",
                           "carta:2014/classes/cleric.md#Colpo Divino / Divine Strike (Tempesta 8, pag. 63)",
                           "carta:2014/classes/cleric.md#Colpo Divino / Divine Strike (Natura 8, pag. 62)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("dominio, opzione, tipo", [
    ("life", "cleric.divine_strike_life", "radiant"),
    ("trickery", "cleric.divine_strike_trickery", "poison"),
    ("tempest", "cleric.divine_strike_tempest", "thunder"),
    ("nature", "cleric.divine_strike_nature_cold", "cold"),
])
@pytest.mark.xfail(strict=True, reason="CB-1664: difforme dal manuale, confermato")
async def test_i_dadi_del_colpo_divino_hanno_il_tipo_del_dominio(client, dominio, opzione, tipo):
    cid = await _chierico(client, 8, dominio, strength=14)
    wid = await _arma(client, cid)
    attacco = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "defer_damage": True})).json()
    r = await client.post(f"/characters/{cid}/attack/{attacco['attack_id']}/damage", json={"options": [opzione]})
    assert r.status_code == 200, r.text
    esito = r.json()["option_result"]
    assert len(esito["extra_rolls"]) == 1
    assert esito["extra_types"] == [tipo]  # non contundente come la mazza


@pytest.mark.caccia(id="CB-1665", fonte="2014 · Chierico · Incanalare Divinità · pag. 59", zona="regola:2014/cleric",
                    voce="regola",
                    copre=["carta:2014/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 59)",
                           "carta:2014/classes/cleric.md#Incanalare Divinità: Scacciare Non Morti / Channel Divinity: Turn Undead (Chierico 2, pag. 59)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_la_cd_di_incanalare_divinita_e_quella_degli_incantesimi_del_chierico(client):
    cid = await _chierico(client, 2, wisdom=16)  # 8 + 2 + 3 = 13
    r = await client.post(f"/characters/{cid}/items", json={"name": "Amuleto", "item_type": "accessory",
                                                            "item_metadata": {"bonuses": [{"target": "spell_dc", "value": 1}]}})
    assert r.status_code == 201, r.text
    iid = next(i["id"] for i in r.json()["items"] if i["name"] == "Amuleto")
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "neck"})
    assert r.status_code == 200, r.text
    (cd_incantesimi,) = [c["save_dc"] for c in (await _scheda(client, cid))["spellcasting"]["casters"]]
    assert cd_incantesimi == 14
    r = await _usa(client, cid, "cleric.turn_undead")
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["dc"] == cd_incantesimi


@pytest.mark.caccia(id="CB-1671", fonte="2014 · Chierico · Guaritore Benedetto · pag. 63", zona="regola:2014/cleric",
                    voce="regola",
                    copre=["carta:2014/classes/cleric.md#Guaritore Benedetto / Blessed Healer (Vita 6, pag. 63)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.xfail(strict=True, reason="CB-1671: difforme dal manuale, confermato")
async def test_guaritore_benedetto_non_vale_se_l_unico_bersaglio_e_il_chierico(client, dadi):
    cid = await _chierico(client, 6, "life")  # Saggezza 10
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})).status_code == 200
    prima = (await _scheda(client, cid))["current_hit_points"]
    cura = next(s["id"] for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "cure-wounds")
    dadi(3)
    r = await client.post(f"/characters/{cid}/spells/{cura}/roll_healing", json={
        "casting_level": 1, "apply_to_self": True, "options": ["cleric.blessed_healer"]})
    # Cura ferite ha un solo bersaglio e qui è il chierico: niente PF in più per sé
    assert r.status_code != 200 or r.json()["self_healed"] == 0
    assert (await _scheda(client, cid))["current_hit_points"] in (prima, prima + 3 + 3)


# ---------------------------------------------------------------------------
# Regole che restano giuste
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1666", fonte="2014 · Chierico · Incanalare Divinità · pag. 59", zona="regola:2014/cleric",
                    voce="limiti",
                    copre=["carta:2014/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 59)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, usi", [(1, None), (2, 1), (5, 1), (6, 2), (17, 2), (18, 3), (20, 3)])
async def test_usi_di_incanalare_divinita_per_livello(client, livello, usi):
    riga = await _riga(client, await _chierico(client, livello), RISERVA)
    if usi is None:
        assert riga is None
    else:
        assert (riga["max_uses"], riga["restoration_type"]) == (usi, "short_rest")


@pytest.mark.caccia(id="CB-1672", fonte="2014 · Chierico · Lampo di Interdizione · pag. 62", zona="regola:2014/cleric",
                    voce="regola",
                    copre=["carta:2014/classes/cleric.md#Lampo di Interdizione / Warding Flare (Luce 1, pag. 62)",
                           "POST /characters/{char_id}/rest"])
async def test_lampo_di_interdizione_torna_solo_col_riposo_lungo(client):
    cid = await _chierico(client, 1, "light", wisdom=14)  # Saggezza +2: due usi
    assert (await _riga(client, cid, "cleric.warding_flare"))["max_uses"] == 2
    assert (await _usa(client, cid, "cleric.warding_flare")).status_code == 200
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _riga(client, cid, "cleric.warding_flare"))["uses"] == 1
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, "cleric.warding_flare"))["uses"] == 2


@pytest.mark.caccia(id="CB-1673", fonte="2014 · Chierico · Incanalare Divinità · pag. 59 / 2024 · Chierico · Incanalare Divinità · pag. 70",
                    zona="regola:2014/cleric", voce="edizioni",
                    copre=["carta:2014/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 59)",
                           "carta:2024/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 70)",
                           "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("edizione, usi, dopo_breve", [("2014", 2, 2), ("2024", 3, 1)])
async def test_incanalare_divinita_al_sesto_livello_per_edizione(client, edizione, usi, dopo_breve):
    r = await client.post("/characters", json={"name": "Chierico", "rules_edition": edizione,
                                               "initial_class": {"class_name": "cleric", "level": 6}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await _riga(client, cid, RISERVA))["max_uses"] == usi
    for _ in range(usi):
        assert (await _usa(client, cid, "cleric.turn_undead")).status_code == 200
        await client.post(f"/characters/{cid}/turn/new")
    assert (await _riga(client, cid, RISERVA))["uses"] == 0
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _riga(client, cid, RISERVA))["uses"] == dopo_breve


@pytest.mark.caccia(id="CB-1674", fonte="2014 · Chierico · Mitigare Elementi · pag. 62", zona="regola:2014/cleric",
                    voce="annullamento",
                    copre=["carta:2014/classes/cleric.md#Mitigare Elementi / Dampen Elements (Natura 6, pag. 62)",
                           "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_rende_la_reazione_di_mitigare_elementi(client):
    cid = await _chierico(client, 6, "nature")
    prima = (await _scheda(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 9, "damage_type": "fire", "options": ["cleric.dampen_elements"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == prima - 4
    annullo = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})
    assert annullo.status_code == 200, annullo.text
    assert annullo.json()["current_hit_points"] == prima
    turno = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turno["reaction_used"] is False


@pytest.mark.caccia(id="CB-1667", fonte="2014 · Chierico · Tabella di classe (slot incantesimo) · pag. 57", zona="regola:2014/cleric",
                    voce="limiti",
                    copre=["carta:2014/classes/cleric.md#Incantesimi / Spellcasting (Chierico 1, pag. 58)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, slot", [
    (1, {1: 2}),
    (17, {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1}),
    (18, {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1}),
    (19, {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1}),
    (20, {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1}),
])
async def test_slot_del_chierico_dalla_tabella(client, livello, slot):
    scheda = await _scheda(client, await _chierico(client, livello))
    assert {s["level"]: s["total"] for s in scheda["spell_slots"]} == slot


@pytest.mark.caccia(id="CB-1668", fonte="2014 · Chierico · Incantesimi (preparati) · pag. 58", zona="regola:2014/cleric",
                    voce="limiti",
                    copre=["carta:2014/classes/cleric.md#Incantesimi / Spellcasting (Chierico 1, pag. 58)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, saggezza, preparati", [(1, 8, 1), (1, 16, 4), (20, 20, 25)])
async def test_preparati_saggezza_piu_livello_minimo_uno(client, livello, saggezza, preparati):
    scheda = await _scheda(client, await _chierico(client, livello, wisdom=saggezza))
    assert scheda["spellcasting"]["prepared_cap"] == preparati


@pytest.mark.caccia(id="CB-1669", fonte="2014 · Chierico · Intervento Divino · pag. 59", zona="regola:2014/cleric",
                    voce="interazione",
                    copre=["carta:2014/classes/cleric.md#Intervento Divino / Divine Intervention (Chierico 10, pag. 59)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("d100, riesce", [(10, True), (11, False), (15, False)])
async def test_intervento_divino_confronta_il_d100_col_livello_da_chierico(client, dadi, d100, riesce):
    cid = await _chierico(client, 10)
    await _classe(client, cid, "fighter", 5, 10)  # livello del personaggio 15
    dadi(d100)
    r = await _usa(client, cid, "cleric.divine_intervention")
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["success"] is riesce


@pytest.mark.caccia(id="CB-1670", fonte="2014 · Chierico · Incanalare Divinità: Preservare Vita · pag. 63",
                    zona="regola:2014/cleric", voce="interazione",
                    copre=["carta:2014/classes/cleric.md#Incanalare Divinità: Preservare Vita / Channel Divinity: Preserve Life (Vita 2, pag. 63)",
                           "POST /characters/{char_id}/preserve-life"])
async def test_preservare_vita_usa_cinque_volte_il_livello_da_chierico(client):
    cid = await _chierico(client, 2, "life")
    await _classe(client, cid, "fighter", 5, 10)  # livello del personaggio 7: la riserva resta 10
    for corpo in ({"op": "set_max", "value": 80}, {"op": "set_current", "value": 1}):
        assert (await client.patch(f"/characters/{cid}/hp", json=corpo)).status_code == 200
    troppo = await client.post(f"/characters/{cid}/preserve-life", json={
        "allocations": [{"character_id": cid, "amount": 11}], "confirm_living": True})
    assert troppo.status_code == 422 and troppo.json()["detail"]["code"] == "over_pool"
    r = await client.post(f"/characters/{cid}/preserve-life", json={
        "allocations": [{"character_id": cid, "amount": 10}], "confirm_living": True})
    assert r.status_code == 200, r.text
    assert r.json()["pool"] == 10 and (await _scheda(client, cid))["current_hit_points"] == 11
