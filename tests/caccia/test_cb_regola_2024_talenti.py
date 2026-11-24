"""Controlli della zona regola:2024/talenti."""
import pytest

from core.db.models import Ability

BASE = {"strength": 14, "dexterity": 14, "constitution": 14, "intelligence": 13, "wisdom": 13, "charisma": 13}


async def _pg(client, classe="fighter", livello=4, sottoclasse=None, **punteggi) -> dict:
    iniziale = {"class_name": classe, "level": livello, **({"subclass": sottoclasse} if sottoclasse else {})}
    r = await client.post("/characters", json={"name": "Talenti 2024", "rules_edition": "2024",
                                               "ability_scores": {**BASE, **punteggi}, "initial_class": iniziale})
    assert r.status_code == 201, r.text
    return r.json()


async def _prendi(client, cid, chiave, caratteristica=None):
    return await client.post(f"/characters/{cid}/feats", json={"feat_key": chiave, "ability": caratteristica})


async def _preso(client, cid, chiave, caratteristica=None) -> dict:
    r = await _prendi(client, cid, chiave, caratteristica)
    assert r.status_code == 201, r.text
    return r.json()


def _righe(body, chiave) -> list[dict]:
    return [a for a in body["abilities"] if a["feature_key"] == f"feat.{chiave}"]


async def _completa(client, cid, riga_id, opzioni, incantesimi=()):
    return await client.put(f"/characters/{cid}/feats/{riga_id}/options", json={"options": opzioni, "spells": list(incantesimi)})


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _opzioni(client, cid, tiro, **query) -> list[dict]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return r.json()


async def _usi_a_zero(factory, riga_id) -> None:
    async with factory() as s:
        (await s.get(Ability, riga_id)).uses = 0
        await s.commit()


def _punteggio(body, nome) -> int:
    return next(s["value"] for s in body["ability_scores"] if s["name"] == nome)


async def _lancia_gratis(client, cid, sid):
    corpo = {"free_cast": True}
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json=corpo)
    dettaglio = r.json().get("detail") if r.status_code == 409 else None
    if isinstance(dettaglio, dict) and dettaglio.get("code") == "cast_confirm":
        r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={**corpo, "confirm": dettaglio["warnings"]})
    return r


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3461", fonte="2024 · Talenti · Doni epici · pag. 210; Guerriero · Dono Epico · pag. 92", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Robusto / Tough (pag. 202) - Origine",
                           "carta:2024/classes/fighter.md#Dono Epico / Epic Boon (Guerriero 19, pag. 92)",
                           "POST /characters/{char_id}/choices/{choice_id}/resolve"])
@pytest.mark.xfail(strict=True, reason="CB-3461: difforme dal manuale, confermato")
async def test_il_dono_epico_del_19_ammette_un_altro_talento_per_cui_si_e_qualificati(client):
    ch = await _pg(client, "fighter", 1)
    r = await client.patch(f"/characters/{ch['id']}/xp", json={"set": 305000})
    assert r.status_code == 200, r.text
    scelta = next(c for c in r.json()["pending_choices"] if c["kind"] == "epic_boon")
    url = f"/characters/{ch['id']}/choices/{scelta['id']}/resolve"
    risposte = [await client.post(url, json={"kind": "epic_boon", "feat_key": "2024_tough"})]
    if risposte[0].status_code != 200:  # qualunque delle due forme di risposta, purché il talento entri
        risposte.append(await client.post(url, json={"kind": "feat", "feat_key": "2024_tough"}))
    assert risposte[-1].status_code == 200, [x.text for x in risposte]
    assert _righe(risposte[-1].json(), "2024_tough")


@pytest.mark.caccia(id="CB-3462", fonte="2024 · Talenti · Incantatore da guerra · pag. 209; Guerriero e Ladro · Incantesimi della sottoclasse", zona="regola:2024/talenti",
                    voce="interazione",
                    copre=["carta:2024/feats.md#Incantatore da guerra / War Caster (pag. 209) - Generale (livello 4+, Incantesimi o Magia del Patto)",
                           "POST /characters/{char_id}/feats"])
@pytest.mark.parametrize(("classe", "sottoclasse", "chiave"), [("fighter", "Cavaliere Mistico", "eldritch_knight"),
                                                              ("rogue", "Mistificatore Arcano", "arcane_trickster")])
@pytest.mark.xfail(strict=True, reason="CB-3462: difforme dal manuale, confermato")
async def test_il_terzo_incantatore_soddisfa_il_prerequisito_incantesimi(client, classe, sottoclasse, chiave):
    ch = await _pg(client, classe, 4, sottoclasse)
    assert ch["classes"][0]["subclass_key"] == chiave, ch["classes"]
    r = await _prendi(client, ch["id"], "2024_war_caster", "intelligence")
    assert r.status_code == 201, r.text


@pytest.mark.caccia(id="CB-3463", fonte="2024 · Talenti · Dono del Richiamo degli incantesimi · pag. 211", zona="regola:2024/talenti", voce="limiti",
                    copre=["carta:2024/feats.md#Dono del Richiamo degli incantesimi / Boon of Spell Recall (pag. 211) - Dono epico (livello 19+, privilegio Incantesimi)",
                           "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3463: difforme dal manuale, confermato")
async def test_il_dono_del_richiamo_non_si_prende_con_la_sola_magia_del_patto(client):
    mago = await _pg(client, "wizard", 19)
    assert (await _prendi(client, mago["id"], "2024_boon_spell_recall", "intelligence")).status_code == 201
    warlock = await _pg(client, "warlock", 19)
    r = await _prendi(client, warlock["id"], "2024_boon_spell_recall", "charisma")
    assert r.status_code == 422, r.text


@pytest.mark.caccia(id="CB-3464", fonte="2024 · Talenti · Armatura media · pag. 205", zona="regola:2024/talenti", voce="edizioni",
                    copre=["carta:2024/feats.md#Armatura media / Moderately Armored (pag. 205) - Generale (livello 4+, Addestramento con armature leggere)",
                           "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3464: difforme dal manuale, confermato")
async def test_armatura_media_2024_non_addestra_agli_scudi(client):
    ch = await _pg(client, "rogue", 4)
    assert not any("scud" in a.lower() or "shield" in a.lower() for a in ch["general_proficiencies"]["armor"])
    body = await _preso(client, ch["id"], "2024_moderately_armored", "dexterity")
    armature = [a.lower() for a in body["general_proficiencies"]["armor"]]
    assert any("medi" in a for a in armature), armature
    assert not any("scud" in a or "shield" in a for a in armature), armature


@pytest.mark.caccia(id="CB-3465", fonte="2024 · Talenti · Attaccabrighe da taverna · pag. 202", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Attaccabrighe da taverna / Tavern Brawler (pag. 202) - Origine", "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3465: difforme dal manuale, confermato")
async def test_attaccabrighe_da_taverna_da_competenza_nelle_armi_improvvisate(client):
    ch = await _pg(client, "wizard", 1)
    body = await _preso(client, ch["id"], "2024_tavern_brawler")
    armi = [w.lower() for w in body["general_proficiencies"]["weapons"]]
    assert any("improvvis" in w or "improvised" in w for w in armi), armi


@pytest.mark.caccia(id="CB-3466", fonte="2024 · Talenti · Avvelenatore · pag. 206", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Avvelenatore / Poisoner (pag. 206) - Generale (livello 4+)", "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3466: difforme dal manuale, confermato")
async def test_avvelenatore_da_competenza_nel_kit_da_avvelenatore(client):
    ch = await _pg(client, "fighter", 4)
    body = await _preso(client, ch["id"], "2024_poisoner", "dexterity")
    assert body["tool_proficiencies"].get("poisoners_kit"), body["tool_proficiencies"]


@pytest.mark.caccia(id="CB-3467", fonte="2024 · Talenti · Artigiano · pag. 200", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Artigiano / Crafter (pag. 200) - Origine", "PUT /characters/{char_id}/feats/{ability_id}/options"])
@pytest.mark.xfail(strict=True, reason="CB-3467: difforme dal manuale, confermato")
async def test_artigiano_sceglie_solo_strumenti_della_tabella_creazione_rapida(client):
    ch = await _pg(client, "fighter", 1)
    riga = _righe(await _preso(client, ch["id"], "2024_crafter"), "2024_crafter")[0]
    fuori = await _completa(client, ch["id"], riga["id"], {"tools": ["alchemists_supplies", "carpenters_tools", "smiths_tools"]})
    assert fuori.status_code == 422, fuori.text
    dentro = await _completa(client, ch["id"], riga["id"], {"tools": ["carpenters_tools", "smiths_tools", "weavers_tools"]})
    assert dentro.status_code == 200, dentro.text


@pytest.mark.caccia(id="CB-3468", fonte="2024 · Talenti · Maestro d'armi · pag. 209", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Maestro d'armi / Weapon Master (pag. 209) - Generale (livello 4+)",
                           "PUT /characters/{char_id}/feats/{ability_id}/options"])
@pytest.mark.xfail(strict=True, reason="CB-3468: difforme dal manuale, confermato")
async def test_maestro_d_armi_sceglie_solo_un_arma_in_cui_si_e_competenti(client):
    ch = await _pg(client, "wizard", 4)
    riga = _righe(await _preso(client, ch["id"], "2024_weapon_master", "strength"), "2024_weapon_master")[0]
    spadone = await _completa(client, ch["id"], riga["id"], {"weapon_mastery": ["greatsword"]})  # il mago 2024 non ha le armi da guerra
    assert spadone.status_code == 422, spadone.text
    pugnale = await _completa(client, ch["id"], riga["id"], {"weapon_mastery": ["dagger"]})
    assert pugnale.status_code == 200, pugnale.text


@pytest.mark.caccia(id="CB-3469", fonte="2024 · Talenti · Dono del Fato · pag. 210", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Dono del Fato / Boon of Fate (pag. 210) - Dono epico", "POST /characters/{char_id}/dice/initiative"])
@pytest.mark.xfail(strict=True, reason="CB-3469: difforme dal manuale, confermato")
async def test_il_dono_del_fato_torna_quando_tiri_l_iniziativa(client, test_session_factory):
    ch = await _pg(client, "fighter", 19)
    riga = _righe(await _preso(client, ch["id"], "2024_boon_fate", "charisma"), "2024_boon_fate")[0]
    await _usi_a_zero(test_session_factory, riga["id"])
    prima = [o["key"] for o in await _opzioni(client, ch["id"], "initiative") if "boon_fate" in o["key"] and o["phase"] == "before"]
    r = await client.post(f"/characters/{ch['id']}/dice/initiative", json={"die": 10, "options": prima})
    assert r.status_code == 200, r.text
    assert _righe(await _scheda(client, ch["id"]), "2024_boon_fate")[0]["uses"] == 1


@pytest.mark.caccia(id="CB-3470", fonte="2024 · Talenti · Toccato dalle fate · pag. 204", zona="regola:2024/talenti", voce="limiti",
                    copre=["carta:2024/feats.md#Toccato dalle fate / Fey-Touched (pag. 204) - Generale (livello 4+)",
                           "PUT /characters/{char_id}/feats/{ability_id}/options", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3470: difforme dal manuale, confermato")
async def test_toccato_dalle_fate_passo_velato_gratis_una_sola_volta(client):
    ch = await _pg(client, "fighter", 4)
    cid = ch["id"]
    riga = _righe(await _preso(client, cid, "2024_fey_touched", "intelligence"), "2024_fey_touched")[0]
    charme = {"name": "Charme su Persone", "level": 1, "srd_index": "charm-person", "casting_time": "1 azione", "school": "enchantment"}
    assert (await _completa(client, cid, riga["id"], {}, [charme])).status_code == 200
    passo = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "misty-step")
    primo = await _lancia_gratis(client, cid, passo["id"])
    assert primo.status_code == 200, primo.text
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    secondo = await _lancia_gratis(client, cid, passo["id"])
    assert secondo.status_code == 409, secondo.text  # il lancio gratuito rimasto è quello di Charme su Persone


@pytest.mark.caccia(id="CB-3471", fonte="2024 · Talenti · Dono dello Spirito della notte · pag. 211", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Dono dello Spirito della notte / Boon of the Night Spirit (pag. 211) - Dono epico",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3471: difforme dal manuale, confermato")
async def test_fondersi_con_le_ombre_rende_invisibile(client):
    ch = await _pg(client, "fighter", 19)
    await _preso(client, ch["id"], "2024_boon_night_spirit", "dexterity")
    r = await client.post(f"/characters/{ch['id']}/features/feat.2024_boon_night_spirit/use", json={})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, ch["id"]))["conditions"].get("invisible"), (await _scheda(client, ch["id"]))["conditions"]


@pytest.mark.caccia(id="CB-3472", fonte="2024 · Talenti · Regole comuni (+1 fino a 20) · pag. 199; Attore · pag. 202", zona="regola:2024/talenti", voce="limiti",
                    copre=["carta:2024/feats.md#Attore / Actor (pag. 202) - Generale (livello 4+, Carisma 13+)", "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-3472: difforme dal manuale, confermato")
async def test_un_talento_con_piu_uno_si_prende_anche_con_la_caratteristica_a_20(client):
    ch = await _pg(client, "fighter", 4, charisma=20)
    r = await _prendi(client, ch["id"], "2024_actor", "charisma")
    assert r.status_code == 201, r.text
    assert _punteggio(r.json(), "charisma") == 20 and _righe(r.json(), "2024_actor")


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3473", fonte="2024 · Talenti · Fortunato · pag. 201; Dono del Fato · pag. 210", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Fortunato / Lucky (pag. 201) - Origine",
                           "carta:2024/feats.md#Dono del Fato / Boon of Fate (pag. 210) - Dono epico",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize(("livello", "chiave", "caratteristica"), [(1, "2024_lucky", None), (19, "2024_boon_fate", "charisma")])
async def test_una_prova_di_caratteristica_senza_abilita_e_un_test_d20(client, livello, chiave, caratteristica):
    ch = await _pg(client, "fighter", livello)
    await _preso(client, ch["id"], chiave, caratteristica)
    assert f"feat.{chiave}" in [o["key"] for o in await _opzioni(client, ch["id"], "skill", skill="athletics", ability="strength")]
    prova = [o["key"] for o in await _opzioni(client, ch["id"], "ability", ability="strength")]
    assert f"feat.{chiave}" in prova, prova


@pytest.mark.caccia(id="CB-3474", fonte="2024 · Talenti · Robusto · pag. 202", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Robusto / Tough (pag. 202) - Origine", "POST /characters/{char_id}/feats"])
async def test_robusto_due_punti_ferita_per_livello(client):
    ch = await _pg(client, "fighter", 5)
    body = await _preso(client, ch["id"], "2024_tough")
    assert body["computed"]["hp_max_effective"] == ch["computed"]["hp_max_effective"] + 10


@pytest.mark.caccia(id="CB-3475", fonte="2024 · Talenti · Durevole · pag. 203", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Durevole / Durable (pag. 203) - Generale (livello 4+)", "POST /characters/{char_id}/death_saves/roll"])
async def test_durevole_vantaggio_ai_tiri_salvezza_contro_la_morte(client):
    ch = await _pg(client, "fighter", 4)
    body = await _preso(client, ch["id"], "2024_durable", "constitution")
    assert _punteggio(body, "constitution") == 15
    assert (await client.patch(f"/characters/{ch['id']}/hp", json={"op": "set_current", "value": 0})).status_code == 200
    r = await client.post(f"/characters/{ch['id']}/death_saves/roll", json={"dice": [3, 15]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage" and r.json()["outcome"] == "success"


@pytest.mark.caccia(id="CB-3476", fonte="2024 · Talenti · Fortunato · pag. 201", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Fortunato / Lucky (pag. 201) - Origine", "POST /characters/{char_id}/rest"])
async def test_fortunato_punti_pari_alla_competenza_col_riposo_lungo(client, test_session_factory):
    ch = await _pg(client, "fighter", 5)
    riga = _righe(await _preso(client, ch["id"], "2024_lucky"), "2024_lucky")[0]
    assert riga["max_uses"] == 3
    await _usi_a_zero(test_session_factory, riga["id"])
    assert (await client.post(f"/characters/{ch['id']}/rest", json={"rest_type": "short"})).status_code == 200
    assert _righe(await _scheda(client, ch["id"]), "2024_lucky")[0]["uses"] == 0
    assert (await client.post(f"/characters/{ch['id']}/rest", json={"rest_type": "long", "confirm_early": True})).status_code == 200
    assert _righe(await _scheda(client, ch["id"]), "2024_lucky")[0]["uses"] == 3


@pytest.mark.caccia(id="CB-3477", fonte="2024 · Talenti · Capo ispiratore · pag. 204", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Capo ispiratore / Inspiring Leader (pag. 204) - Generale (livello 4+, Saggezza o Carisma 13+)",
                           "POST /characters/{char_id}/rest"])
async def test_capo_ispiratore_livello_piu_caratteristica_aumentata_al_riposo_lungo(client):
    ch = await _pg(client, "fighter", 5, charisma=15)
    await _preso(client, ch["id"], "2024_inspiring_leader", "charisma")  # 15 -> 16: +3
    r = await client.post(f"/characters/{ch['id']}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == 5 + 3


@pytest.mark.caccia(id="CB-3478", fonte="2024 · Talenti · Doni epici (+1 fino a 30) · pag. 210", zona="regola:2024/talenti", voce="limiti",
                    copre=["carta:2024/feats.md#Dono della Forza d'animo / Boon of Fortitude (pag. 210) - Dono epico", "POST /characters/{char_id}/feats"])
async def test_un_dono_epico_porta_la_caratteristica_oltre_20(client):
    ch = await _pg(client, "fighter", 19, strength=20)
    body = await _preso(client, ch["id"], "2024_boon_fortitude", "strength")
    assert _punteggio(body, "strength") == 21
    assert body["computed"]["hp_max_effective"] == ch["computed"]["hp_max_effective"] + 40


@pytest.mark.caccia(id="CB-3479", fonte="2024 · Talenti · Resiliente · pag. 206", zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/feats.md#Resiliente / Resilient (pag. 206) - Generale (livello 4+)", "POST /characters/{char_id}/feats"])
async def test_resiliente_solo_su_un_tiro_salvezza_senza_competenza(client):
    ch = await _pg(client, "fighter", 4)
    gia = await _prendi(client, ch["id"], "2024_resilient", "strength")  # il guerriero è già competente nei TS di Forza
    assert gia.status_code == 422, gia.text
    body = await _preso(client, ch["id"], "2024_resilient", "wisdom")
    assert _punteggio(body, "wisdom") == 14 and body["saving_throws"]["wisdom"] is True


@pytest.mark.caccia(id="CB-3480", fonte="2024 · Talenti · Mente acuta · pag. 205", zona="regola:2024/talenti", voce="ripetizione",
                    copre=["carta:2024/feats.md#Mente acuta / Keen Mind (pag. 205) - Generale (livello 4+, Intelligenza 13+)",
                           "PUT /characters/{char_id}/feats/{ability_id}/options"])
async def test_mente_acuta_completata_due_volte_non_diventa_maestria(client):
    ch = await _pg(client, "fighter", 4)
    riga = _righe(await _preso(client, ch["id"], "2024_keen_mind", "intelligence"), "2024_keen_mind")[0]
    primo = await _completa(client, ch["id"], riga["id"], {"skill": "arcana"})
    assert primo.status_code == 200, primo.text
    assert primo.json()["skills"]["arcana"] is True
    secondo = await _completa(client, ch["id"], riga["id"], {"skill": "arcana"})
    assert secondo.status_code == 409, secondo.text
    assert (await _scheda(client, ch["id"]))["skills"]["arcana"] is True
