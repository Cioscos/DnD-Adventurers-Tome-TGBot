"""Controlli della zona regola:2024/bard."""
import pytest

from tests.integration._encounter_helpers import PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import BI, _ability, _add_spell, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_bard_inspiration import _give
from tests.integration.rules.test_2024_bard import DANCE, GLAMOUR, LORE, VALOR, _bard24, _set_uses, _slot_used, _table, _turn
from tests.integration.rules.test_2024_bard_lore_valor import _sword


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2211", fonte="2024 · Bardo · Collegio del Valore · Ispirazione in Combattimento (Offesa) · pag. 67", zona="regola:2024/bard",
                    voce="regola", copre=["carta:2024/classes/bard.md#Ispirazione in Combattimento / Combat Inspiration (Collegio del Valore 3, pag. 67)",
                                          "POST /characters/{char_id}/spells/{spell_id}/attack",
                                          "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_il_dado_del_valore_2024_si_somma_al_danno_di_un_attacco_con_incantesimo(client, test_session_factory, dadi):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=VALOR)
    assert (await _give(client, bard, hero)).status_code == 200
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/spells", json={"name": "Dardo di fuoco", "level": 0, "casting_time": "1 azione",
                                                               "attack_save": "ATK", "damage_dice": "1d10", "damage_type": "fire"})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    hit = await client.post(f"/characters/{hero}/spells/{spell}/attack", json={"die": 18})
    assert hit.status_code == 200 and not hit.json()["is_fumble"], hit.text
    dadi(3)  # il dado di Ispirazione (d6 al 3°)
    r = await client.post(f"/characters/{hero}/spells/{spell}/roll_damage", json={"main_rolls": [4], "options": ["bardic_die:damage"]})
    assert r.status_code == 200 and r.json()["total"] == 4 + 3, r.text


@pytest.mark.caccia(id="CB-2212", fonte="2024 · Bardo · Ispirazione Superiore pag. 61 e Passo a Due pag. 64; Effetti simultanei pag. 374", zona="regola:2024/bard",
                    voce="interazione", copre=["carta:2024/classes/bard.md#Ispirazione Superiore / Superior Inspiration (Bardo 18, pag. 61)",
                                               "carta:2024/classes/bard.md#Passo a Due / Tandem Footwork (Collegio della Danza 6, pag. 64)",
                                               "carta:2024/general.md#Simultaneous Effects (Effetti simultanei) (pag. 374)",
                                               "GET /characters/{char_id}/roll-options"])
async def test_ispirazione_superiore_paga_il_passo_a_due_della_stessa_iniziativa(client):
    cid = await _bard24(client, 18, DANCE, charisma=16)
    await _set_uses(client, cid, BI, 0)
    assert "bard.tandem_footwork" in await _roll_keys(client, cid, "initiative")  # all'Iniziativa recupera due usi e ne spende uno


@pytest.mark.caccia(id="CB-2213", fonte="2024 · Glossario · Incapacitato · pag. 369; Bardo · privilegi ad azione bonus e reazione · pag. 59-67", zona="regola:2024/bard",
                    voce="interazione", copre=["carta:2024/general.md#Incapacitated [Condition] (Incapacitato) (pag. 369)",
                                               "carta:2024/classes/bard.md#Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 59)",
                                               "carta:2024/classes/bard.md#Controfascino / Countercharm (Bardo 7, pag. 61)",
                                               "carta:2024/classes/bard.md#Parole Taglienti / Cutting Words (Collegio della Sapienza 3, pag. 66)",
                                               "carta:2024/classes/bard.md#Mantello di Ispirazione / Mantle of Inspiration (Collegio dell'Incanto 3, pag. 65)",
                                               "carta:2024/classes/bard.md#Mantello di Maestà / Mantle of Majesty (Collegio dell'Incanto 6, pag. 65)",
                                               "carta:2024/classes/bard.md#Maestà Infrangibile / Unbreakable Majesty (Collegio dell'Incanto 14, pag. 66)",
                                               "carta:2024/classes/bard.md#Movimento Ispiratore / Inspiring Movement (Collegio della Danza 6, pag. 64)",
                                               "PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("college,key", [
    (None, "bard.bardic_inspiration"), (None, "bard.countercharm"), (LORE, "bard.cutting_words"),
    (GLAMOUR, "bard.mantle_of_inspiration"), (GLAMOUR, "bard.mantle_of_majesty"), (GLAMOUR, "bard.unbreakable_majesty"),
    (DANCE, "bard.inspiring_movement")])
async def test_un_bardo_incapacitato_non_usa_azioni_bonus_ne_reazioni(client, college, key):
    cid = await _bard24(client, 14, college, charisma=16)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert r.status_code == 200, r.text
    assert (await _use(client, cid, key)).status_code == 409


@pytest.mark.caccia(id="CB-2214", fonte="2024 · Bardo · Collegio del Valore · Magia da Battaglia · pag. 67", zona="regola:2024/bard",
                    voce="regola", copre=["carta:2024/classes/bard.md#Magia da Battaglia / Battle Magic (Collegio del Valore 14, pag. 67)",
                                          "POST /characters/{char_id}/spells/{spell_id}/use", "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-2214: difforme dal manuale, confermato")
async def test_magia_da_battaglia_non_segue_un_incantesimo_da_un_minuto(client):
    cid = await _bard24(client, 14, VALOR)
    sword = await _sword(client, cid)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    spell = (await _add_spell(client, cid, "Incantesimo lungo", 1, casting_time="1 minuto", is_prepared=True, class_id=bard_class)).json()
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2216", fonte="2024 · Bardo · Ispirazione Bardica · pag. 59", zona="regola:2024/bard", voce="limiti",
                    copre=["carta:2024/classes/bard.md#Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 59)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("level,die", [(1, 6), (4, 6), (5, 8), (9, 8), (10, 10), (14, 10), (15, 12), (20, 12)])
async def test_il_dado_di_ispirazione_segue_il_livello_e_dura_un_ora(client, level, die):
    cid = await _bard24(client, level, charisma=16)
    r = await _use(client, cid, BI)
    assert r.status_code == 200, r.text
    assert (r.json()["state"]["data"]["die"], r.json()["state"]["rounds_left"]) == (die, 600)
    assert (await _turn(client, cid))["bonus_used"] is True


@pytest.mark.caccia(id="CB-2217", fonte="2024 · Bardo · Ispirazione Bardica pag. 59 e Fonte di Ispirazione pag. 61", zona="regola:2024/bard", voce="limiti",
                    copre=["carta:2024/classes/bard.md#Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 59)",
                           "carta:2024/classes/bard.md#Fonte di Ispirazione / Font of Inspiration (Bardo 5, pag. 61)",
                           "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("level,cha,uses,rest", [(1, 8, 1, "long_rest"), (4, 16, 3, "long_rest"), (5, 16, 3, "short_rest"),
                                                 (20, 20, 5, "short_rest")])
async def test_usi_di_ispirazione_pari_al_carisma_e_ricarica_dal_quinto(client, level, cha, uses, rest):
    cid = await _bard24(client, level, charisma=cha)
    row = await _ability(client, cid, BI)
    assert (row["max_uses"], row["restoration_type"]) == (uses, rest)
    await _set_uses(client, cid, BI, 0)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _ability(client, cid, BI))["uses"] == (uses if rest == "short_rest" else 0)


@pytest.mark.caccia(id="CB-2218", fonte="2024 · Bardo · Tabella di classe e Incantesimi · pag. 59", zona="regola:2024/bard", voce="regola",
                    copre=["carta:2024/classes/bard.md#Incantesimi / Spellcasting (Bardo 1, pag. 59)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("level,cantrips,prepared,slots", [
    (1, 2, 4, (2,)), (3, 2, 6, (4, 2)), (4, 3, 7, (4, 3)), (9, 3, 14, (4, 3, 3, 3, 1)), (10, 4, 15, (4, 3, 3, 3, 2)),
    (18, 4, 20, (4, 3, 3, 3, 3, 1, 1, 1, 1)), (20, 4, 22, (4, 3, 3, 3, 3, 2, 2, 1, 1))])
async def test_trucchetti_preparati_e_slot_seguono_la_tabella_2024(client, level, cantrips, prepared, slots):
    full = await _full(client, await _bard24(client, level))
    limits = full["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (cantrips, prepared)
    assert tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"])) == slots


@pytest.mark.caccia(id="CB-2219", fonte="2024 · Bardo · Controfascino · pag. 61", zona="regola:2024/bard", voce="limiti",
                    copre=["carta:2024/classes/bard.md#Controfascino / Countercharm (Bardo 7, pag. 61)",
                           "POST /characters/{char_id}/last-roll/options"])
async def test_controfascino_arriva_al_settimo_e_ripete_il_ts_con_vantaggio_in_reazione(client):
    assert "bard.countercharm" not in await _keys_of(client, await _bard24(client, 6))
    cid = await _bard24(client, 7)
    assert (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 3})).status_code == 200
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["bard.countercharm"]})
    assert r.status_code == 200 and r.json()["mode_applied"] == "advantage", r.text
    assert (await _turn(client, cid))["reaction_used"] is True


@pytest.mark.caccia(id="CB-2220", fonte="2024 · Bardo · Ispirazione Superiore · pag. 61", zona="regola:2024/bard", voce="limiti",
                    copre=["carta:2024/classes/bard.md#Ispirazione Superiore / Superior Inspiration (Bardo 18, pag. 61)",
                           "POST /characters/{char_id}/dice/initiative"])
@pytest.mark.parametrize("level,expected", [(17, 0), (18, 2)])
async def test_ispirazione_superiore_dal_diciottesimo_riporta_gli_usi_a_due(client, level, expected):
    cid = await _bard24(client, level, charisma=16)
    await _set_uses(client, cid, BI, 0)
    assert (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8})).status_code == 200
    assert (await _ability(client, cid, BI))["uses"] == expected


@pytest.mark.caccia(id="CB-2221", fonte="2024 · Bardo · Fonte di Ispirazione · pag. 61", zona="regola:2024/bard", voce="ripetizione",
                    copre=["carta:2024/classes/bard.md#Fonte di Ispirazione / Font of Inspiration (Bardo 5, pag. 61)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_fonte_di_ispirazione_converte_uno_slot_una_volta_sola_e_senza_azione(client):
    cid = await _bard24(client, 5, charisma=16)  # 3 usi
    await _set_uses(client, cid, BI, 2)
    for _ in range(2):  # il secondo invio trova gli usi già pieni: nessuno slot speso
        await _use(client, cid, "bard.font_of_inspiration", params={"slot_level": "1"})
    assert (await _ability(client, cid, BI))["uses"] == 3 and await _slot_used(client, cid, 1) == 1
    turn = await _turn(client, cid)
    assert not (turn["action_used"] or turn["bonus_used"] or turn["reaction_used"])


@pytest.mark.caccia(id="CB-2222", fonte="2024 · Bardo · Collegio del Valore · Attacco Extra pag. 67; Multiclasse pag. 44", zona="regola:2024/bard",
                    voce="interazione", copre=["carta:2024/classes/bard.md#Attacco Extra / Extra Attack (Collegio del Valore 6, pag. 67)",
                                               "carta:2024/classes/bard.md#Multiclasse: Bardo / Multiclassing: Bard (Capitolo 2, pag. 44)",
                                               "POST /characters/{char_id}/classes"])
async def test_attacco_extra_del_valore_dal_sesto_e_non_si_somma_a_quello_del_guerriero(client):
    five, six = await _bard24(client, 5, VALOR), await _bard24(client, 6, VALOR)
    allowed = lambda c: client.get(f"/characters/{c}/turn-state")  # noqa: E731
    assert ((await allowed(five)).json()["attacks_allowed"], (await allowed(six)).json()["attacks_allowed"]) == (1, 2)
    r = await client.post(f"/characters/{six}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    assert (await allowed(six)).json()["attacks_allowed"] == 2


@pytest.mark.caccia(id="CB-2223", fonte="2024 · Bardo · Collegio della Sapienza · Abilità Impareggiabile · pag. 67", zona="regola:2024/bard",
                    voce="annullamento", copre=["carta:2024/classes/bard.md#Abilità Impareggiabile / Peerless Skill (Collegio della Sapienza 14, pag. 67)",
                                                "POST /characters/{char_id}/last-roll/options", "POST /characters/{char_id}/last-roll/refund"])
async def test_abilita_impareggiabile_rende_l_uso_se_la_prova_fallisce_comunque(client):
    cid = await _bard24(client, 14, LORE, charisma=16)
    assert (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 2})).status_code == 200
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["bard.peerless_skill"]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, BI))["uses"] == 2
    assert (await client.post(f"/characters/{cid}/last-roll/refund")).status_code == 200
    assert (await _ability(client, cid, BI))["uses"] == 3
