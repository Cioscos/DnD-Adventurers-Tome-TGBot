"""Controlli della zona regola:2014/generali (parte generali-b)."""
import pytest

from core.db.models import SessionParticipant, SessionRole
from core.rules.spellcasting import concentration_dc
from tests.integration._encounter_helpers import GM_ID, NOW, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_warlock_invocations import _caster, _spells_by_index


async def _pg(client, classe="cleric", livello=7, sottoclasse=None) -> int:
    corpo = {"name": "Incantatore", "initial_class": {"class_name": classe, "level": livello, "subclass": sottoclasse}}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})
    assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _incantesimo(client, cid, nome, livello, srd=None, tempo="1 azione", concentrazione=False, preparato=True) -> int:
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    corpo = {"name": nome, "level": livello, "casting_time": tempo, "class_id": classe, "is_prepared": preparato,
             "is_concentration": concentrazione, **({"srd_index": srd} if srd else {})}
    r = await client.post(f"/characters/{cid}/spells", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _lancia(client, cid, sid, **corpo) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json=corpo)
    assert r.status_code == 200, r.text
    return r.json()


async def _condizioni(client, cid, **cond) -> dict:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": cond})
    assert r.status_code == 200, r.text
    return r.json()


async def _pf(client, cid, massimo, attuali) -> None:
    for op, v in (("set_max", massimo), ("set_current", attuali)):
        r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})
        assert r.status_code == 200, r.text


async def _danno(client, cid, valore, **extra) -> dict:
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": valore, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def _opzioni(client, cid, tiro, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _seduto(client, fabbrica, sessione, utente, classe, livello, caratteristica, valore, nome, srd, livello_inc, conc) -> tuple[int, int]:
    """Un incantatore 2014 di ``utente`` seduto nella serata ``sessione``: (personaggio, incantesimo)."""
    as_user(utente)
    cid = await _pg(client, classe, livello)
    assert (await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})).status_code == 200
    sid = await _incantesimo(client, cid, nome, livello_inc, srd, concentrazione=conc)
    if utente == GM_ID:
        await _seat(fabbrica, cid, GM_ID)
    else:
        async with fabbrica() as s:
            s.add(SessionParticipant(session_id=sessione, user_id=utente, character_id=cid, role=SessionRole.PLAYER,
                                     display_name=f"Incantatore {utente}", joined_at=NOW))
            await s.commit()
    return cid, sid


async def _finta_morte(client, cid) -> None:
    await _lancia(client, cid, await _incantesimo(client, cid, "Finta morte", 3, "feign-death"), slot_level=3)


async def _pianta_in_vaso(client, cid) -> None:
    r = await client.post(f"/characters/{cid}/wild-magic/surge", json={"die": 1, "percentile": [41]})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2811", fonte="2014 · Condizioni · Incapacitato · pag. 291; Combattimento · Azioni Bonus · pag. 189-190",
                    zona="regola:2014/generali", voce="regola",
                    copre=["carta:2014/general.md#Azioni Bonus / Bonus Actions (pag. 189-190)",
                           "carta:2014/general.md#Lanciare un Incantesimo / Casting a Spell (pag. 202)",
                           "PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("condizione,tempo", [("stunned", "1 azione"), ("paralyzed", "1 azione bonus"), ("incapacitated", "1 reazione")])
@pytest.mark.xfail(strict=True, reason="CB-2811: difforme dal manuale, confermato")
async def test_chi_non_puo_agire_non_lancia_e_non_spende_lo_slot(client, condizione, tempo):
    cid = await _pg(client, "cleric", 3)
    sid = await _incantesimo(client, cid, "Preghiera breve", 1, tempo=tempo)
    await _condizioni(client, cid, **{condizione: True})
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 1})
    assert r.status_code == 409, r.text
    assert all(s["used"] == 0 for s in (await _scheda(client, cid))["spell_slots"])


@pytest.mark.caccia(id="CB-2812", fonte="2014 · Condizioni · Regole generali · pag. 290 (ogni effetto ha la sua durata)", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Regole generali / General (pag. 290)",
                                               "POST /characters/{char_id}/features/{feature_key}/use", "DELETE /characters/{char_id}/active-states/{key}"])
@pytest.mark.xfail(strict=True, reason="CB-2812: difforme dal manuale, confermato")
async def test_finiti_i_due_effetti_che_rendono_invisibili_la_condizione_cade(client):
    cid = await _pg(client, "monk", 18, "Via dell'Ombra")
    r = await client.post(f"/characters/{cid}/features/monk.cloak_of_shadows/use", json={"params": {"light": "dim_or_dark"}})
    assert r.status_code == 200, r.text
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    r = await client.post(f"/characters/{cid}/features/monk.empty_body/use", json={})
    assert r.status_code == 200, r.text
    for chiave in ("cloak_of_shadows", "empty_body"):
        assert (await client.delete(f"/characters/{cid}/active-states/{chiave}")).status_code == 200
    j = await _scheda(client, cid)
    assert not j["active_states"]
    assert not j["conditions"].get("invisible")


@pytest.mark.caccia(id="CB-2813", fonte="2014 · Lancio di incantesimi · Tempo di Lancio, Azione Bonus · pag. 202", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Tempo di Lancio / Casting Time (pag. 202)",
                                               "POST /characters/{char_id}/spells/{spell_id}/use", "GET /characters/{char_id}/spells/{spell_id}/cast-check"])
@pytest.mark.xfail(strict=True, reason="CB-2813: difforme dal manuale, confermato")
async def test_dopo_un_incantesimo_di_livello_senza_slot_quello_bonus_va_confermato(client):
    cid = await _caster(client, 2, "armor_of_shadows")
    armatura = (await _spells_by_index(client, cid))["mage-armor"]
    rapido = await _incantesimo(client, cid, "Incantesimo rapido", 1, tempo="1 azione bonus")
    await _lancia(client, cid, armatura["id"], free_cast=True)
    r = await client.get(f"/characters/{cid}/spells/{rapido}/cast-check")
    assert r.status_code == 200, r.text
    assert "bonus_spell" in r.json()


@pytest.mark.caccia(id="CB-2814", fonte="2014 · Lancio di incantesimi · Combinare Effetti Magici · pag. 205 (vale il più potente)", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Combinare Effetti Magici / Combining Magical Effects (pag. 205)",
                                               "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/turn/new"])
@pytest.mark.xfail(strict=True, reason="CB-2814: difforme dal manuale, confermato")
async def test_due_eroismi_sullo_stesso_bersaglio_vale_il_piu_potente(client, test_session_factory):
    sessione, eroe = await seed_session(test_session_factory)
    forte = await _seduto(client, test_session_factory, sessione, GM_ID, "bard", 1, "charisma", 20, "Eroismo", "heroism", 1, True)
    debole = await _seduto(client, test_session_factory, sessione, 9001, "bard", 1, "charisma", 16, "Eroismo", "heroism", 1, True)
    for utente, (bardo, eroismo) in ((GM_ID, forte), (9001, debole)):
        as_user(utente)
        assert (await _lancia(client, bardo, eroismo, slot_level=1, targets=[eroe]))["spell_effects"]["applied"] == [{"id": eroe, "name": "Eroe"}]
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{eroe}/turn/new")).status_code == 200
    assert (await _scheda(client, eroe))["temp_hp"] == 5


@pytest.mark.caccia(id="CB-2815", fonte="2014 · Lancio di incantesimi · Concentrazione · pag. 203 (incapacitato la interrompe); Incapacitato · pag. 291",
                    zona="regola:2014/generali", voce="interazione",
                    copre=["carta:2014/general.md#Durata / Duration (pag. 203)", "PATCH /characters/{char_id}/concentration",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/wild-magic/surge"])
@pytest.mark.parametrize("classe,sottoclasse,incapacita", [("cleric", None, _finta_morte), ("sorcerer", "Magia Selvaggia", _pianta_in_vaso)])
@pytest.mark.xfail(strict=True, reason="CB-2815: difforme dal manuale, confermato")
async def test_uno_stato_che_incapacita_interrompe_la_concentrazione(client, classe, sottoclasse, incapacita):
    cid = await _pg(client, classe, 5, sottoclasse)
    volo = await _incantesimo(client, cid, "Volo", 1, concentrazione=True)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": volo})).status_code == 200
    await incapacita(client, cid)
    j = await _scheda(client, cid)
    assert j["conditions"].get("incapacitated") is True
    assert j["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-2816", fonte="2014 · Condizioni · Afferrato · pag. 290, Trattenuto · pag. 292 (velocità 0); Indebolimento · pag. 291 (velocità dimezzata, poi 0)",
                    zona="regola:2014/generali", voce="interazione",
                    copre=["carta:2014/general.md#Afferrato / Grappled (pag. 290)", "carta:2014/general.md#Trattenuto / Restrained (pag. 292)",
                           "carta:2014/general.md#Movimento e Posizione / Movement and Position (pag. 190)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("condizioni,volo", [({"grappled": True}, 0), ({"restrained": True}, 0), ({"exhaustion": 2}, 30), ({"exhaustion": 5}, 0)])
async def test_la_velocita_di_volo_segue_le_condizioni_che_toccano_la_velocita(client, condizioni, volo):
    cid = await _pg(client, "wizard", 5)
    sid = await _incantesimo(client, cid, "Volare", 3, "fly", concentrazione=True, preparato=False)
    await _lancia(client, cid, sid, slot_level=3)
    assert (await _scheda(client, cid))["computed"]["fly_speed"] == 60
    j = await _condizioni(client, cid, **condizioni)
    assert (j["computed"]["fly_speed"] or 0) == volo


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2817", fonte="2014 · Condizioni · Spaventato · pag. 292; Accecato, Assordato · pag. 290", zona="regola:2014/generali",
                    voce="regola", copre=["carta:2014/general.md#Spaventato / Frightened (pag. 292)",
                                          "carta:2014/general.md#Accecato / Blinded (pag. 290)",
                                          "carta:2014/general.md#Assordato / Deafened (pag. 290)",
                                          "GET /characters/{char_id}/roll-options", "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("condizione", ["frightened", "blinded", "deafened"])
async def test_la_condizione_vale_anche_sulla_prova_di_caratteristica_pura(client, condizione):
    cid = await _pg(client, "fighter", 3)
    await _condizioni(client, cid, **{condizione: True})
    assert f"condition:{condizione}" in await _opzioni(client, cid, "skill", skill="athletics")
    assert f"condition:{condizione}" in await _opzioni(client, cid, "ability", ability="strength")


@pytest.mark.caccia(id="CB-2818", fonte="2014 · Combattimento · Morte Istantanea · pag. 197 (chierico max 12, 6 PF, 18 danni)", zona="regola:2014/generali",
                    voce="limiti", copre=["carta:2014/general.md#Scendere a 0 Punti Ferita / Dropping to 0 Hit Points (pag. 197)",
                                          "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("danno,morto", [(18, True), (17, False)])
async def test_morte_istantanea_quando_il_residuo_raggiunge_il_massimo(client, danno, morto):
    cid = await _pg(client, "cleric", 1)
    await _pf(client, cid, 12, 6)
    j = await _danno(client, cid, danno)
    assert (j["is_dead"], j["current_hit_points"]) == (morto, 0)
    assert morto or j["conditions"].get("unconscious") is True


@pytest.mark.caccia(id="CB-2819", fonte="2014 · Combattimento · Tiri Salvezza Contro Morte · pag. 197", zona="regola:2014/generali",
                    voce="regola", copre=["POST /characters/{char_id}/death_saves/roll"])
@pytest.mark.parametrize("dado,successi,fallimenti,pf", [(1, 0, 2, 0), (9, 0, 1, 0), (10, 1, 0, 0), (20, 0, 0, 1)])
async def test_tiro_contro_la_morte_10_successo_1_due_fallimenti_20_un_pf(client, dado, successi, fallimenti, pf):
    cid = await _pg(client, "fighter", 3)
    await _pf(client, cid, 20, 0)
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": dado})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["successes"], j["failures"], j["current_hp"]) == (successi, fallimenti, pf)
    assert bool((await _scheda(client, cid))["conditions"].get("unconscious")) is (pf == 0)


@pytest.mark.caccia(id="CB-2820", fonte="2014 · Combattimento · Danni a 0 Punti Ferita · pag. 197; Punti Ferita Temporanei · pag. 198", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Punti Ferita Temporanei / Temporary Hit Points (pag. 198)",
                                               "PATCH /characters/{char_id}/hp"])
async def test_a_zero_pf_i_temporanei_non_svegliano_e_assorbono_prima_del_fallimento(client):
    cid = await _pg(client, "fighter", 3)
    await _pf(client, cid, 20, 0)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 5})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["conditions"].get("unconscious") is True and j["death_saves"].get("failures", 0) == 0
    j = await _danno(client, cid, 3)
    assert (j["temp_hp"], j["death_saves"].get("failures", 0)) == (2, 0)
    j = await _danno(client, cid, 4, was_critical_hit=True)
    assert (j["temp_hp"], j["death_saves"]["failures"], j["is_dead"]) == (0, 2, False)


@pytest.mark.caccia(id="CB-2821", fonte="2014 · Lancio di incantesimi · Concentrazione · pag. 203 (CD maggiore fra 10 e metà danno); 2024 · Concentration · pag. 363",
                    zona="regola:2014/generali", voce="edizioni", copre=["carta:2014/general.md#Durata / Duration (pag. 203)"])
@pytest.mark.parametrize("danno,cd_2014", [(1, 10), (21, 10), (22, 11), (70, 35)])
def test_cd_di_concentrazione_senza_tetto_nel_2014(danno, cd_2014):
    assert concentration_dc("2014", danno) == cd_2014
    assert concentration_dc("2024", danno) == min(cd_2014, 30)


@pytest.mark.caccia(id="CB-2822", fonte="2014 · Combattimento · Resistenza e Vulnerabilità · pag. 197 (più istanze contano come una)", zona="regola:2014/generali",
                    voce="regola", copre=["carta:2014/general.md#Danni e Guarigione / Damage and Healing (pag. 196-197)",
                                          "carta:2014/general.md#Pietrificato / Petrified (pag. 291)",
                                          "PATCH /characters/{char_id}", "PATCH /characters/{char_id}/hp"])
async def test_due_resistenze_allo_stesso_danno_dimezzano_una_volta(client):
    cid = await _pg(client, "fighter", 3)
    r = await client.patch(f"/characters/{cid}", json={"damage_modifiers": {"resistances": ["fire"]}})
    assert r.status_code == 200, r.text
    await _condizioni(client, cid, petrified=True)
    await _pf(client, cid, 40, 40)
    assert (await _danno(client, cid, 25, damage_type="fire"))["current_hit_points"] == 28


@pytest.mark.caccia(id="CB-2823", fonte="2014 · Condizioni · Regole generali · pag. 290; Lancio di incantesimi · Concentrazione · pag. 203", zona="regola:2014/generali",
                    voce="interazione", copre=["POST /characters/{char_id}/spells/{spell_id}/use", "PATCH /characters/{char_id}/concentration"])
async def test_passando_a_invisibilita_superiore_la_condizione_cade_con_la_concentrazione(client):
    cid = await _pg(client, "sorcerer", 7)
    inv = await _incantesimo(client, cid, "Invisibilità", 2, "invisibility", concentrazione=True)
    sup = await _incantesimo(client, cid, "Invisibilità superiore", 4, "greater-invisibility", concentrazione=True)
    await _lancia(client, cid, inv, slot_level=2)
    await _lancia(client, cid, sup, slot_level=4)
    assert (await _scheda(client, cid))["conditions"].get("invisible") is True
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200
    assert not (await _scheda(client, cid))["conditions"].get("invisible")


@pytest.mark.caccia(id="CB-2824", fonte="2014 · Lancio di incantesimi · Combinare Effetti Magici · pag. 205 (vale il più potente)", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Combinare Effetti Magici / Combining Magical Effects (pag. 205)",
                                               "carta:2014/general.md#Lanciare un Incantesimo a un Livello Superiore / Casting a Spell at a Higher Level (pag. 201)",
                                               "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_due_aiuti_sullo_stesso_bersaglio_vale_il_piu_potente(client, test_session_factory):
    sessione, eroe = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await _pf(client, eroe, 30, 30)
    forte = await _seduto(client, test_session_factory, sessione, GM_ID, "cleric", 5, "wisdom", 14, "Aiuto", "aid", 2, False)
    debole = await _seduto(client, test_session_factory, sessione, 9001, "cleric", 5, "wisdom", 14, "Aiuto", "aid", 2, False)
    for utente, (chierico, aiuto), slot in ((GM_ID, forte, 3), (9001, debole, 2)):
        as_user(utente)
        await _lancia(client, chierico, aiuto, slot_level=slot, targets=[eroe])
    as_user(PLAYER_ID)
    assert (await _scheda(client, eroe))["computed"]["hp_max_effective"] == 40
