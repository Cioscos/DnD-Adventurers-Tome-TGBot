"""Controlli della zona regola:2014/barbarian."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_barbarian import (
    BERSERKER, RAGE, _ability, _armor, _attack, _barbarian, _full, _rage, _states, _weapon,
)
from tests.integration.rules.test_2014_druid import _activate, _beast, _form
from tests.integration.test_magic_items import _item


def _in_ira(stati: list[dict]) -> bool:
    return any(s["key"] == "rage" for s in stati)


async def _in_scontro(client, factory, monkeypatch, *classi: tuple[str, int, int]) -> tuple[int, int]:
    """Serata con incontro avviato: tocca al PG (iniziativa 17), poi ai due goblin. Le classi si aggiungono al PG."""
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, factory)
    pg = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    as_user(PLAYER_ID)
    cid = pg["character_id"]
    for nome, livello, dado in classi:
        r = await client.post(f"/characters/{cid}/classes", json={"class_name": nome, "level": livello, "hit_die": dado})
        assert r.status_code == 201, r.text
    return sid, cid


async def _turno_dopo(client, sid, volte=1) -> None:
    as_user(GM_ID)
    for _ in range(volte):
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1561", fonte="2014 · Barbaro · Ira · pag. 48", zona="regola:2014/barbarian", voce="regola",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "POST /characters/{char_id}/turn/new"])
@pytest.mark.xfail(strict=True, reason="CB-1561: difforme dal manuale, confermato")
async def test_fuori_scontro_un_turno_senza_attacchi_ne_danni_chiude_l_ira(client):
    cid = await _barbarian(client, 3, strength=16)
    spada = await _weapon(client, cid)
    assert (await _rage(client, cid)).status_code == 200
    await _attack(client, cid, spada)
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200  # ha attaccato: l'ira resta
    assert _in_ira(await _states(client, cid))
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200  # un turno intero senza attacchi né danni
    assert not _in_ira(await _states(client, cid))


@pytest.mark.caccia(id="CB-1562", fonte="2014 · Barbaro · Ira · pag. 48", zona="regola:2014/barbarian", voce="regola",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "POST /sessions/{session_id}/encounter/next-turn", "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.xfail(strict=True, reason="CB-1562: difforme dal manuale, confermato")
async def test_l_attacco_fatto_nel_turno_di_un_nemico_tiene_viva_l_ira(client, test_session_factory, monkeypatch):
    sid, cid = await _in_scontro(client, test_session_factory, monkeypatch, ("barbarian", 3, 12))
    spada = await _weapon(client, cid)
    assert (await _rage(client, cid)).status_code == 200
    await _attack(client, cid, spada)
    await _turno_dopo(client, sid)  # fine del turno del PG: ha attaccato, l'ira resta; tocca al primo goblin
    assert _in_ira(await _states(client, cid))
    await _attack(client, cid, spada)  # attacco di opportunità nel turno del goblin
    await _turno_dopo(client, sid, 3)  # secondo goblin, turno del PG senza attacchi né danni, fine del suo turno
    assert _in_ira(await _states(client, cid))  # dal turno precedente ha attaccato una creatura ostile


@pytest.mark.caccia(id="CB-1563", fonte="2014 · Barbaro · Cammino del Berserker · Frenesia · pag. 49", zona="regola:2014/barbarian",
                    voce="limiti", copre=["carta:2014/classes/barbarian.md#Frenesia / Frenzy (Cammino del Berserker 3, pag. 49)",
                                          "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.xfail(strict=True, reason="CB-1563: difforme dal manuale, confermato")
async def test_la_frenesia_non_si_sceglie_prima_del_terzo_livello(client):
    cid = await _barbarian(client, 2, BERSERKER)
    assert (await _rage(client, cid, frenzy=True)).status_code == 200
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
    assert not (await _full(client, cid))["conditions"].get("exhaustion")


@pytest.mark.caccia(id="CB-1564", fonte="2014 · Barbaro · Ira · pag. 48", zona="regola:2014/barbarian", voce="regola",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "POST /characters/{char_id}/items/{item_id}/cast"])
@pytest.mark.xfail(strict=True, reason="CB-1564: difforme dal manuale, confermato")
async def test_in_ira_non_si_lancia_un_incantesimo_da_un_oggetto(client):
    cid = await _barbarian(client, 3)
    incantesimo = {"name": "Raggio Fantasma", "level": 2, "charges_cost": 1, "is_concentration": True,
                   "duration": "Concentration, up to 1 minute"}
    bacchetta = await _item(client, cid, name="Bacchetta", charges={"current": 5, "max": 5}, granted_spells=[incantesimo])
    assert (await _rage(client, cid)).status_code == 200
    r = await client.post(f"/characters/{cid}/items/{bacchetta}/cast", json={"spell_index": 0})
    assert r.status_code == 409 and "state_blocks_casting" in r.text


@pytest.mark.caccia(id="CB-1565", fonte="2014 · Barbaro · Ira · pag. 48; 2014 · Druido · Forma Selvatica · pag. 66 (si mantengono i privilegi di classe)",
                    zona="regola:2014/barbarian", voce="interazione",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "POST /characters/{char_id}/companions/{comp_id}/attack", "POST /sessions/{session_id}/encounter/next-turn"])
async def test_l_attacco_della_forma_selvatica_tiene_viva_l_ira(client, test_session_factory, monkeypatch):
    sid, cid = await _in_scontro(client, test_session_factory, monkeypatch, ("barbarian", 2, 12), ("druid", 2, 8))
    bestia = {**_beast(0.25), "actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"}]}
    forma = await _form(client, cid, bestia)
    assert (await _activate(client, cid, forma)).status_code == 200
    assert (await _rage(client, cid)).status_code == 200
    r = await client.post(f"/characters/{cid}/companions/{forma}/attack",
                          json={"action_index": 0, "mode": "normal", "dice": [10], "damage_rolls": [3]})
    assert r.status_code == 200, r.text
    assert _in_ira(await _states(client, cid))
    await _turno_dopo(client, sid)  # fine del turno del PG: la forma ha attaccato
    assert _in_ira(await _states(client, cid))


@pytest.mark.caccia(id="CB-1566", fonte="2014 · Barbaro · Attacco Irruento · pag. 48", zona="regola:2014/barbarian", voce="regola",
                    copre=["carta:2014/classes/barbarian.md#Attacco Irruento / Reckless Attack (Barbaro 2, pag. 48)",
                           "POST /characters/{char_id}/turn/new"])
@pytest.mark.xfail(strict=True, reason="CB-1566: difforme dal manuale, confermato")
async def test_il_vantaggio_concesso_dall_attacco_irruento_finisce_al_turno_seguente(client):
    cid = await _barbarian(client, 2, strength=16)
    spada = await _weapon(client, cid)
    await _attack(client, cid, spada, options=["barbarian.reckless_attack"])
    assert any(s["key"] == "reckless" for s in await _states(client, cid))
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200  # comincia il suo turno successivo
    assert not any(s["key"] == "reckless" for s in await _states(client, cid))


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1567", fonte="2014 · Barbaro · Ira (colonna Danni dell'Ira) · pag. 48", zona="regola:2014/barbarian", voce="limiti",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.parametrize("livello, bonus", [(1, 2), (8, 2), (9, 3), (15, 3), (16, 4), (20, 4)])
async def test_bonus_ai_danni_dell_ira_per_livello(client, livello, bonus):
    cid = await _barbarian(client, livello, strength=16)
    spada = await _weapon(client, cid)
    senza = (await _attack(client, cid, spada))["damage_bonus"]
    await _rage(client, cid)
    assert (await _attack(client, cid, spada))["damage_bonus"] - senza == bonus


@pytest.mark.caccia(id="CB-1568", fonte="2014 · Barbaro · Ira (colonna Ira) e Campione Primordiale · pag. 48-49", zona="regola:2014/barbarian",
                    voce="limiti", copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                                          "carta:2014/classes/barbarian.md#Campione Primordiale / Primal Champion (Barbaro 20, pag. 49)",
                                          "POST /characters"])
@pytest.mark.parametrize("livello, usi", [(1, 2), (2, 2), (3, 3), (5, 3), (6, 4), (11, 4), (12, 5), (16, 5), (17, 6), (19, 6), (20, None)])
async def test_usi_dell_ira_dalla_tabella_di_classe(client, livello, usi):
    ira = await _ability(client, await _barbarian(client, livello), RAGE)
    assert (ira["max_uses"], ira["restoration_type"]) == (usi, "long_rest")


@pytest.mark.caccia(id="CB-1569", fonte="2014 · Barbaro · Difesa Senza Armatura · pag. 48", zona="regola:2014/barbarian", voce="regola",
                    copre=["carta:2014/classes/barbarian.md#Difesa Senza Armatura / Unarmored Defense (Barbaro 1, pag. 48)",
                           "PATCH /characters/{char_id}/items/{item_id}"])
async def test_difesa_senza_armatura_con_lo_scudo(client):
    cid = await _barbarian(client, 1, dexterity=14, constitution=16)
    assert (await _full(client, cid))["ac"] == 15  # 10 + DES 2 + COS 3
    await _item(client, cid, name="Scudo", item_type="shield", slot="off_hand", ac_bonus=2)
    assert (await _full(client, cid))["ac"] == 17


@pytest.mark.caccia(id="CB-1570", fonte="2014 · Barbaro · Ira · pag. 48", zona="regola:2014/barbarian", voce="regola",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "POST /sessions/{session_id}/encounter/next-turn"])
@pytest.mark.parametrize("attacca, resta", [(False, False), (True, True)])
async def test_nello_scontro_l_ira_finisce_a_fine_turno_senza_attacchi_ne_danni(client, test_session_factory, monkeypatch, attacca, resta):
    sid, cid = await _in_scontro(client, test_session_factory, monkeypatch, ("barbarian", 3, 12))
    spada = await _weapon(client, cid)
    assert (await _rage(client, cid)).status_code == 200
    if attacca:
        await _attack(client, cid, spada)
    await _turno_dopo(client, sid)
    assert _in_ira(await _states(client, cid)) is resta


@pytest.mark.caccia(id="CB-1571", fonte="2014 · Barbaro · Ira · pag. 48 (finisce se privo di sensi); 2024 · Barbaro · Ira · pag. 51 (finisce con Incapacitato)",
                    zona="regola:2014/barbarian", voce="edizioni",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("edizione, resta", [("2014", True), ("2024", False)])
async def test_stordito_ma_cosciente_l_ira_resta_solo_nel_2014(client, edizione, resta):
    cid = await _barbarian(client, 5)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    assert (await _rage(client, cid)).status_code == 200
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert _in_ira(await _states(client, cid)) is resta


@pytest.mark.caccia(id="CB-1572", fonte="2014 · Barbaro · Ira · pag. 48 (riposo lungo); 2024 · Barbaro · Ira · pag. 51 (il riposo breve ne ridà uno)",
                    zona="regola:2014/barbarian", voce="edizioni",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("edizione, dopo_breve", [("2014", 1), ("2024", 2)])
async def test_il_riposo_breve_ridà_un_ira_solo_nel_2024(client, edizione, dopo_breve):
    cid = await _barbarian(client, 1)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    assert (await _rage(client, cid)).status_code == 200
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, RAGE))["uses"] == dopo_breve
