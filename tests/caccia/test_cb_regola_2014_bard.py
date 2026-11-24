"""Controlli della zona regola:2014/bard."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.rules.spellcasting import known_limits, slots_for
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, seed_session, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram

LORE = "Collegio della Sapienza"
VALOR = "Collegio del Valore"
BI = "bard.bardic_inspiration"

# Tabella di classe della carta: livello -> (trucchetti, incantesimi conosciuti, slot dal 1° al 9°)
TABELLA = {
    1: (2, 4, (2,)), 2: (2, 5, (3,)), 3: (2, 6, (4, 2)), 4: (3, 7, (4, 3)), 5: (3, 8, (4, 3, 2)),
    6: (3, 9, (4, 3, 3)), 7: (3, 10, (4, 3, 3, 1)), 8: (3, 11, (4, 3, 3, 2)), 9: (3, 12, (4, 3, 3, 3, 1)),
    10: (4, 14, (4, 3, 3, 3, 2)), 11: (4, 15, (4, 3, 3, 3, 2, 1)), 12: (4, 15, (4, 3, 3, 3, 2, 1)),
    13: (4, 16, (4, 3, 3, 3, 2, 1, 1)), 14: (4, 18, (4, 3, 3, 3, 2, 1, 1)), 15: (4, 19, (4, 3, 3, 3, 2, 1, 1, 1)),
    16: (4, 19, (4, 3, 3, 3, 2, 1, 1, 1)), 17: (4, 20, (4, 3, 3, 3, 2, 1, 1, 1, 1)),
    18: (4, 22, (4, 3, 3, 3, 3, 1, 1, 1, 1)), 19: (4, 22, (4, 3, 3, 3, 3, 2, 1, 1, 1)),
    20: (4, 22, (4, 3, 3, 3, 3, 2, 2, 1, 1)),
}
BONUS_COMPETENZA = {lv: 2 + (lv - 1) // 4 for lv in range(1, 21)}


async def _bardo(client, livello=5, collegio=None, **punteggi) -> int:
    body = {"name": "Bardo", "initial_class": {"class_name": "bard", "level": livello, "subclass": collegio}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _riga(client, cid, chiave) -> dict | None:
    return next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == chiave), None)


async def _stati(client, cid) -> list[str]:
    return [s["key"] for s in (await _scheda(client, cid))["active_states"] or []]


async def _opzioni(client, cid, tiro, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _turno(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _spada(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == "Spada")
    r = await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    return wid


# ---------------------------------------------------------------------------
# Difetti
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1611", fonte="2014 · Bardo · Segreti Magici · pag. 54", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Segreti Magici / Magical Secrets (Bardo 10, pag. 54)",
                           "POST /characters/{char_id}/spells", "GET /characters/{char_id}"])
async def test_un_trucchetto_di_segreti_magici_conta_fra_gli_incantesimi_conosciuti(client):
    cid = await _bardo(client, 10)
    scelta = next(c for c in (await _scheda(client, cid))["pending_choices"] if c.get("group") == "magical_secrets")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Trucchetto altrui", "level": 0, "pick_id": scelta["id"]})
    assert r.status_code == 201, r.text
    limiti = (await _scheda(client, cid))["spellcasting"]["limits"][0]
    assert (limiti["known_count"], limiti["cantrips_count"]) == (1, 0)


@pytest.mark.caccia(id="CB-1612", fonte="2014 · Bardo · Magia da Battaglia · pag. 55", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Magia da Battaglia / Battle Magic (Collegio del Valore 14, pag. 55)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("incantesimo, lancio", [
    ({"casting_time": "1 minuto"}, {"slot_level": 1}),
    ({"casting_time": "1 azione", "is_ritual": True}, {"as_ritual": True}),
], ids=["tempo_di_lancio_un_minuto", "rituale"])
@pytest.mark.xfail(strict=True, reason="CB-1612: difforme dal manuale, confermato")
async def test_magia_da_battaglia_solo_dopo_un_incantesimo_lanciato_con_l_azione(client, incantesimo, lancio):
    cid = await _bardo(client, 14, VALOR)
    spada = await _spada(client, cid)
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Incantesimo lento", "level": 1, "class_id": classe, **incantesimo})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json=lancio)
    assert r.status_code == 200, r.text
    assert "bard.battle_magic" not in await _opzioni(client, cid, "attack", item_id=spada)


@pytest.mark.caccia(id="CB-1613", fonte="2014 · Bardo · Ispirazione Bardica, Controfascino, Parole Taglienti · pag. 53-54; Condizioni · Incapacitato · pag. 291",
                    zona="regola:2014/bard", voce="interazione",
                    copre=["carta:2014/classes/bard.md#Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 53)",
                           "carta:2014/classes/bard.md#Controfascino / Countercharm (Bardo 6, pag. 54)",
                           "carta:2014/classes/bard.md#Parole Taglienti / Cutting Words (Collegio della Sapienza 3, pag. 54)",
                           "carta:2014/general.md#Incapacitato / Incapacitated (pag. 291)",
                           "PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("chiave, slot", [
    ("bard.bardic_inspiration", "bonus_used"), ("bard.countercharm", "action_used"), ("bard.cutting_words", "reaction_used"),
], ids=["ispirazione_azione_bonus", "controfascino_azione", "parole_taglienti_reazione"])
@pytest.mark.xfail(strict=True, reason="CB-1613: difforme dal manuale, confermato")
async def test_un_bardo_incapacitato_non_usa_privilegi_che_costano_azione_o_reazione(client, chiave, slot):
    cid = await _bardo(client, 6, LORE, charisma=16)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/features/{chiave}/use", json={})
    assert r.status_code == 409, r.text
    assert (await _riga(client, cid, BI))["uses"] == 3
    assert await _stati(client, cid) == [] and (await _turno(client, cid))[slot] is False


@pytest.mark.caccia(id="CB-1614", fonte="2014 · Bardo · Controfascino · pag. 54", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Controfascino / Countercharm (Bardo 6, pag. 54)",
                           "POST /sessions/{session_id}/encounter/start", "POST /sessions/{session_id}/encounter/next-turn",
                           "POST /characters/{char_id}/features/{feature_key}/use", "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-1614: difforme dal manuale, confermato")
async def test_controfascino_finisce_con_la_fine_del_turno_successivo_del_bardo(client, test_session_factory, monkeypatch, come_utente):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)  # ordine: PG, goblin, goblin
    come_utente(GM_ID)
    pc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    cid = pc["character_id"]
    come_utente(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 6, "hit_die": 8})).status_code == 201
    assert (await client.post(f"/characters/{cid}/features/bard.countercharm/use", json={})).status_code == 200
    for _ in range(3):  # i due goblin, poi il turno successivo del bardo
        come_utente(GM_ID)
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    come_utente(PLAYER_ID)
    assert "countercharm" in await _stati(client, cid)  # dura per tutto il turno successivo
    come_utente(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # finisce il turno del bardo
    come_utente(PLAYER_ID)
    assert "countercharm" not in await _stati(client, cid)
    assert "bard.countercharm" not in await _opzioni(client, cid, "save", ability="wisdom")


@pytest.mark.caccia(id="CB-1615", fonte="2014 · Bardo · Ispirazione Superiore · pag. 54", zona="regola:2014/bard", voce="interazione",
                    copre=["carta:2014/classes/bard.md#Ispirazione Superiore / Superior Inspiration (Bardo 20, pag. 54)",
                           "POST /sessions/{session_id}/encounter/start", "PATCH /characters/{char_id}/abilities/{ability_id}"])
@pytest.mark.xfail(strict=True, reason="CB-1615: difforme dal manuale, confermato")
async def test_ispirazione_superiore_anche_con_l_iniziativa_tirata_dal_master(client, test_session_factory, monkeypatch, come_utente):
    install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    come_utente(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 20, "hit_die": 8})).status_code == 201
    riga = await _riga(client, cid, BI)
    assert (await client.patch(f"/characters/{cid}/abilities/{riga['id']}", json={"uses": 0})).status_code == 200
    come_utente(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})).status_code == 201
    r = await client.post(f"/sessions/{sid}/encounter/combatants",
                          json={"name": "Goblin", "count": 1, "initiative_mod": 2, "max_hp": 7, "ac": 15})
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/sessions/{sid}/encounter/start", json={"auto_roll_missing": True})
    assert r.status_code == 200, r.text
    come_utente(PLAYER_ID)
    assert (await _riga(client, cid, BI))["uses"] == 1


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1616", fonte="2014 · Bardo · Tabella di classe e Incantesimi · pag. 52-53", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Incantesimi / Spellcasting (Bardo 1, pag. 52)"])
@pytest.mark.parametrize("livello", list(range(1, 21)))
def test_trucchetti_conosciuti_e_slot_seguono_la_tabella(livello):
    trucchetti, conosciuti, slot = TABELLA[livello]
    limiti = known_limits("2014", "bard", livello)
    assert (limiti.cantrips, limiti.spells) == (trucchetti, conosciuti)
    riga = SimpleNamespace(class_name="bard", level=livello, subclass_key=None, spellcasting_ability="charisma", subclass=None)
    assert slots_for("2014", [riga]).regular == {i + 1: n for i, n in enumerate(slot)}


@pytest.mark.caccia(id="CB-1617", fonte="2014 · Bardo · Tabella di classe · pag. 52", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Incantesimi / Spellcasting (Bardo 1, pag. 52)"])
def test_progressione_del_frontend_segue_la_tabella():
    dati = Path(__file__).resolve().parents[2] / "webapp/src/data/class-progression.json"
    righe = json.loads(dati.read_text(encoding="utf-8"))["Bardo"]
    assert len(righe) == 20
    for livello, riga in enumerate(righe, 1):
        attesi = TABELLA[livello][2]
        assert riga["proficiency_bonus"] == BONUS_COMPETENZA[livello], livello
        assert riga["spell_slots"] == [*attesi, *[0] * (9 - len(attesi))], livello


@pytest.mark.caccia(id="CB-1618", fonte="2014 · Bardo · Ispirazione Bardica · pag. 53", zona="regola:2014/bard", voce="limiti",
                    copre=["carta:2014/classes/bard.md#Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 53)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("livello, dado", [(1, 6), (4, 6), (5, 8), (9, 8), (10, 10), (14, 10), (15, 12), (20, 12)])
async def test_dado_di_ispirazione_bardica_per_livello(client, livello, dado):
    cid = await _bardo(client, livello, charisma=16)
    r = await client.post(f"/characters/{cid}/features/{BI}/use", json={})
    assert r.status_code == 200, r.text
    stato = r.json()["state"]
    assert (stato["data"]["die"], stato["rounds_left"]) == (dado, 100)
    assert (await _turno(client, cid))["bonus_used"] is True


@pytest.mark.caccia(id="CB-1619", fonte="2014 · Bardo · Fonte di Ispirazione · pag. 54", zona="regola:2014/bard", voce="limiti",
                    copre=["carta:2014/classes/bard.md#Fonte di Ispirazione / Font of Inspiration (Bardo 5, pag. 54)",
                           "carta:2014/classes/bard.md#Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 53)",
                           "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("livello, dopo_il_breve", [(4, 2), (5, 3)])
async def test_ispirazione_bardica_torna_col_riposo_breve_solo_dal_quinto(client, livello, dopo_il_breve):
    cid = await _bardo(client, livello, charisma=16)
    assert (await _riga(client, cid, BI))["max_uses"] == 3
    assert (await client.post(f"/characters/{cid}/features/{BI}/use", json={})).status_code == 200
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _riga(client, cid, BI))["uses"] == dopo_il_breve
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})).status_code == 200
    assert (await _riga(client, cid, BI))["uses"] == 3


@pytest.mark.caccia(id="CB-1620", fonte="2014 · Bardo · Canto di Riposo · pag. 54", zona="regola:2014/bard", voce="limiti",
                    copre=["carta:2014/classes/bard.md#Canto di Riposo / Song of Rest (Bardo 2, pag. 54)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/hit_dice/spend"])
@pytest.mark.parametrize("livello, dado", [(2, 6), (8, 6), (9, 8), (12, 8), (13, 10), (16, 10), (17, 12), (20, 12)])
async def test_canto_di_riposo_un_dado_extra_per_livello(client, dadi, livello, dado):
    cid = await _bardo(client, livello)
    assert (await client.post(f"/characters/{cid}/features/bard.song_of_rest/use", json={})).status_code == 200
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 200})  # PF mancanti: la cura non si tronca
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    dadi(dado)
    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": classe, "count": 1, "rolls": [3]})
    assert r.status_code == 200, r.text
    assert (r.json()["song_die"], r.json()["song_rolls"], r.json()["healed"]) == (dado, [dado], 3 + dado)


@pytest.mark.caccia(id="CB-1621", fonte="2014 · Bardo · Factotum · pag. 54; 2024 · Bardo · Factotum · pag. 60", zona="regola:2014/bard",
                    voce="edizioni",
                    copre=["carta:2014/classes/bard.md#Factotum / Jack of All Trades (Bardo 2, pag. 54)",
                           "carta:2024/classes/bard.md#Factotum / Jack of All Trades (Bardo 2, pag. 60)",
                           "POST /characters/{char_id}/ability_checks/{ability}/roll", "POST /characters/{char_id}/dice/initiative",
                           "POST /characters/{char_id}/skills/{skill_name}/roll"])
@pytest.mark.parametrize("edizione, pura, iniziativa", [("2014", 1, 1), ("2024", 0, 0)])
async def test_factotum_sulle_prove_pure_e_sull_iniziativa_solo_nel_2014(client, edizione, pura, iniziativa):
    cid = await _bardo(client, 2, dexterity=10)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    prova = (await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 10})).json()
    tiro = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    abilita = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()
    ts = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10})).json()
    assert (prova["bonus"], tiro["bonus"], abilita["bonus"], ts["bonus"]) == (pura, iniziativa, 1, 0)


@pytest.mark.caccia(id="CB-1622", fonte="2014 · Bardo · Parole Taglienti · pag. 54", zona="regola:2014/bard", voce="annullamento",
                    copre=["carta:2014/classes/bard.md#Parole Taglienti / Cutting Words (Collegio della Sapienza 3, pag. 54)",
                           "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_ridotto_da_parole_taglienti_rimborsa_uso_e_reazione(client, dadi):
    cid = await _bardo(client, 5, LORE, charisma=16)
    pf = (await _scheda(client, cid))["current_hit_points"]
    dadi(5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 12, "options": ["bard.cutting_words_self"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == pf - 7  # il d8 di Ispirazione (5° livello) toglie 5
    assert (await _riga(client, cid, BI))["uses"] == 2 and (await _turno(client, cid))["reaction_used"] is True
    assert (await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})).status_code == 200
    assert (await _scheda(client, cid))["current_hit_points"] == pf
    assert (await _riga(client, cid, BI))["uses"] == 3 and (await _turno(client, cid))["reaction_used"] is False


@pytest.mark.caccia(id="CB-1623", fonte="2014 · Bardo · Incantesimi · pag. 52", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Incantesimi / Spellcasting (Bardo 1, pag. 52)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, carisma, cd, attacco", [(1, 16, 13, 5), (20, 20, 19, 11)])
async def test_cd_e_attacco_degli_incantesimi_col_carisma(client, livello, carisma, cd, attacco):
    cid = await _bardo(client, livello, charisma=carisma, intelligence=18, wisdom=18)
    [incantatore] = (await _scheda(client, cid))["spellcasting"]["casters"]
    assert (incantatore["ability"], incantatore["save_dc"], incantatore["attack_bonus"]) == ("charisma", cd, attacco)
