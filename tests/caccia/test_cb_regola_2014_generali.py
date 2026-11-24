"""Controlli della zona regola:2014/generali (parte generali: multiclasse, caratteristiche, avventura e riposi)."""
from types import SimpleNamespace

import pytest

from core.data.spell_slots import compute_regular_slots
from core.db.models import GameSession, SessionParticipant, SessionRole, SessionStatus

GM, GIOCATORE, ADESSO = 1234, 5678, "2026-06-09T10:00:00"


async def _pg(client, classe="fighter", livello=1, edizione="2014", sottoclasse=None, **punteggi) -> int:
    r = await client.post("/characters", json={"name": "P", "rules_edition": edizione, "initial_class": {
        "class_name": classe, "level": livello, "subclass": sottoclasse}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _classe(client, cid, nome, livello, sottoclasse=None) -> None:
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": nome, "level": livello, "subclass": sottoclasse})
    assert r.status_code == 201, r.text


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _impostazioni(client, cid, **valori) -> None:
    attuali = (await _scheda(client, cid))["settings"] or {}
    r = await client.patch(f"/characters/{cid}", json={"settings": {**attuali, **valori}})
    assert r.status_code == 200, r.text


async def _serata(fabbrica, cid) -> int:
    """Serata attiva con il GM e il personaggio seduto."""
    async with fabbrica() as s:
        serata = GameSession(code="GEN014", gm_user_id=GM, status=SessionStatus.ACTIVE, created_at=ADESSO, last_activity_at=ADESSO)
        s.add(serata)
        await s.flush()
        s.add(SessionParticipant(session_id=serata.id, user_id=GM, role=SessionRole.GAME_MASTER, joined_at=ADESSO))
        s.add(SessionParticipant(session_id=serata.id, user_id=GIOCATORE, character_id=cid, role=SessionRole.PLAYER,
                                 display_name="Druido", joined_at=ADESSO))
        await s.commit()
        return serata.id


async def _spendi_tutti_i_dadi_vita(client, cid) -> None:
    for c in (await _scheda(client, cid))["classes"]:
        r = await client.post(f"/characters/{cid}/hit_dice/spend",
                              json={"class_id": c["id"], "count": c["level"], "rolls": [1] * c["level"]})
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2761", fonte="2014 · Caratteristiche · Forza, Variante: Ingombro (si ignora la colonna Forza delle armature) · pag. 176",
                    zona="regola:2014/generali", voce="interazione",
                    copre=["carta:2014/general.md#Forza / Strength (pag. 175-176)",
                           "carta:2014/equipment.md#Armature / Armor (pag. 145)",
                           "PATCH /characters/{char_id}", "GET /characters/{char_id}"])
@pytest.mark.xfail(strict=True, reason="CB-2761: difforme dal manuale, confermato")
async def test_con_la_variante_dell_ingombro_l_armatura_pesante_non_toglie_velocita_per_la_forza(client):
    cid = await _pg(client, "fighter", 1)  # Forza 10, addestrato alle armature pesanti
    senza_armatura = (await _scheda(client, cid))["computed"]["speed"]
    await _impostazioni(client, cid, encumbrance_variant=True)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Corazza a strisce", "item_type": "armor", "is_equipped": True, "weight": 1,
        "item_metadata": {"armor_type": "heavy", "ac_value": 17, "strength_req": 15}})
    assert r.status_code == 201, r.text
    scheda = await _scheda(client, cid)
    assert scheda["encumbrance_level"] in (None, "none")  # 1 lb: nessun ingombro
    # con la variante vale solo il peso portato: la Forza richiesta dall'armatura non toglie 3 m
    assert scheda["computed"]["speed"] == senza_armatura


@pytest.mark.caccia(id="CB-2762", fonte="2014 · Caratteristiche · Destrezza, Iniziativa (prova di Destrezza) · pag. 177; Druido · Forma Selvatica · pag. 66",
                    zona="regola:2014/generali", voce="interazione",
                    copre=["carta:2014/general.md#Destrezza / Dexterity (pag. 176-177)",
                           "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)",
                           "POST /sessions/{session_id}/encounter/combatants/{combatant_id}/initiative",
                           "POST /characters/{char_id}/dice/initiative"])
@pytest.mark.xfail(strict=True, reason="CB-2762: difforme dal manuale, confermato")
async def test_iniziativa_dello_scontro_in_forma_selvatica_usa_la_destrezza_della_bestia(client, come_utente, test_session_factory):
    come_utente(GIOCATORE)
    cid = await _pg(client, "druid", 2, dexterity=10)
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Lupo", "max_hp": 11, "armor_class": 13,
        "statblock": {"size": "Medium", "type": "beast", "challenge_rating": 0.25, "speed": {"walk_ft": 40}, "actions": [],
                      "abilities": {"str": 12, "dex": 18, "con": 12}}})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/companions/{r.json()['id']}/activate", json={})
    assert r.status_code == 200, r.text
    fuori = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})
    assert fuori.json()["total"] == 14  # il tiro della scheda usa già la Destrezza 18 del lupo
    sid = await _serata(test_session_factory, cid)
    come_utente(GM)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    pg = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    come_utente(GIOCATORE)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pg['id']}/initiative", json={"die": 10})
    assert r.status_code == 200, r.text
    # in forma le caratteristiche fisiche sono quelle della bestia: 10 + 4
    assert next(c for c in r.json()["combatants"] if c["id"] == pg["id"])["initiative"] == 14


@pytest.mark.caccia(id="CB-2763", fonte="2014 · Caratteristiche · Destrezza, tiri per colpire con armi a distanza · pag. 176; Equipaggiamento · Lancio · pag. 147",
                    zona="regola:2014/generali", voce="regola",
                    copre=["carta:2014/general.md#Destrezza / Dexterity (pag. 176-177)",
                           "carta:2014/general.md#Forza / Strength (pag. 175-176)",
                           "carta:2014/equipment.md#Proprieta delle Armi / Weapon Properties (pagg. 146-147)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_un_arma_a_distanza_da_lancio_lanciata_usa_la_destrezza(client):
    cid = await _pg(client, "fighter", 1, strength=8, dexterity=16)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Rete", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d4", "weapon_type": "ranged", "properties": ["special", "thrown"]}})
    assert r.status_code == 201, r.text
    rete = max(i["id"] for i in (await _scheda(client, cid))["items"])
    r = await client.patch(f"/characters/{cid}/items/{rete}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/items/{rete}/attack", json={"die": 10, "attack_mode": "thrown", "defer_damage": True})
    assert r.status_code == 200, r.text
    # arma a distanza: Destrezza +3 e competenza +2, non la Forza -1 delle armi da mischia lanciate
    assert r.json()["to_hit_bonus"] == 5


@pytest.mark.caccia(id="CB-2764", fonte="2014 · Multiclasse · Punti Ferita e Dadi Vita (nuova classe: dado vita o media) · pag. 163",
                    zona="regola:2014/generali", voce="regola",
                    copre=["carta:2014/general.md#Punti Ferita e Dadi Vita / Hit Points and Hit Dice (pag. 163)",
                           "PATCH /characters/{char_id}/classes/distribute"])
@pytest.mark.xfail(strict=True, reason="CB-2764: difforme dal manuale, confermato")
async def test_con_i_pf_tirati_il_primo_livello_di_una_nuova_classe_si_tira(client):
    cid = await _pg(client, "fighter", 1)  # 10 PF, Costituzione 10
    await _impostazioni(client, cid, hp_mode="rolled", advancement="milestone")
    guerriero = (await _scheda(client, cid))["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/distribute", json={"classes": [
        {"class_id": guerriero, "level": 1}, {"new_class": {"class_name": "wizard", "level": 1}, "level": 1}], "hp_rolls": [1]})
    # il livello da mago è un livello guadagnato: con i PF tirati vale il dado (1), non la media (4)
    assert (r.status_code, r.json().get("hit_points")) == (200, 11)


# ---------------------------------------------------------------------------
# Verdi: regole della zona che restano giuste
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2765", fonte="2014 · Multiclasse · Punti Ferita e Dadi Vita, Bonus di Competenza · pag. 163-164",
                    zona="regola:2014/generali", voce="regola",
                    copre=["carta:2014/general.md#Multiclasse / Multiclassing (pag. 163)",
                           "carta:2014/general.md#Punti Ferita e Dadi Vita / Hit Points and Hit Dice (pag. 163)",
                           "carta:2014/general.md#Bonus di Competenza / Proficiency Bonus (pag. 163-164)",
                           "POST /characters/{char_id}/classes"])
async def test_multiclasse_pf_dalla_seconda_classe_come_dal_secondo_livello_e_competenza_dal_livello_totale(client):
    cid = await _pg(client, "fighter", 3)
    await _classe(client, cid, "rogue", 2)
    scheda = await _scheda(client, cid)
    assert scheda["hit_points"] == 10 + 6 + 6 + 5 + 5  # d10 pieno solo al primo livello della prima classe
    assert scheda["proficiency_bonus"] == 3  # livello 5
    assert sorted(c["hit_die"] for c in scheda["classes"]) == [8, 10]


SLOT_MULTICLASSE = {
    2: {1: 3}, 3: {1: 4, 2: 2}, 4: {1: 4, 2: 3}, 5: {1: 4, 2: 3, 3: 2}, 6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1}, 8: {1: 4, 2: 3, 3: 3, 4: 2}, 9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}, 11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1}, 12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1}, 14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1}, 16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1}, 18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1}, 20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}


def _riga(nome, livello, sottoclasse=None):
    return SimpleNamespace(class_name=nome, level=livello, subclass_key=sottoclasse, spellcasting_ability=None)


@pytest.mark.caccia(id="CB-2766", fonte="2014 · Multiclasse · Incantatore Multiclasse: slot per livello · pag. 164-165",
                    zona="regola:2014/generali", voce="limiti",
                    copre=["carta:2014/general.md#Incantatore Multiclasse: slot per livello di incantesimo / Multiclass Spellcaster: Spell Slots per Spell Level (pag. 165)",
                           "carta:2014/general.md#Incantesimi / Spellcasting (multiclasse) (pag. 164)"])
@pytest.mark.parametrize("classi, livello", [
    *[((("bard", 1), ("wizard", n - 1)), n) for n in range(2, 21)],
    ((("ranger", 4), ("wizard", 3)), 5),  # l'esempio della carta: 2 + 3
    ((("paladin", 5), ("sorcerer", 1), ("fighter", 9, "eldritch_knight")), 6),  # metà e un terzo per difetto: 2 + 1 + 3
])
def test_slot_dell_incantatore_multiclasse(classi, livello):
    assert compute_regular_slots([_riga(*c) for c in classi], "2014") == SLOT_MULTICLASSE[livello]


@pytest.mark.caccia(id="CB-2767", fonte="2014 · Multiclasse · Incanalare Divinità (usi della classe che ne dà di più, effetti di entrambe) · pag. 164",
                    zona="regola:2014/generali", voce="interazione",
                    copre=["carta:2014/general.md#Incanalare Divinità / Channel Divinity (pag. 164)",
                           "carta:2014/general.md#Privilegi di Classe / Class Features (pag. 164)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_incanalare_divinita_chierico_6_paladino_3_due_usi_condivisi(client):
    cid = await _pg(client, "cleric", 6)
    await _classe(client, cid, "paladin", 3, "Giuramento di Devozione")
    riserve = [a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"].endswith(".channel_divinity")]
    assert [(a["uses"], a["max_uses"]) for a in riserve] == [(2, 2)]  # una riserva, nessun uso in più dal paladino
    r = await client.post(f"/characters/{cid}/features/paladin.turn_the_unholy/use", json={"params": {}})
    assert r.status_code == 200, r.text
    riserve = [a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"].endswith(".channel_divinity")]
    assert [a["uses"] for a in riserve] == [1]  # l'effetto del paladino spende dalla stessa riserva


@pytest.mark.caccia(id="CB-2768", fonte="2014 · Caratteristiche · Prove Passive (10 + modificatori, -5 con svantaggio) · pag. 175",
                    zona="regola:2014/generali", voce="regola",
                    copre=["carta:2014/general.md#Prove Passive / Passive Checks (pag. 175)",
                           "carta:2014/general.md#Abilità / Skills (pag. 174-175)", "GET /characters/{char_id}"])
async def test_percezione_passiva_dell_esempio_e_meno_5_con_svantaggio(client):
    cid = await _pg(client, "fighter", 1, wisdom=15)
    r = await client.patch(f"/characters/{cid}/skills", json={"skills": {"perception": True}})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["passives"]["perception"] == 14  # Sag 15, competente al 1° livello
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 1}})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["passives"]["perception"] == 9  # svantaggio alle prove: -5


@pytest.mark.caccia(id="CB-2769", fonte="2014 · Caratteristiche · Vantaggio e Svantaggio (si annullano, un solo d20) · pag. 173",
                    zona="regola:2014/generali", voce="regola",
                    copre=["carta:2014/general.md#Vantaggio e Svantaggio / Advantage and Disadvantage (pag. 173)",
                           "carta:2014/general.md#Prove di Caratteristica / Ability Checks (pag. 174)",
                           "POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_vantaggio_e_svantaggio_si_annullano_e_si_tira_un_solo_d20(client):
    cid = await _pg(client, "fighter", 1, dexterity=14)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"mode": "advantage", "dice": [3, 18]})
    assert r.status_code == 200, r.text
    tiro = r.json()
    assert (tiro["mode"], tiro["dice"], tiro["total"]) == ("normal", [3], 3 + 2)


@pytest.mark.caccia(id="CB-2770", fonte="2014 · Avventura · Riposo Lungo (Dadi Vita fino a metà del totale, minimo uno) · pag. 186",
                    zona="regola:2014/generali", voce="limiti",
                    copre=["carta:2014/general.md#Riposo Lungo / Long Rest (pag. 186)",
                           "carta:2014/general.md#Punti Ferita e Dadi Vita / Hit Points and Hit Dice (pag. 163)",
                           "POST /characters/{char_id}/rest", "POST /characters/{char_id}/hit_dice/spend"])
@pytest.mark.parametrize("classi, ripresi", [
    ((("fighter", 1),), 1),  # metà di 1 per difetto è 0: minimo uno
    ((("fighter", 3),), 1),
    ((("paladin", 5), ("cleric", 5)), 5),  # 5d10 + 5d8 in un'unica riserva: metà di 10
])
async def test_riposo_lungo_riprende_meta_dei_dadi_vita(client, classi, ripresi):
    (prima, livello), *altre = classi
    cid = await _pg(client, prima, livello)
    for nome, lv in altre:
        await _classe(client, cid, nome, lv)
    await _spendi_tutti_i_dadi_vita(client, cid)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.status_code == 200, r.text
    assert sum(c["level"] - c["hit_dice_used"] for c in r.json()["classes"]) == ripresi


@pytest.mark.caccia(id="CB-2771", fonte="2014 · Avventura · Riposo Breve (Dado Vita + Costituzione, minimo 0) · pag. 186 / 2024 · Short Rest (minimo 1) · pag. 373",
                    zona="regola:2014/generali", voce="edizioni",
                    copre=["carta:2014/general.md#Riposo Breve / Short Rest (pag. 186)",
                           "carta:2024/general.md#Short Rest (Riposo Breve) (pag. 373)",
                           "POST /characters/{char_id}/hit_dice/spend"])
@pytest.mark.parametrize("edizione, curati", [("2014", 0), ("2024", 1)])
async def test_dado_vita_con_costituzione_negativa_per_edizione(client, edizione, curati):
    cid = await _pg(client, "wizard", 2, edizione=edizione, constitution=3)  # modificatore -4
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})
    assert r.status_code == 200, r.text
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": classe, "count": 1, "rolls": [1]})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == curati


@pytest.mark.caccia(id="CB-2772", fonte="2014 · Avventura · Riposo Lungo (uno ogni 24 ore, almeno 1 PF) · pag. 186",
                    zona="regola:2014/generali", voce="ripetizione",
                    copre=["carta:2014/general.md#Riposo Lungo / Long Rest (pag. 186)",
                           "carta:2014/general.md#Riposare / Resting (pag. 186)", "POST /characters/{char_id}/rest"])
async def test_secondo_riposo_lungo_entro_24_ore_rifiutato_senza_benefici(client):
    cid = await _pg(client, "fighter", 3)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    await _spendi_tutti_i_dadi_vita(client, cid)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert (r.status_code, r.json()["detail"]) == (409, "long_rest_too_soon")
    assert (await _scheda(client, cid))["classes"][0]["hit_dice_used"] == 3  # nessun Dado Vita ripreso
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (r.status_code, r.json()["detail"]) == (409, "rest_needs_hp")  # a 0 PF nessun beneficio
