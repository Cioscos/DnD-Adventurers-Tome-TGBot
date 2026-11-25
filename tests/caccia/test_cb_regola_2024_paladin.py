"""Controlli della zona regola:2024/paladin."""
import pytest

from core.db.models import GameSession, SessionParticipant, SessionRole, SessionStatus
from core.rules.catalog import features_for
from tests.integration._encounter_helpers import GM_ID, NOW, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys
from tests.integration.rules.test_2014_paladin import _hp, _hurt
from tests.integration.rules.test_2014_paladin_combat import _damage, _deferred
from tests.integration.rules.test_2024_paladin import _paladin24
from tests.integration.rules.test_2024_paladin_oaths import _oath, _sword

LOH, SENTINEL, FREE_SMITE, PS = "paladin.lay_on_hands", "paladin.undying_sentinel", "paladin.divine_smite_free", "paladin.paladins_smite"


async def _seduti(factory, *coppie) -> None:
    """Una serata attiva con i personaggi indicati (utente, personaggio) seduti come giocatori."""
    async with factory() as s:
        serata = GameSession(code="PAL024", gm_user_id=999, status=SessionStatus.ACTIVE, created_at=NOW, last_activity_at=NOW)
        s.add(serata)
        await s.flush()
        for utente, cid in coppie:
            s.add(SessionParticipant(session_id=serata.id, user_id=utente, character_id=cid, role=SessionRole.PLAYER,
                                     display_name=f"P{cid}", joined_at=NOW))
        await s.commit()


async def _aggiungi(client, cid, classe, livello, dado) -> None:
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": classe, "level": livello, "hit_die": dado})
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2461", fonte="2024 · Paladino · Aura di Protezione, una sola aura alla volta scelta dalla creatura · pag. 111",
                    zona="regola:2024/paladin", voce="interazione",
                    copre=["carta:2024/classes/paladin.md#Aura di Protezione / Aura of Protection (Paladino 6, pag. 111)",
                           "GET /characters/{char_id}/roll-options", "GET /characters/{char_id}"])
@pytest.mark.xfail(strict=True, reason="CB-2461: difforme dal manuale, confermato")
async def test_un_paladino_puo_scegliere_l_aura_di_protezione_piu_forte_di_un_compagno(client, test_session_factory):
    debole = await _paladin24(client, 6, charisma=12)  # la sua aura dà +1
    as_user(PLAYER_ID)
    forte = await _paladin24(client, 6, charisma=18)  # la sua aura dà +4
    await _seduti(test_session_factory, (GM_ID, debole), (PLAYER_ID, forte))
    as_user(GM_ID)
    offerte = await _roll_keys(client, debole, "save", ability="dexterity")
    bonus = set((await _full(client, debole))["computed"]["save_flat"].values())
    assert "aura:protection" in offerte or bonus == {4}


@pytest.mark.caccia(id="CB-2462", fonte="2024 · Paladino · Incantesimi preparati solo di livelli per cui si hanno slot · pag. 109",
                    zona="regola:2024/paladin", voce="regola",
                    copre=["carta:2024/classes/paladin.md#Incantesimi / Spellcasting (Paladino 1, pag. 109)",
                           "POST /characters/{char_id}/spells", "GET /characters/{char_id}/spells"])
async def test_il_paladino_2024_non_prepara_un_incantesimo_di_livello_senza_slot(client):
    cid = await _paladin24(client, 4, charisma=16)  # slot solo di 1° livello, 5 preparati
    classe = (await _full(client, cid))["classes"][0]["id"]
    await client.post(f"/characters/{cid}/spells", json={"name": "Aiuto", "level": 2, "class_id": classe, "is_prepared": True})
    incantesimi = (await client.get(f"/characters/{cid}/spells")).json()
    assert not [s["name"] for s in incantesimi if s["level"] == 2 and s["is_prepared"]]


# ---------------------------------------------------------------------------
# Regole che restano giuste
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2464", fonte="2024 · Paladino · livelli dei privilegi di classe e di giuramento · pag. 109-117",
                    zona="regola:2024/paladin", voce="regola",
                    copre=["carta:2024/classes/paladin.md#Imposizione delle Mani / Lay On Hands (Paladino 1, pag. 109)",
                           "carta:2024/classes/paladin.md#Maestria nelle Armi / Weapon Mastery (Paladino 1, pag. 110)",
                           "carta:2024/classes/paladin.md#Stile di Combattimento / Fighting Style (Paladino 2, pag. 110)",
                           "carta:2024/classes/paladin.md#Guerriero Benedetto / Blessed Warrior (Stile di Combattimento, Paladino 2, pag. 110)",
                           "carta:2024/classes/paladin.md#Punizione del Paladino / Paladin's Smite (Paladino 2, pag. 110)",
                           "carta:2024/classes/paladin.md#Percezione del Divino / Divine Sense (Incanalare Divinità, Paladino 3, pag. 111)",
                           "carta:2024/classes/paladin.md#Incanalare Divinità / Channel Divinity (Paladino 3, pag. 110)",
                           "carta:2024/classes/paladin.md#Sottoclasse del Paladino / Paladin Subclass (Paladino 3, pag. 111)",
                           "carta:2024/classes/paladin.md#Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Paladino 4, pag. 111)",
                           "carta:2024/classes/paladin.md#Attacco Extra / Extra Attack (Paladino 5, pag. 111)",
                           "carta:2024/classes/paladin.md#Destriero Fedele / Faithful Steed (Paladino 5, pag. 111)",
                           "carta:2024/classes/paladin.md#Aura di Protezione / Aura of Protection (Paladino 6, pag. 111)",
                           "carta:2024/classes/paladin.md#Abiurare i Nemici / Abjure Foes (Paladino 9, pag. 111)",
                           "carta:2024/classes/paladin.md#Aura di Coraggio / Aura of Courage (Paladino 10, pag. 111)",
                           "carta:2024/classes/paladin.md#Assalti Radianti / Radiant Strikes (Paladino 11, pag. 111)",
                           "carta:2024/classes/paladin.md#Tocco Ristoratore / Restoring Touch (Paladino 14, pag. 111)",
                           "carta:2024/classes/paladin.md#Espansione dell'Aura / Aura Expansion (Paladino 18, pag. 111)",
                           "carta:2024/classes/paladin.md#Dono Epico / Epic Boon (Paladino 19, pag. 111)",
                           "carta:2024/classes/paladin.md#Incantesimi del Giuramento di Devozione / Oath of Devotion Spells (Giuramento di Devozione, Paladino 3, pag. 113)",
                           "carta:2024/classes/paladin.md#Arma Consacrata / Sacred Weapon (Incanalare Divinità, Giuramento di Devozione, Paladino 3, pag. 113)",
                           "carta:2024/classes/paladin.md#Aura di Devozione / Aura of Devotion (Giuramento di Devozione, Paladino 7, pag. 114)",
                           "carta:2024/classes/paladin.md#Punizione Protettiva / Smite of Protection (Giuramento di Devozione, Paladino 15, pag. 114)",
                           "carta:2024/classes/paladin.md#Nube Sacra / Holy Nimbus (Giuramento di Devozione, Paladino 20, pag. 114)",
                           "carta:2024/classes/paladin.md#Incantesimi del Giuramento della Gloria / Oath of Glory Spells (Giuramento della Gloria, Paladino 3, pag. 115)",
                           "carta:2024/classes/paladin.md#Punizione Ispiratrice / Inspiring Smite (Incanalare Divinità, Giuramento della Gloria, Paladino 3, pag. 114)",
                           "carta:2024/classes/paladin.md#Atleta Impareggiabile / Peerless Athlete (Incanalare Divinità, Giuramento della Gloria, Paladino 3, pag. 115)",
                           "carta:2024/classes/paladin.md#Aura di Alacrità / Aura of Alacrity (Giuramento della Gloria, Paladino 7, pag. 115)",
                           "carta:2024/classes/paladin.md#Difesa Gloriosa / Glorious Defense (Giuramento della Gloria, Paladino 15, pag. 115)",
                           "carta:2024/classes/paladin.md#Leggenda Vivente / Living Legend (Giuramento della Gloria, Paladino 20, pag. 115)",
                           "carta:2024/classes/paladin.md#Incantesimi del Giuramento degli Antichi / Oath of the Ancients Spells (Giuramento degli Antichi, Paladino 3, pag. 115)",
                           "carta:2024/classes/paladin.md#Collera della Natura / Nature's Wrath (Incanalare Divinità, Giuramento degli Antichi, Paladino 3, pag. 115)",
                           "carta:2024/classes/paladin.md#Aura di Interdizione / Aura of Warding (Giuramento degli Antichi, Paladino 7, pag. 116)",
                           "carta:2024/classes/paladin.md#Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 116)",
                           "carta:2024/classes/paladin.md#Campione degli Antichi / Elder Champion (Giuramento degli Antichi, Paladino 20, pag. 116)",
                           "carta:2024/classes/paladin.md#Incantesimi del Giuramento di Vendetta / Oath of Vengeance Spells (Giuramento di Vendetta, Paladino 3, pag. 117)",
                           "carta:2024/classes/paladin.md#Giuramento di Inimicizia / Vow of Enmity (Incanalare Divinità, Giuramento di Vendetta, Paladino 3, pag. 117)",
                           "carta:2024/classes/paladin.md#Vendicatore Implacabile / Relentless Avenger (Giuramento di Vendetta, Paladino 7, pag. 117)",
                           "carta:2024/classes/paladin.md#Anima di Vendetta / Soul of Vengeance (Giuramento di Vendetta, Paladino 15, pag. 117)",
                           "carta:2024/classes/paladin.md#Angelo Vendicatore / Avenging Angel (Giuramento di Vendetta, Paladino 20, pag. 117)"])
def test_ogni_privilegio_2024_arriva_al_livello_della_carta():
    attesi = {
        "lay_on_hands": 1, "spellcasting": 1, "weapon_mastery": 1, "fighting_style": 2, "style_blessed_warrior": 2,
        "paladins_smite": 2, "divine_sense": 3, "channel_divinity": 3, "paladin_subclass": 3, "ability_score_improvement": 4,
        "extra_attack": 5, "faithful_steed": 5, "aura_of_protection": 6, "abjure_foes": 9, "aura_of_courage": 10,
        "radiant_strikes": 11, "restoring_touch": 14, "aura_expansion": 18, "epic_boon": 19,
        "sacred_weapon": 3, "aura_of_devotion": 7, "smite_of_protection": 15, "holy_nimbus": 20,
        "inspiring_smite": 3, "peerless_athlete": 3, "aura_of_alacrity": 7, "glorious_defense": 15, "living_legend": 20,
        "natures_wrath": 3, "aura_of_warding": 7, "undying_sentinel": 15, "elder_champion": 20,
        "vow_of_enmity": 3, "relentless_avenger": 7, "soul_of_vengeance": 15, "avenging_angel": 20,
        **{f"{g}_spells": 3 for g in ("devotion", "glory", "ancients", "vengeance")},
        **{f"{g}_spells_{n}": n for g in ("devotion", "glory", "ancients", "vengeance") for n in (5, 9, 13, 17)},
    }
    livelli = {f.key.removeprefix("paladin."): f.level for f in features_for("2024", "paladin")}
    assert {k: livelli.get(k) for k in attesi} == attesi


@pytest.mark.caccia(id="CB-2465", fonte="2024 · Paladino · usi e ricariche dei privilegi · pag. 109-117",
                    zona="regola:2024/paladin", voce="regola",
                    copre=["carta:2024/classes/paladin.md#Imposizione delle Mani / Lay On Hands (Paladino 1, pag. 109)",
                           "carta:2024/classes/paladin.md#Punizione del Paladino / Paladin's Smite (Paladino 2, pag. 110)",
                           "carta:2024/classes/paladin.md#Incanalare Divinità / Channel Divinity (Paladino 3, pag. 110)",
                           "carta:2024/classes/paladin.md#Destriero Fedele / Faithful Steed (Paladino 5, pag. 111)",
                           "carta:2024/classes/paladin.md#Nube Sacra / Holy Nimbus (Giuramento di Devozione, Paladino 20, pag. 114)",
                           "carta:2024/classes/paladin.md#Difesa Gloriosa / Glorious Defense (Giuramento della Gloria, Paladino 15, pag. 115)",
                           "carta:2024/classes/paladin.md#Leggenda Vivente / Living Legend (Giuramento della Gloria, Paladino 20, pag. 115)",
                           "carta:2024/classes/paladin.md#Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 116)",
                           "carta:2024/classes/paladin.md#Campione degli Antichi / Elder Champion (Giuramento degli Antichi, Paladino 20, pag. 116)",
                           "carta:2024/classes/paladin.md#Angelo Vendicatore / Avenging Angel (Giuramento di Vendetta, Paladino 20, pag. 117)"])
def test_ogni_uso_2024_ha_il_numero_e_la_ricarica_della_carta():
    # (ricarica, recuperati col riposo breve, per livello, tabella, caratteristica); il minimo 1 di Difesa Gloriosa è quello di Uses
    attesi = {
        "lay_on_hands": ("long_rest", 0, 5, None, None), "paladins_smite": ("long_rest", 0, 0, {2: 1}, None),
        "channel_divinity": ("long_rest", 1, 0, {3: 2, 11: 3}, None), "faithful_steed": ("long_rest", 0, 0, {5: 1}, None),
        "glorious_defense": ("long_rest", 0, 0, None, "charisma"), "undying_sentinel": ("long_rest", 0, 0, {15: 1}, None),
        "holy_nimbus": ("long_rest", 0, 0, {20: 1}, None), "living_legend": ("long_rest", 0, 0, {20: 1}, None),
        "elder_champion": ("long_rest", 0, 0, {20: 1}, None), "avenging_angel": ("long_rest", 0, 0, {20: 1}, None),
    }
    righe = {f.key.removeprefix("paladin."): f for f in features_for("2024", "paladin")}
    letti = {k: (righe[k].restoration, righe[k].short_rest_recovers or 0, righe[k].uses.per_level, righe[k].uses.table or None,
                 righe[k].uses.ability) for k in attesi}
    assert letti == attesi


@pytest.mark.caccia(id="CB-2466", fonte="2024 · Paladino · Incantesimi già dal 1° livello (CD da Carisma) · pag. 109",
                    zona="regola:2024/paladin", voce="limiti",
                    copre=["carta:2024/classes/paladin.md#Incantesimi / Spellcasting (Paladino 1, pag. 109)", "GET /characters/{char_id}"])
async def test_il_paladino_2024_di_primo_livello_ha_la_cd_degli_incantesimi_da_carisma(client):
    lanciatori = (await _full(client, await _paladin24(client, 1, charisma=16)))["spellcasting"]["casters"]
    assert [(c["class_name"], c["ability"], c["save_dc"]) for c in lanciatori] == [("paladin", "charisma", 8 + 2 + 3)]


@pytest.mark.caccia(id="CB-2467", fonte="2024 · Paladino · slot multiclasse con metà dei livelli per eccesso, anche al 1° · pag. 109, 44",
                    zona="regola:2024/paladin", voce="interazione",
                    copre=["carta:2024/classes/paladin.md#Incantesimi / Spellcasting (Paladino 1, pag. 109)",
                           "carta:2024/classes/paladin.md#Multiclasse: Paladino / Multiclassing: Paladin (Regole di multiclasse, pag. 44)",
                           "POST /characters/{char_id}/classes"])
async def test_il_paladino_2024_di_primo_livello_conta_mezzo_livello_per_eccesso_negli_slot(client):
    cid = await _paladin24(client, 1)
    await _aggiungi(client, cid, "wizard", 1, 6)
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]} == {1: 3}  # 1 + 1 = livello 2


@pytest.mark.caccia(id="CB-2468", fonte="2024 · Paladino · Imposizione delle Mani e Tocco Ristoratore contano i livelli da paladino · pag. 109, 111",
                    zona="regola:2024/paladin", voce="interazione",
                    copre=["carta:2024/classes/paladin.md#Imposizione delle Mani / Lay On Hands (Paladino 1, pag. 109)",
                           "carta:2024/classes/paladin.md#Tocco Ristoratore / Restoring Touch (Paladino 14, pag. 111)",
                           "POST /characters/{char_id}/classes"])
async def test_riserva_e_condizioni_di_imposizione_seguono_il_livello_da_paladino(client):
    cid = await _paladin24(client, 13)
    await _aggiungi(client, cid, "fighter", 1, 10)  # livello totale 14, da paladino 13
    riga = await _ability(client, cid, LOH)
    assert (riga["max_uses"], [c["key"] for c in riga["removal"]["conditions"]]) == (65, ["poisoned"])


@pytest.mark.caccia(id="CB-2469", fonte="2024 · Paladino · Sentinella Imperitura, 1 PF più 3 x livello da paladino · pag. 116",
                    zona="regola:2024/paladin", voce="interazione",
                    copre=["carta:2024/classes/paladin.md#Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 116)",
                           "PATCH /characters/{char_id}/hp"])
async def test_sentinella_imperitura_cura_tre_volte_il_livello_da_paladino_in_multiclasse(client, test_session_factory):
    cid = await _oath(client, 15, "ancients")
    await _aggiungi(client, cid, "fighter", 2, 10)
    await _hurt(test_session_factory, cid, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9, "options": [SENTINEL]})
    assert r.status_code == 200, r.text
    assert await _hp(client, cid) == 1 + 3 * 15


@pytest.mark.caccia(id="CB-2470", fonte="2024 · Paladino · Sentinella Imperitura, annullare il danno rende l'uso · pag. 116",
                    zona="regola:2024/paladin", voce="annullamento",
                    copre=["carta:2024/classes/paladin.md#Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 116)",
                           "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_tenuto_a_uno_rende_la_sentinella_e_i_pf(client, test_session_factory):
    cid = await _oath(client, 15, "ancients")
    await _hurt(test_session_factory, cid, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9, "options": [SENTINEL]})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": (await _full(client, cid))["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert (await _hp(client, cid), (await _ability(client, cid, SENTINEL))["uses"]) == (5, 1)


@pytest.mark.caccia(id="CB-2471", fonte="2024 · Paladino · Punizione del Paladino, un lancio gratuito speso una volta · pag. 110",
                    zona="regola:2024/paladin", voce="ripetizione",
                    copre=["carta:2024/classes/paladin.md#Punizione del Paladino / Paladin's Smite (Paladino 2, pag. 110)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
async def test_punizione_gratuita_mandata_due_volte_sullo_stesso_colpo_si_spende_una_volta(client):
    cid = await _paladin24(client, 5)
    colpo = await _deferred(client, cid, await _sword(client, cid))
    primo = await _damage(client, cid, colpo, [FREE_SMITE])
    secondo = await _damage(client, cid, colpo, [FREE_SMITE])
    assert primo.status_code == 200 and secondo.status_code >= 400
    assert (await _ability(client, cid, PS))["uses"] == 0
