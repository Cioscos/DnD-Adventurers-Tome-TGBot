"""Controlli della zona regola:2014/ranger."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.data.spell_slots import compute_regular_slots
from tests.integration.rules.test_2014_bard import _full, _roll_keys, _use
from tests.integration.rules.test_2014_paladin import _turn
from tests.integration.rules.test_2014_ranger import _ranger, _states
from tests.integration.rules.test_2014_ranger_beast import _beast, _bite, _companion, _master, _order
from tests.integration.rules.test_2014_ranger_hunter import _bow, _full_hp, _hunter, _hurt, _save, _superior, _sword
from tests.integration.rules.test_2024_ranger import _ranger24
from tests.integration.test_rules_forms import beast

FOE_SLAYER = ("ranger.foe_slayer_attack", "ranger.foe_slayer_attack_late", "ranger.foe_slayer_damage")
FERAL, HORDE, UNCANNY = "ranger.feral_senses", "ranger.horde_breaker", "ranger.uncanny_dodge"
EVASION, EVASION_OK = "ranger.evasion", "ranger.evasion_success"
CAMO_FEATURE, CAMO_STATE = "ranger.hide_in_plain_sight", "camouflaged"
PREY, TACTICS, MULTI = "hunters_prey", "defensive_tactics", "hunter_multiattack"

# Tabella di classe del Ranger 2014: slot di 1°-5° per livello
SLOTS_2014 = [
    {}, {1: 2}, {1: 3}, {1: 3}, {1: 4, 2: 2}, {1: 4, 2: 2}, {1: 4, 2: 3}, {1: 4, 2: 3}, {1: 4, 2: 3, 3: 2}, {1: 4, 2: 3, 3: 2},
    {1: 4, 2: 3, 3: 3}, {1: 4, 2: 3, 3: 3}, {1: 4, 2: 3, 3: 3, 4: 1}, {1: 4, 2: 3, 3: 3, 4: 1}, {1: 4, 2: 3, 3: 3, 4: 2},
    {1: 4, 2: 3, 3: 3, 4: 2}, {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}, {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}, {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
]
PROFICIENCY = [2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6]


async def _slots(client, cid) -> dict[int, int]:
    return {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}


async def _add_class(client, cid, name, level, hit_die=10):
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": name, "level": level, "hit_die": hit_die})
    assert r.status_code == 201, r.text


async def _incapacitate(client, cid, condition="incapacitated"):
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condition: True}})
    assert r.status_code == 200, r.text


async def _undo_hp(client, cid):
    op = (await _full(client, cid))["hp_undo_id"]
    assert op, "nessuna operazione PF da annullare"
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": op})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1911", fonte="2014 · Ranger · Incantesimi dal 2° livello · pag. 104; Multiclasse · Incantesimi: con una sola classe che ha il privilegio valgono le sue regole · pag. 164",
                    zona="regola:2014/ranger", voce="interazione",
                    copre=["carta:2014/classes/ranger.md#Multiclasse: Ranger / Multiclassing: Ranger (Opzioni di Personalizzazione, pag. 163)",
                           "carta:2014/classes/ranger.md#Incantesimi / Spellcasting (Ranger 2, pag. 104)", "POST /characters/{char_id}/classes"])
@pytest.mark.parametrize("initial,slots", [
    ({"class_name": "paladin", "level": 5}, {1: 4, 2: 2}),
    ({"class_name": "fighter", "level": 7, "subclass": "Cavaliere Mistico"}, {1: 4, 2: 2}),
])
@pytest.mark.xfail(strict=True, reason="CB-1911: difforme dal manuale, confermato")
async def test_un_livello_da_ranger_non_cambia_gli_slot_dell_unico_incantatore(client, initial, slots):
    r = await client.post("/characters", json={"name": "Multiclasse", "initial_class": initial})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert await _slots(client, cid) == slots  # la tabella della sua classe
    await _add_class(client, cid, "ranger", 1)  # il ranger di 1° livello non ha ancora Incantesimi
    assert await _slots(client, cid) == slots


@pytest.mark.caccia(id="CB-1912", fonte="2014 · Ranger · Sterminatore di Nemici · pag. 105 (l'attacco è del ranger, non della bestia)",
                    zona="regola:2014/ranger", voce="interazione",
                    copre=["carta:2014/classes/ranger.md#Sterminatore di Nemici / Foe Slayer (Ranger 20, pag. 105)",
                           "carta:2014/classes/ranger.md#Sensi Ferini / Feral Senses (Ranger 18, pag. 105)",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/companions/{comp_id}/attack"])
async def test_l_attacco_della_bestia_non_prende_le_opzioni_d_attacco_del_ranger(client):
    cid, comp = await _beast(client, 20, wisdom=16)  # Signore delle Bestie 20, Saggezza +3
    offered = set(await _roll_keys(client, cid, "attack", attack_mode="companion"))
    assert not offered & {*FOE_SLAYER, FERAL}, offered
    assert (await _order(client, cid, comp, "attack")).status_code == 200
    r = await _bite(client, cid, comp, options=[FOE_SLAYER[0]])
    assert r.status_code == 409, r.text  # la Saggezza del ranger non va sul tiro per colpire della bestia


@pytest.mark.caccia(id="CB-1913", fonte="2014 · Ranger · Signore delle Bestie · Compagno del Ranger: bestia Media o più piccola, GS 1/4 o meno · pag. 106",
                    zona="regola:2014/ranger", voce="regola",
                    copre=["carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)",
                           "POST /characters/{char_id}/companions"])
@pytest.mark.parametrize("cr,size,kind", [(0.5, "Medium", "beast"), (2, "Large", "beast"), (0.25, "Large", "beast"),
                                          (0.25, "Medium", "monstrosity")])
async def test_la_bestia_compagna_rispetta_taglia_grado_di_sfida_e_tipo(client, cr, size, kind):
    cid = await _master(client, 3)
    sb = beast(cr=cr, type_=kind, dex=15, con=10)
    sb["size"] = size
    r = await _companion(client, cid, statblock=sb)
    assert r.status_code == 422, r.text


@pytest.mark.caccia(id="CB-1914", fonte="2014 · Ranger · Nascondersi in Piena Vista: muoversi, compiere un'azione o una reazione fa perdere il bonus · pag. 105",
                    zona="regola:2014/ranger", voce="regola",
                    copre=["carta:2014/classes/ranger.md#Nascondersi in Piena Vista / Hide in Plain Sight (Ranger 10, pag. 105)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("feature,params", [("ranger.primeval_awareness", {"slot_level": "1"}),  # un'azione
                                            ("ranger.stand_against_the_tide", None)])  # una reazione
async def test_agire_o_reagire_toglie_il_mimetismo(client, feature, params):
    cid = await _superior(client, "stand_against_the_tide")  # Cacciatore 15: ha anche Nascondersi in Piena Vista
    assert (await _use(client, cid, CAMO_FEATURE)).status_code == 200
    assert CAMO_STATE in {s["key"] for s in await _states(client, cid)}
    r = await _use(client, cid, feature, **({"params": params} if params else {}))
    assert r.status_code == 200, r.text
    assert CAMO_STATE not in {s["key"] for s in await _states(client, cid)}


@pytest.mark.caccia(id="CB-1915", fonte="2014 · Ranger · Schivata Prodigiosa (reazione) · pag. 106; Condizioni · Incapacitato: niente azioni né reazioni · pag. 291",
                    zona="regola:2014/ranger", voce="interazione",
                    copre=["carta:2014/classes/ranger.md#Schivata Prodigiosa / Uncanny Dodge (Cacciatore 15, pag. 106)",
                           "GET /characters/{char_id}/roll-options", "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("condition", ["incapacitated", "stunned"])
@pytest.mark.xfail(strict=True, reason="CB-1915: difforme dal manuale, confermato")
async def test_schivata_prodigiosa_non_si_usa_da_incapacitato(client, condition):
    cid = await _superior(client, "uncanny_dodge")
    await _full_hp(client, cid)
    await _incapacitate(client, cid, condition)
    assert UNCANNY not in await _roll_keys(client, cid, "damage_taken")
    r = await _hurt(client, cid, 20, UNCANNY)
    assert r.status_code == 409, r.text  # nessuna reazione: il danno non si dimezza


@pytest.mark.caccia(id="CB-1916", fonte="2014 · Ranger · privilegi con azione, azione bonus o reazione · pag. 105-106; Condizioni · Incapacitato: niente azioni né reazioni · pag. 291",
                    zona="regola:2014/ranger", voce="interazione",
                    copre=["carta:2014/classes/ranger.md#Consapevolezza Primordiale / Primeval Awareness (Ranger 3, pag. 105)",
                           "carta:2014/classes/ranger.md#Svanire / Vanish (Ranger 14, pag. 105)",
                           "carta:2014/classes/ranger.md#Attacco Turbinante / Whirlwind Attack (Cacciatore 11, pag. 106)",
                           "carta:2014/classes/ranger.md#Opporsi alla Marea / Stand Against the Tide (Cacciatore 15, pag. 106)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("who,feature,params", [
    ("ranger3", "ranger.primeval_awareness", {"slot_level": "1"}),
    ("ranger14", "ranger.vanish", None),
    ("whirlwind", "ranger.whirlwind_attack", None),
    ("tide", "ranger.stand_against_the_tide", None),
])
@pytest.mark.xfail(strict=True, reason="CB-1916: difforme dal manuale, confermato")
async def test_da_incapacitato_i_privilegi_d_azione_non_si_usano(client, who, feature, params):
    if who == "ranger3":
        cid = await _ranger(client, 3)
    elif who == "ranger14":
        cid = await _ranger(client, 14)
    elif who == "whirlwind":
        cid = await _hunter(client, 11, (PREY, "colossus_slayer"), (TACTICS, "steel_will"), (MULTI, "whirlwind_attack"))
    else:
        cid = await _superior(client, "stand_against_the_tide")
    await _incapacitate(client, cid)
    slots_before = await _slots(client, cid)
    r = await _use(client, cid, feature, **({"params": params} if params else {}))
    assert r.status_code == 409, r.text
    turn = await _turn(client, cid)
    assert not (turn["action_used"] or turn["bonus_used"] or turn["reaction_used"])
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]} == {lv: 0 for lv in slots_before}


@pytest.mark.caccia(id="CB-1917", fonte="2014 · Ranger · Cacciatore · Devastatore dell'Orda: un altro attacco con la stessa arma · pag. 106",
                    zona="regola:2014/ranger", voce="regola",
                    copre=["carta:2014/classes/ranger.md#Devastatore dell'Orda / Horde Breaker (Cacciatore 3, pag. 106)",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_devastatore_dell_orda_solo_con_la_stessa_arma(client):
    cid = await _hunter(client, 3, (PREY, "horde_breaker"))
    sword = await _sword(client, cid, equip="main_hand")
    bow = await _bow(client, cid)
    r = await client.post(f"/characters/{cid}/items/{bow}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    assert HORDE in await _roll_keys(client, cid, "attack", item_id=bow)  # la stessa arma: sì
    assert HORDE not in await _roll_keys(client, cid, "attack", item_id=sword)  # un'altra arma: no


@pytest.mark.caccia(id="CB-1918", fonte="2014 · Ranger · Compagno del Ranger: senza ordini solo la reazione, o da sola col ranger incapacitato · pag. 106; Combattimento · una reazione per round",
                    zona="regola:2014/ranger", voce="limiti",
                    copre=["carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)",
                           "POST /characters/{char_id}/companions/{comp_id}/attack"])
@pytest.mark.parametrize("way", ["reaction", "autonomous"])
async def test_la_bestia_senza_ordini_non_attacca_senza_limite(client, way):
    cid, comp = await _beast(client, 3)  # pantera senza Multiattacco
    if way == "autonomous":
        await _incapacitate(client, cid)  # il ranger non ordina: la bestia agisce da sola, con la sua azione
    body = {"reaction": True} if way == "reaction" else {}
    assert (await _bite(client, cid, comp, **body)).status_code == 200
    second = await _bite(client, cid, comp, **body)
    assert second.status_code == 409, second.text


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1919", fonte="2014 · Ranger · Tabella di classe: slot di 1°-5° per livello · pag. 103-104", zona="regola:2014/ranger", voce="regola",
                    copre=["carta:2014/classes/ranger.md#Incantesimi / Spellcasting (Ranger 2, pag. 104)"])
def test_gli_slot_del_ranger_seguono_la_tabella_di_classe():
    rows = [compute_regular_slots([SimpleNamespace(class_name="ranger", level=lv, subclass_key=None, spellcasting_ability="wisdom")], "2014")
            for lv in range(1, 21)]
    assert rows == SLOTS_2014


@pytest.mark.caccia(id="CB-1920", fonte="2014 · Ranger · Tabella di classe: bonus di competenza e slot · pag. 103", zona="regola:2014/ranger", voce="regola",
                    copre=["carta:2014/classes/ranger.md#Incantesimi / Spellcasting (Ranger 2, pag. 104)"])
def test_la_progressione_della_webapp_ha_slot_e_competenza_della_tabella():
    path = Path(__file__).resolve().parents[2] / "webapp/src/data/class-progression.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["Ranger"]
    assert [r["proficiency_bonus"] for r in rows] == PROFICIENCY
    assert [{i + 1: n for i, n in enumerate(r["spell_slots"]) if n} for r in rows] == SLOTS_2014


@pytest.mark.caccia(id="CB-1921", fonte="2014 · Ranger · Compagno del Ranger: PF il maggiore fra scheda e 4 x livello, competenza a CA, attacco e danni · pag. 106",
                    zona="regola:2014/ranger", voce="limiti",
                    copre=["carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)",
                           "GET /characters/{char_id}/companions"])
@pytest.mark.parametrize("level,stats", [(3, (13, 14, 2, 2)), (20, (80, 18, 6, 6))])
async def test_la_bestia_compagna_ai_livelli_estremi(client, level, stats):
    cid, comp = await _beast(client, level)  # scheda: 13 PF, CA 12
    read = next(c for c in (await client.get(f"/characters/{cid}/companions")).json() if c["id"] == comp)
    assert (read["max_hp"], read["armor_class"], read["attack_bonus_extra"], read["damage_bonus_extra"]) == stats


@pytest.mark.caccia(id="CB-1922", fonte="2014 · Ranger · Cacciatore · Elusione · pag. 106 (annullare il danno rende l'Elusione confermata)",
                    zona="regola:2014/ranger", voce="annullamento",
                    copre=["carta:2014/classes/ranger.md#Elusione / Evasion (Cacciatore 15, pag. 106)", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_eluso_rende_l_elusione(client):
    cid = await _superior(client, "evasion")
    await _full_hp(client, cid)
    await _save(client, cid, "dexterity", EVASION)
    assert (await _hurt(client, cid, 20, EVASION_OK)).json()["current_hit_points"] == 60
    assert EVASION_OK not in await _roll_keys(client, cid, "damage_taken")
    await _undo_hp(client, cid)
    assert (await _full(client, cid))["current_hit_points"] == 60
    assert EVASION_OK in await _roll_keys(client, cid, "damage_taken")


@pytest.mark.caccia(id="CB-1923", fonte="2014 · Ranger · Cacciatore · Schivata Prodigiosa (reazione) · pag. 106 (annullare il danno rende la reazione)",
                    zona="regola:2014/ranger", voce="annullamento",
                    copre=["carta:2014/classes/ranger.md#Schivata Prodigiosa / Uncanny Dodge (Cacciatore 15, pag. 106)", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_dimezzato_rende_la_reazione(client):
    cid = await _superior(client, "uncanny_dodge")
    await _full_hp(client, cid)
    assert (await _hurt(client, cid, 21, UNCANNY)).json()["current_hit_points"] == 50  # 21 dimezzato per difetto
    assert (await _turn(client, cid))["reaction_used"] is True
    await _undo_hp(client, cid)
    assert (await _full(client, cid))["current_hit_points"] == 60
    assert (await _turn(client, cid))["reaction_used"] is False


@pytest.mark.caccia(id="CB-1924", fonte="2014 · Multiclasse · Incantesimi: metà dei livelli da ranger e da paladino, per difetto, sulla tabella multiclasse · pag. 164-165",
                    zona="regola:2014/ranger", voce="interazione",
                    copre=["carta:2014/classes/ranger.md#Multiclasse: Ranger / Multiclassing: Ranger (Opzioni di Personalizzazione, pag. 163)",
                           "POST /characters/{char_id}/classes"])
async def test_ranger_2_e_paladino_3_sommano_meta_dei_livelli(client):
    cid = await _ranger(client, 2)
    await _add_class(client, cid, "paladin", 3)  # 2 // 2 + 3 // 2 = livello da incantatore 2
    assert await _slots(client, cid) == {1: 3}


@pytest.mark.caccia(id="CB-1925", fonte="2014 · Ranger · Incantesimi dal 2° livello · pag. 104; 2024 · Ranger · Incantesimi dal 1° livello, 2 slot · pag. 119",
                    zona="regola:2014/ranger", voce="edizioni",
                    copre=["carta:2014/classes/ranger.md#Incantesimi / Spellcasting (Ranger 2, pag. 104)",
                           "carta:2024/classes/ranger.md#Incantesimi / Spellcasting (Ranger 1, pag. 119)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("edition,slots", [("2014", {}), ("2024", {1: 2})])
async def test_gli_slot_del_ranger_di_1_livello_per_edizione(client, edition, slots):
    cid = await (_ranger(client, 1) if edition == "2014" else _ranger24(client, 1))
    assert await _slots(client, cid) == slots


@pytest.mark.caccia(id="CB-1926", fonte="invariante: due ordini d'attacco uguali insieme spendono una sola azione e aprono un solo attacco della bestia",
                    zona="regola:2014/ranger", voce="ripetizione",
                    copre=["carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)",
                           "POST /characters/{char_id}/companions/{comp_id}/command"])
async def test_due_ordini_d_attacco_insieme_ne_valgono_uno(client):
    cid, comp = await _beast(client, 3)
    rs = await asyncio.gather(*(_order(client, cid, comp, "attack") for _ in range(2)))
    assert sorted(r.status_code for r in rs) == [200, 409], [r.text for r in rs]
    turn = await _turn(client, cid)
    assert turn["action_attacks"] == 1 and turn["beast"]["attacks_left"] == 1
