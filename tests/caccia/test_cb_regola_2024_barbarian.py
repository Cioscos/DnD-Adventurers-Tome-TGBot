"""Controlli della zona regola:2024/barbarian."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_barbarian import _ability, _attack, _full, _hit, _hp, _weapon
from tests.integration.rules.test_2014_barbarian_round1 import _in_encounter
from tests.integration.rules.test_2014_druid import _activate, _beast, _form
from tests.integration.rules.test_2024_barbarian import _barbarian, _new_turn, _rage, _rage_state
from tests.integration.rules.test_2024_barbarian_paths import _pick, _use
from tests.integration.rules.test_2024_barbarian_strike import _damage
from tests.integration.rules.test_2024_druid import _druid24

RAGE = "barbarian.rage"
WILD = "Cammino del Cuore Selvaggio"
TREE = "Cammino dell'Albero del Mondo"
ZEALOT = "Cammino dello Zelota"


async def _riposo_lungo(client, cid) -> None:
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text


async def _url_sostituzione(client, cid) -> str:
    classe = (await _full(client, cid))["classes"][0]["id"]
    return f"/characters/{cid}/classes/{classe}/options/replace"


async def _scurovisione(client, cid) -> int:
    sensi = (await _full(client, cid))["computed"]["senses"]
    return max((s["range_ft"] for s in sensi if s["type"] == "darkvision"), default=0)


async def _mio_turno(client, cid) -> bool:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["is_my_turn"]


async def _barbaro_in_scontro(client, factory, monkeypatch, sottoclasse) -> tuple[int, int]:
    """PG 2024 barbaro di 3° livello primo nell'ordine di iniziativa, con due goblin dopo di lui."""
    sid, cid = await _in_encounter(client, factory, monkeypatch)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 3, "hit_die": 12,
                                                               "subclass": sottoclasse})
    assert r.status_code == 201, r.text
    assert await _mio_turno(client, cid) is True
    return sid, cid


async def _turno_del_goblin(client, sid, cid) -> None:
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)
    assert await _mio_turno(client, cid) is False


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2161", fonte="2024 · Barbaro, Cammino del Cuore Selvaggio · Aspetto della Natura Selvaggia · pag. 55",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Aspetto della Natura Selvaggia / Aspect of the Wilds (Cammino del Cuore Selvaggio 6, pag. 55)",
                           "POST /characters/{char_id}/classes/{class_id}/options/replace", "POST /characters/{char_id}/rest"])
@pytest.mark.xfail(strict=True, reason="CB-2161: difforme dal manuale, confermato")
async def test_aspetto_della_natura_selvaggia_si_cambia_una_volta_per_riposo_lungo(client):
    cid = await _barbarian(client, 6, WILD)
    await _pick(client, cid, "aspect_of_the_wilds", "owl")
    await _riposo_lungo(client, cid)
    url = await _url_sostituzione(client, cid)
    primo = await client.post(url, json={"group": "aspect_of_the_wilds", "old_key": "owl", "new_key": "panther"})
    assert primo.status_code == 200, primo.text
    secondo = await client.post(url, json={"group": "aspect_of_the_wilds", "old_key": "panther", "new_key": "salmon"})
    assert secondo.status_code == 409, "un secondo cambio prima del prossimo riposo lungo non è ammesso"


@pytest.mark.caccia(id="CB-2162", fonte="2024 · Barbaro, Cammino del Cuore Selvaggio · Gufo · pag. 55",
                    zona="regola:2024/barbarian", voce="interazione",
                    copre=["carta:2024/classes/barbarian.md#Gufo / Owl (Aspetto della Natura Selvaggia, Cammino del Cuore Selvaggio 6, pag. 55)",
                           "PUT /characters/{char_id}/species"])
@pytest.mark.xfail(strict=True, reason="CB-2162: difforme dal manuale, confermato")
async def test_gufo_aggiunge_60_piedi_alla_scurovisione_della_specie_2024(client):
    cid = await _barbarian(client, 6, WILD)
    r = await client.put(f"/characters/{cid}/species", json={"key": "2024_dwarf", "options": {}})
    assert r.status_code == 200, r.text
    assert await _scurovisione(client, cid) == 120
    await _pick(client, cid, "aspect_of_the_wilds", "owl")
    assert await _scurovisione(client, cid) == 180


@pytest.mark.caccia(id="CB-2163", fonte="2024 · Barbaro · Ira · pag. 51", zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("condizione", ["incapacitated", "stunned", "paralyzed", "unconscious"])
@pytest.mark.xfail(strict=True, reason="CB-2163: difforme dal manuale, confermato")
async def test_da_incapacitato_non_si_entra_in_ira(client, condizione):
    cid = await _barbarian(client, 5)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condizione: True}})
    assert r.status_code == 200, r.text
    await _rage(client, cid)
    assert await _rage_state(client, cid) is None
    assert (await _ability(client, cid, RAGE))["uses"] == 3


@pytest.mark.caccia(id="CB-2164", fonte="2024 · Barbaro, Cammino dell'Albero del Mondo · Forza Vivificante · pag. 56",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Forza Vivificante / Life-Giving Force (Vitalità dell'Albero, Cammino dell'Albero del Mondo 3, pag. 56)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /sessions/{session_id}/encounter/next-turn"])
@pytest.mark.xfail(strict=True, reason="CB-2164: difforme dal manuale, confermato")
async def test_forza_vivificante_solo_all_inizio_del_proprio_turno(client, test_session_factory, monkeypatch):
    sid, cid = await _barbaro_in_scontro(client, test_session_factory, monkeypatch, TREE)
    assert (await _rage(client, cid)).status_code == 200
    assert (await _use(client, cid, "life_giving_force")).status_code == 200
    await _turno_del_goblin(client, sid, cid)
    r = await _use(client, cid, "life_giving_force")
    assert r.status_code == 409, "nel turno di un altro combattente Forza Vivificante non si usa di nuovo"


@pytest.mark.caccia(id="CB-2165", fonte="2024 · Barbaro, Cammino dello Zelota · Furia Divina · pag. 57",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Furia Divina / Divine Fury (Cammino dello Zelota 3, pag. 57)",
                           "POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.xfail(strict=True, reason="CB-2165: difforme dal manuale, confermato")
async def test_furia_divina_solo_nel_proprio_turno(client, test_session_factory, monkeypatch):
    sid, cid = await _barbaro_in_scontro(client, test_session_factory, monkeypatch, ZEALOT)
    assert (await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 16})).status_code == 200
    ascia = await _weapon(client, cid)
    assert (await _rage(client, cid)).status_code == 200
    await _turno_del_goblin(client, sid, cid)
    colpo = await client.post(f"/characters/{cid}/items/{ascia}/attack",
                              json={"die": 10, "defer_damage": True, "confirm_extra_attack": True})
    assert colpo.status_code == 200, colpo.text
    r = await _damage(client, cid, colpo.json(), ["barbarian.divine_fury_radiant"])
    assert r.status_code == 409, "un attacco nel turno di un altro non porta la Furia Divina"


@pytest.mark.caccia(id="CB-2166", fonte="2024 · Barbaro · Ira · pag. 51; 2024 · Druido · Regole della Forma Selvatica · pag. 81",
                    zona="regola:2024/barbarian", voce="interazione",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
                           "POST /characters/{char_id}/companions/{comp_id}/attack", "POST /characters/{char_id}/turn/new"])
async def test_il_tiro_per_colpire_della_forma_selvatica_prolunga_l_ira(client):
    cid = await _druid24(client, 2)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 2, "hit_die": 12})
    assert r.status_code == 201, r.text
    bestia = {**_beast(0.25), "actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"}]}
    forma = await _form(client, cid, bestia)
    assert (await _activate(client, cid, forma)).status_code == 200
    await _new_turn(client, cid)  # la Forma Selvatica 2024 ha speso l'azione bonus del turno
    assert (await _rage(client, cid)).status_code == 200
    await _new_turn(client, cid)  # fine del turno in cui è nata: l'Ira arriva alla fine del turno seguente
    morso = await client.post(f"/characters/{cid}/companions/{forma}/attack",
                              json={"action_index": 0, "mode": "normal", "dice": [10], "damage_rolls": [3]})
    assert morso.status_code == 200, morso.text
    await _new_turn(client, cid)  # fine del turno con un tiro per colpire contro un nemico
    assert await _rage_state(client, cid) is not None


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2167", fonte="2024 · Barbaro · Ira (Danni dell'Ira) · pag. 51", zona="regola:2024/barbarian", voce="limiti",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.parametrize("livello, bonus", [(1, 2), (8, 2), (9, 3), (15, 3), (16, 4), (20, 4)])
async def test_bonus_ai_danni_dell_ira_ai_livelli_di_soglia(client, livello, bonus):
    cid = await _barbarian(client, livello, strength=16)
    ascia = await _weapon(client, cid)
    senza = (await _attack(client, cid, ascia))["damage_bonus"]
    await _new_turn(client, cid)
    assert (await _rage(client, cid)).status_code == 200
    assert (await _attack(client, cid, ascia))["damage_bonus"] - senza == bonus


@pytest.mark.caccia(id="CB-2168", fonte="2024 · Barbaro · Ira · pag. 51; 2014 · Barbaro · Ira · pag. 48", zona="regola:2024/barbarian",
                    voce="edizioni",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)"])
@pytest.mark.parametrize("edizione, usi", [("2014", None), ("2024", 6)])
async def test_ire_al_ventesimo_livello_per_edizione(client, edizione, usi):
    body = {"name": "Barbaro", "initial_class": {"class_name": "barbarian", "level": 20, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    assert (await _ability(client, cid, RAGE))["max_uses"] == usi


@pytest.mark.caccia(id="CB-2169", fonte="2024 · Barbaro · Potenza Indomabile · pag. 53; 2014 · Barbaro · Potenza Indomabile · pag. 49",
                    zona="regola:2024/barbarian", voce="edizioni",
                    copre=["carta:2024/classes/barbarian.md#Potenza Indomabile / Indomitable Might (Barbaro 18, pag. 53)",
                           "carta:2014/classes/barbarian.md#Potenza Indomabile / Indomitable Might (Barbaro 18, pag. 49)",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("edizione, al_punteggio", [("2014", False), ("2024", True)])
async def test_potenza_indomabile_sui_tiri_salvezza_di_forza_per_edizione(client, edizione, al_punteggio):
    body = {"name": "Barbaro", "initial_class": {"class_name": "barbarian", "level": 18, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 20})).status_code == 200
    r = await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 1})
    assert r.status_code == 200, r.text
    assert (r.json()["total"] >= 20) is al_punteggio


@pytest.mark.caccia(id="CB-2170", fonte="2024 · Barbaro · Conoscenza Primordiale · pag. 52; Potenza Indomabile · pag. 53",
                    zona="regola:2024/barbarian", voce="interazione",
                    copre=["carta:2024/classes/barbarian.md#Conoscenza Primordiale / Primal Knowledge (Barbaro 3, pag. 52)",
                           "carta:2024/classes/barbarian.md#Potenza Indomabile / Indomitable Might (Barbaro 18, pag. 53)",
                           "POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_prova_di_conoscenza_primordiale_e_una_prova_di_forza_per_potenza_indomabile(client):
    cid = await _barbarian(client, 18, strength=20, dexterity=10)
    assert (await _rage(client, cid)).status_code == 200
    r = await client.post(f"/characters/{cid}/skills/acrobatics/roll",
                          json={"die": 1, "dice": [1, 1], "options": ["barbarian.primal_knowledge"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 20


@pytest.mark.caccia(id="CB-2171", fonte="2024 · Barbaro · Padronanza delle Armi · pag. 52; Aspetto della Natura Selvaggia · pag. 55",
                    zona="regola:2024/barbarian", voce="interazione",
                    copre=["carta:2024/classes/barbarian.md#Padronanza delle Armi / Weapon Mastery (Barbaro 1, pag. 52)",
                           "carta:2024/classes/barbarian.md#Aspetto della Natura Selvaggia / Aspect of the Wilds (Cammino del Cuore Selvaggio 6, pag. 55)",
                           "POST /characters/{char_id}/classes/{class_id}/options/replace"])
async def test_cambiare_l_aspetto_non_consuma_il_cambio_della_padronanza(client):
    cid = await _barbarian(client, 6, WILD)
    scelta = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "weapon_mastery")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve",
                          json={"kind": "class_option", "options": ["greataxe", "handaxe", "maul"]})
    assert r.status_code == 200, r.text
    await _pick(client, cid, "aspect_of_the_wilds", "owl")
    await _riposo_lungo(client, cid)
    url = await _url_sostituzione(client, cid)
    aspetto = await client.post(url, json={"group": "aspect_of_the_wilds", "old_key": "owl", "new_key": "panther"})
    assert aspetto.status_code == 200, aspetto.text
    arma = await client.post(url, json={"group": "weapon_mastery", "old_key": "maul", "new_key": "greatsword"})
    assert arma.status_code == 200, arma.text


@pytest.mark.caccia(id="CB-2172", fonte="2024 · Barbaro · Ira Implacabile · pag. 53", zona="regola:2024/barbarian", voce="limiti",
                    copre=["carta:2024/classes/barbarian.md#Ira Implacabile / Relentless Rage (Barbaro 11, pag. 53)",
                           "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/classes"])
async def test_ira_implacabile_in_multiclasse_usa_il_livello_da_barbaro(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11, constitution=14)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    await _hp(client, cid, 40, 40)
    assert (await _rage(client, cid)).status_code == 200
    corpo = await _hit(client, cid, 45)
    assert corpo["zero_hp_save"]["success"] is True
    assert corpo["current_hit_points"] == 22


@pytest.mark.caccia(id="CB-2173", fonte="2024 · Barbaro · Ira Implacabile · pag. 53", zona="regola:2024/barbarian", voce="annullamento",
                    copre=["carta:2024/classes/barbarian.md#Ira Implacabile / Relentless Rage (Barbaro 11, pag. 53)",
                           "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_colpo_restituisce_la_cd_di_ira_implacabile(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11, constitution=14)
    await _hp(client, cid, 40, 40)
    assert (await _rage(client, cid)).status_code == 200
    primo = await _hit(client, cid, 45)
    assert primo["zero_hp_save"]["dc"] == 10
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": primo["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert (await _hit(client, cid, 45))["zero_hp_save"]["dc"] == 10


@pytest.mark.caccia(id="CB-2174", fonte="2024 · Barbaro · Ira · pag. 51", zona="regola:2024/barbarian", voce="ripetizione",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_un_doppio_invio_dell_ira_spende_un_solo_uso(client):
    cid = await _barbarian(client, 5)
    assert (await _rage(client, cid)).status_code == 200
    assert (await _rage(client, cid)).status_code == 409
    assert (await _ability(client, cid, RAGE))["uses"] == 2

