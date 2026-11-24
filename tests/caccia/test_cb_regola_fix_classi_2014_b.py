"""Controlli scritti dai correttori del gruppo classi-2014-b per i dubbi «Q-…» che i verificatori hanno risolto come difetti."""
import pytest

from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.test_campaigns_api import act

GM, PA, PB = 1234, 5678, 9002


async def _pg(client, classe: dict, **punteggi) -> int:
    r = await client.post("/characters", json={"name": "Prova", "rules_edition": "2014", "initial_class": classe})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _serata(client, *seduti: tuple[int, int]) -> tuple[int, str]:
    """Il GM apre una serata e ogni (utente, personaggio) ci si siede."""
    act(GM)
    r = await client.post("/sessions", json={})
    assert r.status_code == 201, r.text
    sid, codice = r.json()["id"], r.json()["code"]
    for utente, cid in seduti:
        act(utente)
        assert (await client.post("/sessions/join", json={"code": codice, "character_id": cid})).status_code == 200
    return sid, codice


@pytest.mark.caccia(id="CB-4431", fonte="2014 · Monaco · Discepolo degli Elementi · pag. 93", zona="regola:2014/monk", voce="regola",
                    copre=["carta:2014/classes/monk.md#Discepolo degli Elementi / Disciple of the Elements (Monaco 3, pag. 93)",
                           "POST /characters/{char_id}/classes/{class_id}/options/replace"])
@pytest.mark.xfail(strict=True, reason="CB-4431: Q-2014-monk-1 rinviato, serve un legame fra sostituzione e disciplina nuova (scelta dell'utente)")
async def test_una_disciplina_si_sostituisce_solo_quando_se_ne_impara_una_nuova(client):
    # «Ogni volta che ne impara una, può sostituirne una già conosciuta»: al 3° non se ne impara un'altra, niente cambio
    cid = await _pg(client, {"class_name": "monk", "level": 3, "subclass": "Via dei Quattro Elementi"})
    scheda = await _scheda(client, cid)
    scelta = next(c for c in scheda["pending_choices"] if c.get("group") == "elemental_disciplines")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": ["water_whip"]})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/classes/{scheda['classes'][0]['id']}/options/replace",
                          json={"group": "elemental_disciplines", "old_key": "water_whip", "new_key": "fist_of_unbroken_air"})
    assert r.status_code in (409, 422), r.status_code


@pytest.mark.caccia(id="CB-4432", fonte="2014 · Paladino · Collera della Natura · pag. 100", zona="regola:2014/paladin", voce="interazione",
                    copre=["carta:2014/classes/paladin.md#Collera della Natura / Nature's Wrath (Incanalare Divinità, Giuramento degli Antichi, Paladino 3, pag. 100)",
                           "POST /characters/{char_id}/target-effects", "POST /characters/{char_id}/pending-saves/{psid}/roll"])
@pytest.mark.xfail(strict=True, reason="CB-4432: Q-2014-paladin-1 rinviato, scelta automatica (A) o del bersaglio (B, schema) da decidere")
async def test_collera_della_natura_il_bersaglio_puo_usare_la_destrezza(client, monkeypatch):
    # TS su Forza o Destrezza a scelta del bersaglio: con Destrezza 16 (+3) e 11 al dado arriva a 14, la CD
    install_fake_telegram(monkeypatch)
    act(PA)
    pal = await _pg(client, {"class_name": "paladin", "level": 5, "subclass": "Giuramento degli Antichi"}, charisma=16)  # CD 8 + 3 + 3
    act(PB)
    bersaglio = await _pg(client, {"class_name": "fighter", "level": 1}, strength=8, dexterity=16)
    sid, _ = await _serata(client, (PA, pal), (PB, bersaglio))
    act(GM)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    lottatori = {c.get("character_id"): c for c in r.json()["combatants"]}
    for utente, cid, dado in ((PA, pal, 15), (PB, bersaglio, 5)):
        act(utente)
        r = await client.post(f"/sessions/{sid}/encounter/combatants/{lottatori[cid]['id']}/initiative", json={"die": dado})
        assert r.status_code == 200, r.text
    act(GM)
    assert (await client.post(f"/sessions/{sid}/encounter/start", json={})).status_code == 200
    act(PA)
    assert (await client.post(f"/characters/{pal}/features/paladin.natures_wrath/use", json={})).status_code == 200
    r = await client.post(f"/characters/{pal}/target-effects",
                          json={"combatant_id": lottatori[bersaglio]["id"], "effect_key": "paladin.natures_wrath"})
    assert r.status_code == 200, r.text
    act(PB)
    r = await client.post(f"/characters/{bersaglio}/pending-saves/{r.json()['pending_save_id']}/roll",
                          json={"die": 11, "ability": "dexterity"})
    assert r.status_code == 200, r.text
    assert r.json()["passed"] is True


@pytest.mark.caccia(id="CB-4433", fonte="2014 · Paladino · Tocco Purificatore · pag. 98", zona="regola:2014/paladin", voce="interazione",
                    copre=["carta:2014/classes/paladin.md#Tocco Purificatore / Cleansing Touch (Paladino 14, pag. 98)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_tocco_purificatore_termina_un_incantesimo_su_di_se_anche_lanciato_da_un_altro(client, monkeypatch):
    # «Termina un incantesimo su di sé»: Scudo della Fede del chierico sul paladino finisce, e il chierico non lo mantiene più
    install_fake_telegram(monkeypatch)
    act(PA)
    pal = await _pg(client, {"class_name": "paladin", "level": 14}, charisma=16)
    act(PB)
    chierico = await _pg(client, {"class_name": "cleric", "level": 1}, wisdom=16)
    await _serata(client, (PA, pal), (PB, chierico))
    act(PB)
    classe = (await _scheda(client, chierico))["classes"][0]["id"]
    r = await client.post(f"/characters/{chierico}/spells", json={
        "name": "Scudo della Fede", "srd_index": "shield-of-faith", "level": 1, "is_prepared": True, "class_id": classe,
        "is_concentration": True, "casting_time": "1 azione bonus"})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{chierico}/spells/{r.json()['id']}/use", json={"slot_level": 1, "targets": [pal]})
    assert r.status_code == 200, r.text
    act(PA)
    stato = next(s["key"] for s in (await _scheda(client, pal))["active_states"] if s["key"].startswith("spell:"))
    riga = next(a for a in (await _scheda(client, pal))["abilities"] if a["feature_key"] == "paladin.cleansing_touch")
    offerti = {o["key"]: o["label"]["it"] for o in (riga["removal"] or {}).get("conditions", [])}
    assert offerti.get(stato) == "Scudo della Fede", offerti
    r = await client.post(f"/characters/{pal}/features/paladin.cleansing_touch/use",
                          json={"params": {"removal": {"targets": ["self"], "conditions": [stato]}}})
    assert r.status_code == 200, r.text
    assert stato not in [s["key"] for s in (await _scheda(client, pal))["active_states"] or []]
    act(PB)
    lanciatore = await _scheda(client, chierico)
    assert not [s for s in lanciatore["active_states"] or [] if s["key"].startswith("spell_cast:")]
    assert lanciatore["concentrating_spell_id"] is None
