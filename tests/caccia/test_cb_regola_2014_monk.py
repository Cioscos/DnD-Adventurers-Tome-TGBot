"""Controlli della zona regola:2014/monk."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_barbarian_round1 import _in_encounter
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_monk import SHIELD, _equip, _monk, _rest
from tests.integration.rules.test_2014_monk_ki import _damage, _hit, _ki, _states, _strike


async def _hp_pieni(client, cid, pf=60) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": pf})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": pf})


async def _monaco_in_scontro(client, factory, monkeypatch, livello, sottoclasse=None) -> tuple[int, int]:
    """Il PG dello scontro di prova (primo all'iniziativa, è il suo turno) diventa un monaco 2014."""
    sid, cid = await _in_encounter(client, factory, monkeypatch)
    corpo = {"class_name": "monk", "level": livello, "hit_die": 8, **({"subclass": sottoclasse} if sottoclasse else {})}
    r = await client.post(f"/characters/{cid}/classes", json=corpo)
    assert r.status_code == 201, r.text
    return sid, cid


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1811", fonte="2014 · Monaco · Elusione · pag. 92", zona="regola:2014/monk", voce="edizioni",
                    copre=["carta:2014/classes/monk.md#Elusione / Evasion (Monaco 7, pag. 92)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("edizione, offerta", [pytest.param("2014", True, marks=pytest.mark.xfail(strict=True, reason="CB-1811: difforme dal manuale, confermato")), ("2024", False)])
async def test_elusione_da_stordito_solo_nel_2024_si_perde(client, edizione, offerta):
    # 2014: nessuna clausola sull'incapacitato (il TS fallito d'ufficio dà comunque metà danni); 2024: non funziona da Incapacitato
    cid = await _monk(client, 7)
    if edizione != "2014":
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert r.status_code == 200, r.text
    assert ("monk.evasion" in await _roll_keys(client, cid, "save", ability="dexterity")) is offerta


@pytest.mark.caccia(id="CB-1812", fonte="2014 · Monaco · Difesa Paziente · pag. 91", zona="regola:2014/monk", voce="regola",
                    copre=["carta:2014/classes/monk.md#Difesa Paziente / Patient Defense (Monaco 2, pag. 91)",
                           "POST /characters/{char_id}/features/{feature_key}/use",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.xfail(strict=True, reason="CB-1812: difforme dal manuale, confermato")
async def test_difesa_paziente_da_vantaggio_ai_ts_su_destrezza(client, dadi):
    # Difesa Paziente fa l'azione di Schivata: fino al prossimo turno i TS su Destrezza hanno vantaggio (Schivata, pag. 193)
    cid = await _monk(client, 2)
    assert (await _use(client, cid, "monk.patient_defense")).status_code == 200
    dadi(4, 16)
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={})
    assert r.status_code == 200, r.text
    assert (r.json()["mode"], r.json()["die"]) == ("advantage", 16)


@pytest.mark.caccia(id="CB-1813", fonte="2014 · Monaco · Tranquillità · pag. 93", zona="regola:2014/monk", voce="interazione",
                    copre=["carta:2014/classes/monk.md#Tranquillità / Tranquility (Monaco 11, pag. 93)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-1813: difforme dal manuale, confermato")
async def test_tranquillita_resta_dopo_un_incantesimo_che_non_tocca_nemici(client):
    # Santuario 2014 (pag. 272) finisce se il protetto attacca o lancia un incantesimo su un nemico: Luce non tocca nessuno
    cid = await _monk(client, 11, "open_hand")
    await _rest(client, cid, "long")
    assert "tranquility" in await _states(client, cid)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Luce", "level": 0, "srd_index": "light",
                                                            "casting_time": "1 azione"})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={})).status_code == 200
    assert "tranquility" in await _states(client, cid)


@pytest.mark.caccia(id="CB-1814", fonte="2014 · Monaco · Passo dell'Ombra, Zanne del Serpente di Fuoco, Raffica di Colpi · pag. 93, 94, 91",
                    zona="regola:2014/monk", voce="regola",
                    copre=["carta:2014/classes/monk.md#Passo dell'Ombra / Shadow Step (Monaco 6, pag. 93)",
                           "carta:2014/classes/monk.md#Zanne del Serpente di Fuoco / Fangs of the Fire Snake (Monaco 3, Via dei Quattro Elementi, pag. 94)",
                           "carta:2014/classes/monk.md#Raffica di Colpi / Flurry of Blows (Monaco 2, pag. 91)",
                           "POST /sessions/{session_id}/encounter/next-turn"])
@pytest.mark.parametrize("caso", ["passo_dell_ombra", "zanne", "raffica"])
@pytest.mark.xfail(strict=True, reason="CB-1814: difforme dal manuale, confermato")
async def test_gli_effetti_di_questo_turno_finiscono_con_il_turno_del_monaco(client, test_session_factory, monkeypatch, caso):
    # Vantaggio «prima della fine del turno», portata e fuoco «per il resto del turno», i due colpi dell'azione bonus:
    # nel turno del goblin non valgono più (un attacco di opportunità non li usa)
    if caso == "passo_dell_ombra":
        sid, cid = await _monaco_in_scontro(client, test_session_factory, monkeypatch, 6, "Via dell'Ombra")
        assert (await _use(client, cid, "monk.shadow_step", params={"light": "dim_or_dark"})).status_code == 200
        opzione = "monk.shadow_step_advantage"
    elif caso == "zanne":
        sid, cid = await _monaco_in_scontro(client, test_session_factory, monkeypatch, 3, "Via dei Quattro Elementi")
        scelta = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "elemental_disciplines")
        r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve",
                              json={"kind": "class_option", "options": ["fangs_of_the_fire_snake"]})
        assert r.status_code == 200, r.text
        assert (await _use(client, cid, "monk.discipline_fangs_of_the_fire_snake")).status_code == 200
        opzione = "monk.fangs_extra_damage"
    else:
        sid, cid = await _monaco_in_scontro(client, test_session_factory, monkeypatch, 2)
        assert (await _strike(client, cid)).status_code == 200
        assert (await _use(client, cid, "monk.flurry_of_blows")).status_code == 200
        opzione = "monk.flurry_strike"
    assert opzione in await _roll_keys(client, cid, "attack")
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # tocca al primo goblin
    as_user(PLAYER_ID)
    assert opzione not in await _roll_keys(client, cid, "attack")


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1815", fonte="2014 · Monaco · Ki · pag. 91", zona="regola:2014/monk", voce="limiti",
                    copre=["carta:2014/classes/monk.md#Ki / Ki (Monaco 2, pag. 91)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, atteso", [(1, None), (2, (2, "short_rest")), (19, (19, "short_rest")), (20, (20, "short_rest"))])
async def test_punti_ki_pari_al_livello_e_tornano_col_riposo_breve(client, livello, atteso):
    riga = await _ability(client, await _monk(client, livello), "monk.ki")
    assert (None if riga is None else (riga["max_uses"], riga["restoration_type"])) == atteso


@pytest.mark.caccia(id="CB-1816", fonte="2014 · Monaco · Arti Marziali · pag. 91", zona="regola:2014/monk", voce="limiti",
                    copre=["carta:2014/classes/monk.md#Arti Marziali / Martial Arts (Monaco 1, pag. 91)",
                           "POST /characters/{char_id}/attack/unarmed"])
@pytest.mark.parametrize("livello, dado", [(1, "1d4"), (4, "1d4"), (5, "1d6"), (10, "1d6"), (11, "1d8"), (16, "1d8"),
                                           (17, "1d10"), (20, "1d10")])
async def test_dado_di_arti_marziali_alle_soglie(client, livello, dado):
    r = await client.post(f"/characters/{await _monk(client, livello)}/attack/unarmed", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"] == dado


@pytest.mark.caccia(id="CB-1817", fonte="2014 · Monaco · Movimento Senza Armatura · pag. 91", zona="regola:2014/monk", voce="limiti",
                    copre=["carta:2014/classes/monk.md#Movimento Senza Armatura / Unarmored Movement (Monaco 2, pag. 91)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, velocita", [(1, 30), (2, 40), (5, 40), (6, 45), (9, 45), (10, 50), (13, 50), (14, 55),
                                               (17, 55), (18, 60), (20, 60)])
async def test_movimento_senza_armatura_alle_soglie(client, livello, velocita):
    assert (await _full(client, await _monk(client, livello)))["computed"]["speed"] == velocita


@pytest.mark.caccia(id="CB-1818", fonte="2014 · Monaco · Ki · pag. 91", zona="regola:2014/monk", voce="interazione",
                    copre=["carta:2014/classes/monk.md#Ki / Ki (Monaco 2, pag. 91)",
                           "carta:2014/classes/monk.md#Multiclasse: Monaco / Multiclassing: Monk (Capitolo 6, pag. 163)",
                           "POST /characters/{char_id}/classes"])
async def test_ki_in_multiclasse_livello_da_monaco_e_competenza_totale(client):
    cid = await _monk(client, 5, wisdom=16)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 4, "hit_die": 10})
    assert r.status_code == 201, r.text
    riga = await _ability(client, cid, "monk.ki")
    assert (riga["max_uses"], riga["dc"]) == (5, 8 + 4 + 3)  # livello totale 9: competenza +4; Saggezza +3


@pytest.mark.caccia(id="CB-1819", fonte="2014 · Monaco · Deviare Proiettili · pag. 91", zona="regola:2014/monk", voce="interazione",
                    copre=["carta:2014/classes/monk.md#Deviare Proiettili / Deflect Missiles (Monaco 3, pag. 91)",
                           "PATCH /characters/{char_id}/hp"])
async def test_deviare_proiettili_usa_il_solo_livello_da_monaco(client, dadi):
    cid = await _monk(client, 5, dexterity=16)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 4, "hit_die": 10})
    assert r.status_code == 201, r.text
    await _hp_pieni(client, cid)
    dadi(6)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "piercing",
                                                          "options": ["monk.deflect_missiles"]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["damage_after"] == 20 - (6 + 3 + 5)  # 1d10 + Destrezza + livello da monaco (non 9)


@pytest.mark.caccia(id="CB-1820", fonte="2014 · Monaco · Difesa Senza Armatura · pag. 91", zona="regola:2014/monk", voce="regola",
                    copre=["carta:2014/classes/monk.md#Difesa Senza Armatura / Unarmored Defense (Monaco 1, pag. 91)",
                           "PATCH /characters/{char_id}/items/{item_id}"])
async def test_difesa_senza_armatura_destrezza_e_saggezza_senza_scudo(client):
    cid = await _monk(client, 1, dexterity=16, wisdom=14)
    assert (await _full(client, cid))["ac_breakdown"]["base"] == 10 + 3 + 2
    con_scudo = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert (con_scudo["ac_breakdown"]["base"], con_scudo["unarmored_formula"]) == (10 + 3, None)


@pytest.mark.caccia(id="CB-1821", fonte="2014 · Monaco · Colpo Stordente · pag. 92", zona="regola:2014/monk", voce="regola",
                    copre=["carta:2014/classes/monk.md#Colpo Stordente / Stunning Strike (Monaco 5, pag. 92)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage",
                           "GET /characters/{char_id}/target-effects/{effect_key}"])
async def test_colpo_stordente_un_ki_ts_costituzione_cd_ki_fino_al_prossimo_turno(client):
    cid = await _monk(client, 5, wisdom=16, dexterity=16)  # competenza +3, Saggezza +3: CD 14
    colpo = await _hit(client, cid)
    assert (await _damage(client, cid, colpo, "monk.stunning_strike")).status_code == 200
    assert await _ki(client, cid) == 4
    effetto = (await client.get(f"/characters/{cid}/target-effects/monk.stunning_strike")).json()["result"]
    assert (effetto["condition"], effetto["save_ability"], effetto["save_dc"], effetto["ends_at"]) == (
        "stunned", "constitution", 14, {"anchor": "source", "edge": "end", "count": 1})


@pytest.mark.caccia(id="CB-1822", fonte="2014 · Monaco · Discepolo degli Elementi · pag. 93", zona="regola:2014/monk", voce="limiti",
                    copre=["carta:2014/classes/monk.md#Discepolo degli Elementi / Disciple of the Elements (Monaco 3, pag. 93)"])
@pytest.mark.parametrize("livello, tetto", [(5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)])
def test_tetto_di_ki_per_incantesimo(livello, tetto):
    from core.rules.spellcasting import ki_spell_cap
    assert ki_spell_cap(livello) == tetto
