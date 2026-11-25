"""Controlli della zona regola:2024/cleric."""
import pytest

from tests.integration.rules.test_2014_barbarian import _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _resolve, _states, _use
from tests.integration.rules.test_2014_cleric_domains import _deferred
from tests.integration.rules.test_2024_cleric import _cleric24
from tests.integration.rules.test_2024_cleric_domains import _dom

RISERVA = "cleric.channel_divinity"


async def _incantesimi(client, cid) -> dict[str, dict]:
    return {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}


async def _amuleto_cd(client, cid) -> None:
    """Un oggetto al collo con +1 alla CD degli incantesimi."""
    r = await client.post(f"/characters/{cid}/items", json={"name": "Amuleto", "item_type": "accessory",
                                                            "item_metadata": {"bonuses": [{"target": "spell_dc", "value": 1}]}})
    assert r.status_code == 201, r.text
    iid = next(i["id"] for i in r.json()["items"] if i["name"] == "Amuleto")
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "neck"})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2261", fonte="2024 · Chierico · Dominio della Guerra · Benedizione del Dio della Guerra · pag. 77",
                    zona="regola:2024/cleric", voce="regola",
                    copre=["carta:2024/classes/cleric.md#Benedizione del Dio della Guerra / War God's Blessing (Guerra 6, pag. 77)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/rounds/tick", "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("fine", ["un_minuto", "incapacitato"])
@pytest.mark.xfail(strict=True, reason="CB-2261: difforme dal manuale, confermato")
async def test_lo_scudo_della_fede_senza_concentrazione_finisce_con_la_benedizione_del_dio_della_guerra(client, fine):
    cid = await _dom(client, 6, "war")
    ca = (await _full(client, cid))["ac"]
    r = await _use(client, cid, "cleric.war_gods_blessing", params={"spell": "shield-of-faith"})
    assert r.status_code == 200, r.text
    scudo = (await _incantesimi(client, cid))["shield-of-faith"]["id"]
    r = await client.post(f"/characters/{cid}/spells/{scudo}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["ac"] == ca + 2
    if fine == "un_minuto":
        for _ in range(10):
            assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    else:
        r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
        assert r.status_code == 200, r.text
    assert not any(s["key"] == "war_gods_blessing" for s in await _states(client, cid))  # il minuto del privilegio è finito
    assert (await _full(client, cid))["ac"] == ca  # e con lui il +2 dell'incantesimo


@pytest.mark.caccia(id="CB-2262", fonte="2024 · Chierico · Intervento Divino · pag. 71", zona="regola:2024/cleric", voce="regola",
                    copre=["carta:2024/classes/cleric.md#Intervento Divino / Divine Intervention (Chierico 10, pag. 71)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_un_incantesimo_a_concentrazione_lanciato_con_intervento_divino_richiede_concentrazione(client):
    cid = await _cleric24(client, 10, wisdom=16)
    r = await _use(client, cid, "cleric.divine_intervention", params={"spell": "Benedizione", "spell_level": "1"})
    assert r.status_code == 200, r.text
    scelto = next(s["id"] for s in (await client.get(f"/characters/{cid}/spells")).json() if s["name"] == "Benedizione")
    r = await client.post(f"/characters/{cid}/spells/{scelto}/use", json={"free_cast": True, "targets": [cid]})
    assert r.status_code == 200, r.text
    assert any(s["key"] == "spell:bless" for s in await _states(client, cid))  # l'app riconosce Benedizione e ne applica l'effetto
    # Intervento Divino toglie slot e componenti materiali, non la concentrazione
    assert (await _full(client, cid))["concentrating_spell_id"] is not None


@pytest.mark.caccia(id="CB-2263", fonte="2024 · Chierico · Colpi Benedetti: Colpo Divino · pag. 71", zona="regola:2024/cleric",
                    voce="regola",
                    copre=["carta:2024/classes/cleric.md#Colpi Benedetti: Colpo Divino / Blessed Strikes: Divine Strike (Chierico 7, pag. 71)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("opzione, tipo", [("cleric.divine_strike_blessed_necrotic", "necrotic"),
                                           ("cleric.divine_strike_blessed_radiant", "radiant")])
async def test_i_dadi_del_colpo_divino_2024_hanno_il_tipo_scelto(client, opzione, tipo):
    cid = await _cleric24(client, 7, strength=14)
    assert (await _resolve(client, cid, "blessed_strikes", ["divine_strike"])).status_code == 200
    mazza = await _weapon(client, cid, "Mazza", damage_dice="1d6", damage_type="bludgeoning")
    esito = (await _deferred(client, cid, mazza, 15, opzione))["option_result"]
    assert len(esito["extra_rolls"]) == 1
    assert esito["extra_types"] == [tipo]  # non contundente come la mazza


@pytest.mark.caccia(id="CB-2264", fonte="2024 · Chierico · Incanalare Divinità (CD = CD degli incantesimi) · pag. 70-74",
                    zona="regola:2024/cleric", voce="regola",
                    copre=["carta:2024/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 70)",
                           "carta:2024/classes/cleric.md#Incanalare Divinità: Scintilla Divina / Channel Divinity: Divine Spark (Chierico 2, pag. 70)",
                           "carta:2024/classes/cleric.md#Incanalare Divinità: Scacciare Non Morti / Channel Divinity: Turn Undead (Chierico 2, pag. 70)",
                           "carta:2024/classes/cleric.md#Fulgore dell'Alba / Radiance of the Dawn (Luce 3, pag. 74)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("dominio, chiave, parametri", [
    (None, "cleric.divine_spark", {"mode": "damage_radiant"}),
    (None, "cleric.turn_undead", {}),
    ("light", "cleric.radiance_of_the_dawn", {}),
])
async def test_la_cd_di_incanalare_divinita_2024_e_quella_degli_incantesimi_del_chierico(client, dominio, chiave, parametri):
    cid = await (_dom(client, 3, dominio, wisdom=16) if dominio else _cleric24(client, 3, wisdom=16))  # 8 + 2 + 3 = 13
    await _amuleto_cd(client, cid)
    (cd_incantesimi,) = [c["save_dc"] for c in (await _full(client, cid))["spellcasting"]["casters"]]
    assert cd_incantesimi == 14
    r = await _use(client, cid, chiave, params=parametri)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["dc"] == cd_incantesimi


@pytest.mark.caccia(id="CB-2265", fonte="2024 · Chierico · Dominio della Vita · Guaritore Benedetto · pag. 74", zona="regola:2024/cleric",
                    voce="regola",
                    copre=["carta:2024/classes/cleric.md#Guaritore Benedetto / Blessed Healer (Vita 6, pag. 74)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.xfail(strict=True, reason="CB-2265: difforme dal manuale, confermato")
async def test_guaritore_benedetto_2024_non_vale_se_l_unico_bersaglio_e_il_chierico(client):
    cid = await _dom(client, 6, "life")
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})).status_code == 200
    cura = (await _incantesimi(client, cid))["cure-wounds"]["id"]
    r = await client.post(f"/characters/{cid}/spells/{cura}/roll_healing", json={
        "casting_level": 1, "apply_to_self": True, "options": ["cleric.blessed_healer"]})
    # Cura Ferite ha un solo bersaglio e qui è il chierico: la carta chiede almeno una creatura diversa da sé
    assert r.status_code != 200 or r.json()["self_healed"] == 0


@pytest.mark.caccia(id="CB-2266", fonte="2024 · Chierico · Incantesimi (preparati solo di livelli per cui si hanno slot) · pag. 69",
                    zona="regola:2024/cleric", voce="limiti",
                    copre=["carta:2024/classes/cleric.md#Incantesimi / Spellcasting (Chierico 1, pag. 69)",
                           "POST /characters/{char_id}/spells"])
@pytest.mark.parametrize("livello_chierico, livello_incantesimo", [(1, 2), (4, 3), (16, 9)])
async def test_il_chierico_2024_non_prepara_incantesimi_di_un_livello_senza_slot(client, livello_chierico, livello_incantesimo):
    cid = await _cleric24(client, livello_chierico, wisdom=16)  # posto libero fra i preparati
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Incantesimo alto", "level": livello_incantesimo,
                                                              "is_prepared": True})
    preparati = [s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["is_prepared"]]
    assert r.status_code in (400, 409, 422) and preparati == []


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2268", fonte="2024 · Chierico · Incanalare Divinità (usi per livello) · pag. 70", zona="regola:2024/cleric",
                    voce="limiti",
                    copre=["carta:2024/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 70)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, usi", [(1, None), (2, 2), (5, 2), (6, 3), (17, 3), (18, 4), (20, 4)])
async def test_usi_di_incanalare_divinita_2024_per_livello(client, livello, usi):
    riga = await _ability(client, await _cleric24(client, livello), RISERVA)
    assert (riga["max_uses"] if riga else None) == usi


@pytest.mark.caccia(id="CB-2269", fonte="2024 · Chierico · Incanalare Divinità (ricarica) · pag. 70", zona="regola:2024/cleric",
                    voce="regola",
                    copre=["carta:2024/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 70)",
                           "POST /characters/{char_id}/rest"])
async def test_incanalare_divinita_2024_torna_di_uno_col_riposo_breve_e_tutta_col_lungo(client):
    cid = await _cleric24(client, 6)
    for _ in range(3):
        await client.post(f"/characters/{cid}/turn/new")
        assert (await _use(client, cid, "cleric.turn_undead")).status_code == 200
    assert (await _ability(client, cid, RISERVA))["uses"] == 0
    for atteso in (1, 2):
        assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
        assert (await _ability(client, cid, RISERVA))["uses"] == atteso
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, RISERVA))["uses"] == 3


@pytest.mark.caccia(id="CB-2270", fonte="2024 · Chierico · Incanalare Divinità: Scintilla Divina · pag. 70", zona="regola:2024/cleric",
                    voce="limiti",
                    copre=["carta:2024/classes/cleric.md#Incanalare Divinità: Scintilla Divina / Channel Divinity: Divine Spark (Chierico 2, pag. 70)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("livello, dadi", [(2, 1), (6, 1), (7, 2), (12, 2), (13, 3), (17, 3), (18, 4), (20, 4)])
async def test_scintilla_divina_tira_da_uno_a_quattro_d8_piu_saggezza(client, livello, dadi):
    cid = await _cleric24(client, livello, wisdom=16)
    r = await _use(client, cid, "cleric.divine_spark", params={"mode": "damage_necrotic"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert len(corpo["rolls"]) == dadi and corpo["flat"] == 3
    assert corpo["state"]["data"]["damage"] == sum(corpo["rolls"]) + 3


@pytest.mark.caccia(id="CB-2271", fonte="2024 · Chierico · Dominio della Vita · Preservare Vita · pag. 73", zona="regola:2024/cleric",
                    voce="interazione",
                    copre=["carta:2024/classes/cleric.md#Preservare Vita / Preserve Life (Vita 3, pag. 73)",
                           "POST /characters/{char_id}/classes", "POST /characters/{char_id}/preserve-life"])
async def test_preservare_vita_2024_usa_cinque_volte_il_livello_da_chierico(client):
    cid = await _dom(client, 3, "life")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text  # livello del personaggio 8: la riserva resta 15
    for corpo in ({"op": "set_max", "value": 80}, {"op": "set_current", "value": 1}):
        assert (await client.patch(f"/characters/{cid}/hp", json=corpo)).status_code == 200
    troppo = await client.post(f"/characters/{cid}/preserve-life", json={"allocations": [{"character_id": cid, "amount": 16}]})
    assert troppo.status_code == 422 and troppo.json()["detail"]["code"] == "over_pool"
    r = await client.post(f"/characters/{cid}/preserve-life", json={"allocations": [{"character_id": cid, "amount": 15}]})
    assert r.status_code == 200, r.text
    assert r.json()["pool"] == 15 and (await _full(client, cid))["current_hit_points"] == 16


@pytest.mark.caccia(id="CB-2272", fonte="2024 · Chierico · Dominio della Guerra · Avatar della Battaglia · pag. 77", zona="regola:2024/cleric",
                    voce="interazione",
                    copre=["carta:2024/classes/cleric.md#Avatar della Battaglia / Avatar of Battle (Guerra 17, pag. 77)",
                           "PATCH /characters/{char_id}/hp"])
async def test_avatar_della_battaglia_2024_non_si_somma_a_una_resistenza_gia_presente(client):
    cid = await _dom(client, 17, "war")
    r = await client.patch(f"/characters/{cid}", json={"damage_modifiers": {"resistances": ["slashing"]}})
    assert r.status_code == 200, r.text
    prima = (await _full(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "slashing"})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == prima - 10  # dimezzato una volta sola


@pytest.mark.caccia(id="CB-2273", fonte="2024 · Chierico · Incantesimi (multiclasse: metà per eccesso dei livelli da paladino) · pag. 44-45",
                    zona="regola:2024/cleric", voce="interazione",
                    copre=["carta:2024/classes/cleric.md#Incantesimi / Spellcasting (Chierico 1, pag. 69)",
                           "carta:2024/classes/cleric.md#Multiclasse: Chierico / Multiclassing: Cleric (Chierico, pag. 44)",
                           "POST /characters/{char_id}/classes"])
@pytest.mark.parametrize("paladino, slot", [(1, {1: 4, 2: 3}), (3, {1: 4, 2: 3, 3: 2})])
async def test_slot_del_chierico_2024_con_livelli_da_paladino(client, paladino, slot):
    cid = await _cleric24(client, 3)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "paladin", "level": paladino, "hit_die": 10})
    assert r.status_code == 201, r.text
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]} == slot


@pytest.mark.caccia(id="CB-2274", fonte="2014 · Chierico · Dominio Divino · pag. 58 / 2024 · Chierico · Sottoclasse del Chierico · pag. 71",
                    zona="regola:2024/cleric", voce="edizioni",
                    copre=["carta:2024/classes/cleric.md#Sottoclasse del Chierico / Cleric Subclass (Chierico 3, pag. 71)",
                           "GET /rules/subclasses"])
@pytest.mark.parametrize("edizione, livello, domini", [
    ("2014", 1, {"knowledge", "life", "light", "nature", "tempest", "trickery", "war"}),
    ("2024", 3, {"life", "light", "trickery", "war"}),
])
async def test_il_dominio_si_sceglie_al_primo_livello_nel_2014_e_al_terzo_nel_2024(client, edizione, livello, domini):
    r = await client.get("/rules/subclasses", params={"edition": edizione, "class_key": "cleric"})
    assert r.status_code == 200, r.text
    assert {s["key"] for s in r.json()} == domini
    assert {s["choice_level"] for s in r.json()} == {livello}


@pytest.mark.caccia(id="CB-2275", fonte="2024 · Chierico · Dominio della Guerra · Benedizione del Dio della Guerra · pag. 77",
                    zona="regola:2024/cleric", voce="ripetizione",
                    copre=["carta:2024/classes/cleric.md#Benedizione del Dio della Guerra / War God's Blessing (Guerra 6, pag. 77)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_un_doppio_lancio_gratuito_della_benedizione_non_spende_altro(client):
    cid = await _dom(client, 6, "war")
    assert (await _use(client, cid, "cleric.war_gods_blessing", params={"spell": "spiritual-weapon"})).status_code == 200
    arma = (await _incantesimi(client, cid))["spiritual-weapon"]["id"]
    slot = [(s["level"], s["used"]) for s in (await _full(client, cid))["spell_slots"]]
    assert (await client.post(f"/characters/{cid}/spells/{arma}/use", json={"free_cast": True})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    di_nuovo = await client.post(f"/characters/{cid}/spells/{arma}/use", json={"free_cast": True})
    assert di_nuovo.status_code == 409
    assert (await _ability(client, cid, RISERVA))["uses"] == 2  # un solo uso di Incanalare Divinità
    assert [(s["level"], s["used"]) for s in (await _full(client, cid))["spell_slots"]] == slot  # nessuno slot
