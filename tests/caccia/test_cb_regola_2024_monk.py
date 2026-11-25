"""Controlli della zona regola:2024/monk."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_barbarian_round1 import _in_encounter
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_monk import SHIELD, _equip, _rest, _turn
from tests.integration.rules.test_2014_monk_ki import _conditions, _damage, _full_hp, _hit, _ki, _states, _strike
from tests.integration.rules.test_2024_monk import _monk24
from tests.integration.rules.test_2024_monk_subclasses import _sub


async def _monaco_in_scontro(client, factory, monkeypatch, livello, sottoclasse=None) -> tuple[int, int]:
    """Il PG dello scontro di prova (primo all'iniziativa, è il suo turno) diventa un monaco 2024."""
    sid, cid = await _in_encounter(client, factory, monkeypatch)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    corpo = {"class_name": "monk", "level": livello, "hit_die": 8, **({"subclass": sottoclasse} if sottoclasse else {})}
    r = await client.post(f"/characters/{cid}/classes", json=corpo)
    assert r.status_code == 201, r.text
    return sid, cid


async def _monaco(client, sottoclasse, livello, **punteggi) -> int:
    return await (_monk24(client, livello, **punteggi) if sottoclasse is None else _sub(client, sottoclasse, livello, **punteggi))


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2411", fonte="2024 · Monaco · Difesa Paziente · pag. 102; Glossario · Schivata · pag. 366", zona="regola:2024/monk",
                    voce="regola",
                    copre=["carta:2024/classes/monk.md#Difesa Paziente / Patient Defense (Monaco 2, pag. 102)",
                           "carta:2024/general.md#Dodge [Action] (Schivata) (pag. 366)",
                           "POST /characters/{char_id}/features/{feature_key}/use",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
async def test_difesa_paziente_a_punto_da_vantaggio_ai_ts_su_destrezza(client, dadi):
    # La versione a 1 punto fa Disimpegno e Schivata: fino al prossimo turno i TS su Destrezza hanno vantaggio
    cid = await _monk24(client, 2)
    assert (await _use(client, cid, "monk.patient_defense_focus")).status_code == 200
    dadi(4, 16)
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={})
    assert r.status_code == 200, r.text
    assert (r.json()["mode"], r.json()["die"]) == ("advantage", 16)


@pytest.mark.caccia(id="CB-2412", fonte="2024 · Monaco · Raffica di Colpi pag. 102, Passo dell'Ombra e Passo dell'Ombra Migliorato pag. 105, Epitome Elementale pag. 106",
                    zona="regola:2024/monk", voce="regola",
                    copre=["carta:2024/classes/monk.md#Raffica di Colpi / Flurry of Blows (Monaco 2, pag. 102)",
                           "carta:2024/classes/monk.md#Passo dell'Ombra / Shadow Step (Guerriero dell'Ombra 6, pag. 105)",
                           "carta:2024/classes/monk.md#Passo dell'Ombra Migliorato / Improved Shadow Step (Guerriero dell'Ombra 11, pag. 105)",
                           "carta:2024/classes/monk.md#Epitome Elementale / Elemental Epitome (Guerriero degli Elementi 17, pag. 106)",
                           "POST /sessions/{session_id}/encounter/next-turn", "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("caso", ["raffica", "passo_dell_ombra", "colpo_del_passo_migliorato", "passo_distruttivo"])
async def test_gli_effetti_del_turno_finiscono_col_turno_del_monaco(client, test_session_factory, monkeypatch, caso):
    # I colpi dell'azione bonus, il vantaggio «prima della fine del turno», il colpo «subito dopo il teletrasporto» e i +6 m
    # «fino a fine turno»: nel turno del goblin non valgono più
    if caso == "raffica":
        sid, cid = await _monaco_in_scontro(client, test_session_factory, monkeypatch, 2)
        assert (await _use(client, cid, "monk.flurry_of_blows")).status_code == 200
        opzione = "monk.flurry_strike"
    elif caso == "passo_dell_ombra":
        sid, cid = await _monaco_in_scontro(client, test_session_factory, monkeypatch, 6, "Guerriero dell'Ombra")
        assert (await _use(client, cid, "monk.shadow_step", params={"light": "dim_or_dark"})).status_code == 200
        opzione = "monk.shadow_step_advantage"
    elif caso == "colpo_del_passo_migliorato":
        sid, cid = await _monaco_in_scontro(client, test_session_factory, monkeypatch, 11, "Guerriero dell'Ombra")
        assert (await _use(client, cid, "monk.improved_shadow_step")).status_code == 200
        opzione = "monk.shadow_step_strike"
    else:
        sid, cid = await _monaco_in_scontro(client, test_session_factory, monkeypatch, 17, "Guerriero degli Elementi")
        assert (await _use(client, cid, "monk.elemental_attunement")).status_code == 200
        assert (await _use(client, cid, "monk.step_of_the_wind")).status_code == 200
        assert (await _full(client, cid))["computed"]["speed"] == 30 + 25 + 20
        opzione = None
    if opzione:
        assert opzione in await _roll_keys(client, cid, "attack")
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # tocca al primo goblin
    as_user(PLAYER_ID)
    if opzione:
        assert opzione not in await _roll_keys(client, cid, "attack")
    else:
        assert (await _full(client, cid))["computed"]["speed"] == 30 + 25


@pytest.mark.caccia(id="CB-2413", fonte="2024 · Glossario · Incapacitato · pag. 369; Monaco · privilegi ad azione e azione bonus · pag. 102-107",
                    zona="regola:2024/monk", voce="interazione",
                    copre=["carta:2024/general.md#Incapacitated [Condition] (Incapacitato) (pag. 369)",
                           "carta:2024/classes/monk.md#Raffica di Colpi / Flurry of Blows (Monaco 2, pag. 102)",
                           "carta:2024/classes/monk.md#Difesa Paziente / Patient Defense (Monaco 2, pag. 102)",
                           "carta:2024/classes/monk.md#Passo del Vento / Step of the Wind (Monaco 2, pag. 102)",
                           "carta:2024/classes/monk.md#Mano della Guarigione / Hand of Healing (Guerriero della Misericordia 3, pag. 104)",
                           "carta:2024/classes/monk.md#Passo dell'Ombra / Shadow Step (Guerriero dell'Ombra 6, pag. 105)",
                           "carta:2024/classes/monk.md#Manto di Ombre / Cloak of Shadows (Guerriero dell'Ombra 17, pag. 105)",
                           "carta:2024/classes/monk.md#Esplosione Elementale / Elemental Burst (Guerriero degli Elementi 6, pag. 106)",
                           "carta:2024/classes/monk.md#Integrità del Corpo / Wholeness of Body (Guerriero della Mano Aperta 6, pag. 107)",
                           "PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("sottoclasse, livello, chiave, parametri", [
    (None, 2, "monk.flurry_of_blows", {}), (None, 2, "monk.patient_defense_focus", {}), (None, 2, "monk.step_of_the_wind", {}),
    ("mercy", 3, "monk.hand_of_healing", {"mode": "self"}), ("shadow", 6, "monk.shadow_step", {"light": "dim_or_dark"}),
    ("shadow", 17, "monk.cloak_of_shadows", {"light": "dim_or_dark"}), ("elements", 6, "monk.elemental_burst", {"element": "fire"}),
    ("open_hand", 6, "monk.wholeness_of_body", {})])
async def test_un_monaco_incapacitato_non_usa_azioni_ne_azioni_bonus(client, sottoclasse, livello, chiave, parametri):
    cid = await _monaco(client, sottoclasse, livello, wisdom=14)
    await _conditions(client, cid, incapacitated=True)
    assert (await _use(client, cid, chiave, params=parametri)).status_code == 409


@pytest.mark.caccia(id="CB-2414", fonte="2024 · Monaco · Difesa Superiore pag. 103, Sintonia Elementale pag. 106", zona="regola:2024/monk",
                    voce="interazione",
                    copre=["carta:2024/classes/monk.md#Difesa Superiore / Superior Defense (Monaco 18, pag. 103)",
                           "carta:2024/classes/monk.md#Sintonia Elementale / Elemental Attunement (Guerriero degli Elementi 3, pag. 106)",
                           "PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("sottoclasse, livello, chiave, stato", [
    (None, 18, "monk.superior_defense", "superior_defense"), ("elements", 3, "monk.elemental_attunement", "elemental_attunement")])
async def test_un_effetto_che_finisce_da_incapacitato_non_parte_da_incapacitato(client, sottoclasse, livello, chiave, stato):
    # Lo stato finisce quando il monaco diventa incapacitato: avviato mentre lo è già, non deve restare attivo
    cid = await _monaco(client, sottoclasse, livello)
    await _conditions(client, cid, incapacitated=True)
    await _use(client, cid, chiave)
    assert stato not in await _states(client, cid)


@pytest.mark.caccia(id="CB-2415", fonte="2024 · Monaco · Difesa Superiore · pag. 103", zona="regola:2024/monk", voce="ripetizione",
                    copre=["carta:2024/classes/monk.md#Difesa Superiore / Superior Defense (Monaco 18, pag. 103)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_difesa_superiore_ripetuta_non_spende_altri_tre_punti(client):
    # Si attiva a inizio turno per 1 minuto: un secondo invio con lo stato già attivo non costa altri 3 punti
    cid = await _monk24(client, 18)
    assert (await _use(client, cid, "monk.superior_defense")).status_code == 200
    await _use(client, cid, "monk.superior_defense")
    assert await _ki(client, cid) == 18 - 3


@pytest.mark.caccia(id="CB-2416", fonte="2024 · Monaco · Arti Marziali pag. 101, Raffica di Colpi pag. 102; Glossario · Colpo Senz'Armi · pag. 377",
                    zona="regola:2024/monk", voce="regola",
                    copre=["carta:2024/classes/monk.md#Arti Marziali / Martial Arts (Monaco 1, pag. 101)",
                           "carta:2024/classes/monk.md#Raffica di Colpi / Flurry of Blows (Monaco 2, pag. 102)",
                           "carta:2024/general.md#Unarmed Strike (Colpo Senz'Armi) (pag. 377)",
                           "POST /characters/{char_id}/attack/unarmed"])
@pytest.mark.parametrize("via", ["arti_marziali", "raffica"])
async def test_afferrare_o_spingere_con_l_azione_bonus_del_monaco_non_consuma_l_azione_attacco(client, via):
    # Il colpo senz'armi dell'azione bonus e quelli della Raffica possono essere Afferrare o Spingere: non sono attacchi dell'azione Attacco
    cid = await _monk24(client, 2, dexterity=16)
    if via == "arti_marziali":
        assert (await _strike(client, cid)).status_code == 200  # l'unico attacco dell'azione Attacco
        r = await client.post(f"/characters/{cid}/attack/unarmed", json={"effect": "shove", "options": ["monk.martial_arts_bonus"]})
        assert r.status_code == 200, r.text
        turno = await _turn(client, cid)
        assert (turno["bonus_used"], turno["action_attacks"]) == (True, 1)
    else:
        assert (await _use(client, cid, "monk.flurry_of_blows")).status_code == 200
        r = await client.post(f"/characters/{cid}/attack/unarmed", json={"effect": "grapple", "options": ["monk.flurry_strike"]})
        assert r.status_code == 200, r.text
        cariche = (await _states(client, cid))["flurry_of_blows"]["data"]["charges"]
        assert (cariche, (await _turn(client, cid))["action_attacks"]) == (1, 0)


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2418", fonte="2024 · Monaco · Concentrazione del Monaco · pag. 101", zona="regola:2024/monk", voce="limiti",
                    copre=["carta:2024/classes/monk.md#Concentrazione del Monaco / Monk's Focus (Monaco 2, pag. 101)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, atteso", [(1, None), (2, (2, "short_rest")), (19, (19, "short_rest")), (20, (20, "short_rest"))])
async def test_punti_concentrazione_pari_al_livello_e_tornano_col_riposo_breve(client, livello, atteso):
    riga = await _ability(client, await _monk24(client, livello), "monk.ki")
    assert (None if riga is None else (riga["max_uses"], riga["restoration_type"])) == atteso


@pytest.mark.caccia(id="CB-2419", fonte="2024 · Monaco · Arti Marziali · pag. 101", zona="regola:2024/monk", voce="limiti",
                    copre=["carta:2024/classes/monk.md#Arti Marziali / Martial Arts (Monaco 1, pag. 101)",
                           "POST /characters/{char_id}/attack/unarmed"])
@pytest.mark.parametrize("livello, dado", [(1, "1d6"), (4, "1d6"), (5, "1d8"), (10, "1d8"), (11, "1d10"), (16, "1d10"),
                                           (17, "1d12"), (20, "1d12")])
async def test_dado_di_arti_marziali_2024_alle_soglie(client, livello, dado):
    r = await _strike(client, await _monk24(client, livello))
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"] == dado


@pytest.mark.caccia(id="CB-2420", fonte="2024 · Monaco · Movimento Senza Armatura · pag. 102", zona="regola:2024/monk", voce="limiti",
                    copre=["carta:2024/classes/monk.md#Movimento Senza Armatura / Unarmored Movement (Monaco 2, pag. 102)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, velocita", [(1, 30), (2, 40), (5, 40), (6, 45), (9, 45), (10, 50), (13, 50), (14, 55),
                                               (17, 55), (18, 60), (20, 60)])
async def test_movimento_senza_armatura_2024_alle_soglie(client, livello, velocita):
    assert (await _full(client, await _monk24(client, livello)))["computed"]["speed"] == velocita


@pytest.mark.caccia(id="CB-2421", fonte="2024 · Monaco · Colpo Stordente · pag. 103; 2014 · Monaco · Colpo Stordente · pag. 92", zona="regola:2024/monk",
                    voce="edizioni",
                    copre=["carta:2024/classes/monk.md#Colpo Stordente / Stunning Strike (Monaco 5, pag. 103)",
                           "carta:2014/classes/monk.md#Colpo Stordente / Stunning Strike (Monaco 5, pag. 92)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage",
                           "GET /characters/{char_id}/target-effects/{effect_key}"])
@pytest.mark.parametrize("edizione, fine", [("2014", "end"), ("2024", "start")])
async def test_stordito_fino_alla_fine_o_all_inizio_del_prossimo_turno_secondo_l_edizione(client, edizione, fine):
    cid = await _monk24(client, 5, wisdom=16, dexterity=16)  # competenza +3, Saggezza +3: CD 14
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    colpo = await _hit(client, cid)
    assert (await _damage(client, cid, colpo, "monk.stunning_strike")).status_code == 200
    effetto = (await client.get(f"/characters/{cid}/target-effects/monk.stunning_strike")).json()["result"]
    assert (effetto["condition"], effetto["save_ability"], effetto["save_dc"], effetto["ends_at"]) == (
        "stunned", "constitution", 14, {"anchor": "source", "edge": fine, "count": 1})


@pytest.mark.caccia(id="CB-2422", fonte="2024 · Monaco · Metabolismo Prodigioso · pag. 102", zona="regola:2024/monk", voce="interazione",
                    copre=["carta:2024/classes/monk.md#Metabolismo Prodigioso / Uncanny Metabolism (Monaco 2, pag. 102)",
                           "carta:2024/classes/monk.md#Multiclasse: Monaco / Multiclassing: Monk (Capitolo 2, pag. 44)",
                           "POST /characters/{char_id}/dice/initiative", "POST /characters/{char_id}/rest"])
async def test_metabolismo_in_multiclasse_livello_da_monaco_e_un_uso_per_riposo_lungo(client, dadi):
    cid = await _monk24(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 4, "hit_die": 10})
    assert r.status_code == 201, r.text
    await _full_hp(client, cid, 80)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 20})
    ki = await _ability(client, cid, "monk.ki")
    await client.patch(f"/characters/{cid}/abilities/{ki['id']}", json={"uses": 1})
    dadi(5)  # il dado di Arti Marziali del 5° livello da monaco (d8)
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": ["monk.uncanny_metabolism"]})
    assert r.status_code == 200, r.text
    assert ((await _full(client, cid))["current_hit_points"], await _ki(client, cid)) == (20 + 5 + 5, 5)  # livello da monaco, non 9
    assert "monk.uncanny_metabolism" not in await _roll_keys(client, cid, "initiative")
    await _rest(client, cid, "long")
    assert "monk.uncanny_metabolism" in await _roll_keys(client, cid, "initiative")


@pytest.mark.caccia(id="CB-2423", fonte="2024 · Monaco · Deviare Attacchi · pag. 102", zona="regola:2024/monk", voce="annullamento",
                    copre=["carta:2024/classes/monk.md#Deviare Attacchi / Deflect Attacks (Monaco 3, pag. 102)",
                           "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_deviato_rende_la_reazione_e_chiude_il_rinvio(client, dadi):
    cid = await _monk24(client, 5, dexterity=16)
    await _full_hp(client, cid)
    dadi(10)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing",
                                                          "options": ["monk.deflect_attacks"]})
    assert r.status_code == 200 and r.json()["option_result"]["damage_after"] == 0, r.text
    assert "deflected_attack" in await _states(client, cid)
    u = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})
    assert u.status_code == 200, u.text
    assert ((await _turn(client, cid))["reaction_used"], "deflected_attack" in await _states(client, cid)) == (False, False)


@pytest.mark.caccia(id="CB-2424", fonte="2024 · Monaco · Difesa Senza Armatura · pag. 101", zona="regola:2024/monk", voce="regola",
                    copre=["carta:2024/classes/monk.md#Difesa Senza Armatura / Unarmored Defense (Monaco 1, pag. 101)",
                           "PATCH /characters/{char_id}/items/{item_id}"])
async def test_difesa_senza_armatura_2024_destrezza_e_saggezza_senza_scudo(client):
    cid = await _monk24(client, 1, dexterity=16, wisdom=14)
    assert (await _full(client, cid))["ac_breakdown"]["base"] == 10 + 3 + 2
    con_scudo = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert (con_scudo["ac_breakdown"]["base"], con_scudo["unarmored_formula"]) == (10 + 3, None)
