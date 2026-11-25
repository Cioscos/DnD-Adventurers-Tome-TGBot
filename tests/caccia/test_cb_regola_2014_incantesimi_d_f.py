"""Controlli della zona regola:2014/incantesimi-D-F (parte incantesimi-d-f)."""
import json
from pathlib import Path

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat

_CATALOGO = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells.json"
SRD = {x["index"]: x for x in json.loads(_CATALOGO.read_text(encoding="utf-8"))["items"]}


def _dal_catalogo(indice: str) -> dict:
    """La scheda che la webapp manda aggiungendo l'incantesimo dal catalogo 2014 (spellToForm, in italiano)."""
    e = SRD[indice]
    materiale = (e.get("material") or {}).get("it", "").rstrip(".")
    corpo = {
        "name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
        "is_concentration": e["concentration"], "is_ritual": e["ritual"], "school": e["school"], "srd_index": indice,
        "components": ", ".join(e["components"]) + (f" ({materiale})" if materiale and "M" in e["components"] else ""),
        "attack_save": e.get("attack_type"), "damage_dice": e.get("damage_dice"), "damage_type": e.get("damage_type"),
        "higher_levels_dice": e.get("higher_levels_dice") if e.get("damage_dice") else None, "is_prepared": True,
    }
    return {k: v for k, v in corpo.items() if v not in (None, "")}


async def _pg(client, classe: str, livello: int) -> int:
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": "2014",
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _impara(client, cid: int, indice: str) -> int:
    r = await client.post(f"/characters/{cid}/spells", json=_dal_catalogo(indice))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _scheda(client, cid: int) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _danni(client, cid: int, sid: int, **corpo) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json=corpo)
    assert r.status_code == 200, r.text
    return r.json()


async def _serata(client, factory, classe: str, livello: int, indice: str) -> tuple[int, int, int]:
    """Una serata con un eroe (utente giocatore, 20 PF) e chi lancia (utente GM) che conosce l'incantesimo: ``(eroe, lanciatore, incantesimo)``."""
    _, eroe = await seed_session(factory)
    as_user(GM_ID)
    cid = await _pg(client, classe, livello)
    sid = await _impara(client, cid, indice)
    await _seat(factory, cid, GM_ID)
    as_user(PLAYER_ID)
    for op in ("set_max", "set_current"):
        assert (await client.patch(f"/characters/{eroe}/hp", json={"op": op, "value": 20})).status_code == 200
    return eroe, cid, sid


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3261", fonte="2014 · Incantesimi · Dominare Bestie, Dominare Persone, Dominare Mostri (durata con slot superiori) · pag. 231-232",
                    zona="regola:2014/incantesimi-D-F", voce="limiti",
                    copre=["carta:2014/spells.md#Dominare Bestie", "carta:2014/spells.md#Dominare Persone",
                           "carta:2014/spells.md#Dominare Mostri", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("classe, livello, indice, slot, round_attesi", [
    ("druid", 9, "dominate-beast", 5, 100), ("druid", 11, "dominate-beast", 6, 600), ("druid", 13, "dominate-beast", 7, 4800),
    ("bard", 11, "dominate-person", 6, 100), ("bard", 13, "dominate-person", 7, 600), ("bard", 15, "dominate-person", 8, 4800),
    ("sorcerer", 17, "dominate-monster", 9, 4800),
])
@pytest.mark.xfail(strict=True, reason="CB-3261: difforme dal manuale, confermato")
async def test_dominare_con_slot_superiore_allunga_la_concentrazione(client, classe, livello, indice, slot, round_attesi):
    cid = await _pg(client, classe, livello)
    sid = await _impara(client, cid, indice)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": slot})
    assert r.status_code == 200, r.text
    # 10 minuti = 100 round, 1 ora = 600, 8 ore = 4800: allo scadere del contatore la concentrazione finisce
    assert r.json()["settings"]["concentration_rounds_left"] == round_attesi


@pytest.mark.caccia(id="CB-3262", fonte="2014 · Incantesimi · Forma Gassosa (termina a 0 PF) · pag. 237", zona="regola:2014/incantesimi-D-F",
                    voce="regola",
                    copre=["carta:2014/spells.md#Forma Gassosa", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "PATCH /characters/{char_id}/hp"])
@pytest.mark.xfail(strict=True, reason="CB-3262: difforme dal manuale, confermato")
async def test_forma_gassosa_finisce_quando_il_bersaglio_scende_a_zero_pf(client, test_session_factory):
    eroe, cid, sid = await _serata(client, test_session_factory, "sorcerer", 5, "gaseous-form")
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 3, "targets": [eroe]})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    assert any(s["key"] == "spell:gaseous_form" for s in (await _scheda(client, eroe))["active_states"])
    assert (await client.patch(f"/characters/{eroe}/hp", json={"op": "damage", "value": 20})).status_code == 200
    assert not any(s["key"] == "spell:gaseous_form" for s in (await _scheda(client, eroe))["active_states"])


@pytest.mark.caccia(id="CB-3263", fonte="2014 · Incantesimi · Favore Divino (1d4 radiosi agli attacchi con arma, nessun danno al lancio) · pag. 235",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Favore Divino", "GET /characters/{char_id}/spells"])
async def test_favore_divino_non_tira_danni_al_lancio(client):
    cid = await _pg(client, "paladin", 2)
    await _impara(client, cid, "divine-favor")
    r = await client.get(f"/characters/{cid}/spells")
    assert r.status_code == 200, r.text
    favore = next(s for s in r.json() if s["srd_index"] == "divine-favor")
    # la regola del client (rollsDamageOnCast): dadi dell'incantesimo e nessun danno «al colpo» -> il lancio apre il tiro di danno
    assert not (favore["damage_dice"] and not (favore["effect"] or {}).get("hit_damage"))


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3265", fonte="2014 · Incantesimi · tabella degli incantesimi D-F (livello, tempo di lancio, componenti, concentrazione, rituale, classi) · pag. 211-238",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Fiotto Acido", "carta:2014/spells.md#Forme Animali", "carta:2014/spells.md#Esilio",
                           "carta:2014/spells.md#Faro di Speranza", "carta:2014/spells.md#Duello Obbligato", "carta:2014/spells.md#Evoca Animali",
                           "carta:2014/spells.md#Evoca Raffica", "carta:2014/spells.md#Evoca Celestiale", "carta:2014/spells.md#Evoca Elementale",
                           "carta:2014/spells.md#Evoca Folletto", "carta:2014/spells.md#Evoca Elementali Minori",
                           "carta:2014/spells.md#Evoca Pioggia di Armi", "carta:2014/spells.md#Evoca Creature Boschive",
                           "carta:2014/spells.md#Fiamma Perenne", "carta:2014/spells.md#Disintegrazione",
                           "carta:2014/spells.md#Dissolvi il Bene e il Male", "carta:2014/spells.md#Dissolvi Magie",
                           "carta:2014/spells.md#Divinazione", "carta:2014/spells.md#Favore Divino", "carta:2014/spells.md#Dominare Bestie",
                           "carta:2014/spells.md#Dominare Mostri", "carta:2014/spells.md#Dominare Persone",
                           "carta:2014/spells.md#Evocazioni Istantanee di Drawmij", "carta:2014/spells.md#Deflagrazione Occulta",
                           "carta:2014/spells.md#Estasiare", "carta:2014/spells.md#Forma Eterea", "carta:2014/spells.md#Fabbricare",
                           "carta:2014/spells.md#Dito della Morte", "carta:2014/spells.md#Dardo di Fuoco", "carta:2014/spells.md#Forma Gassosa",
                           "carta:2014/spells.md#Dardo Tracciante", "carta:2014/spells.md#Folata di Vento", "carta:2014/spells.md#Ferire",
                           "carta:2014/spells.md#Eroismo", "carta:2014/spells.md#Fame di Hadar", "carta:2014/spells.md#Freccia Folgorante",
                           "carta:2014/spells.md#Fulmine", "carta:2014/spells.md#Dardo Incantato", "carta:2014/spells.md#Fondersi nella Pietra",
                           "carta:2014/spells.md#Freccia Acida di Melf", "carta:2014/spells.md#Fuorviare",
                           "carta:2014/spells.md#Danza Irresistibile di Otto", "carta:2014/spells.md#Destriero Fantomatico",
                           "carta:2014/spells.md#Fiamma Sacra", "carta:2014/spells.md#Frantumare", "carta:2014/spells.md#Esplosione Solare",
                           "carta:2014/spells.md#Faretra Rapida", "carta:2014/spells.md#Disco Fluttuante di Tenser",
                           "carta:2014/spells.md#Frusta di Spine", "carta:2014/spells.md#Fermare il Tempo", "carta:2014/spells.md#Fatale",
                           "carta:2014/spells.md#Desiderio", "carta:2014/spells.md#Dardo Stregato"])
@pytest.mark.parametrize("indice, livello, lancio, componenti, concentrazione, rituale, classi", [
    ("acid-splash", 0, "1 action", "VS", False, False, "sorcerer wizard"),
    ("animal-shapes", 8, "1 action", "VS", True, False, "druid"),
    ("banishment", 4, "1 action", "VSM", True, False, "cleric paladin sorcerer warlock wizard"),
    ("beacon-of-hope", 3, "1 action", "VS", True, False, "cleric"),
    ("compelled-duel", 1, "1 bonus action", "V", True, False, "paladin"),
    ("conjure-animals", 3, "1 action", "VS", True, False, "druid ranger"),
    ("conjure-barrage", 3, "1 action", "VSM", False, False, "ranger"),
    ("conjure-celestial", 7, "1 minute", "VS", True, False, "cleric"),
    ("conjure-elemental", 5, "1 minute", "VSM", True, False, "druid wizard"),
    ("conjure-fey", 6, "1 minute", "VS", True, False, "druid warlock"),
    ("conjure-minor-elementals", 4, "1 minute", "VS", True, False, "druid wizard"),
    ("conjure-volley", 5, "1 action", "VSM", False, False, "ranger"),
    ("conjure-woodland-beings", 4, "1 action", "VSM", True, False, "druid ranger"),
    ("continual-flame", 2, "1 action", "VSM", False, False, "cleric wizard"),
    ("disintegrate", 6, "1 action", "VSM", False, False, "sorcerer wizard"),
    ("dispel-evil-and-good", 5, "1 action", "VSM", True, False, "cleric paladin"),
    ("dispel-magic", 3, "1 action", "VS", False, False, "bard cleric druid paladin sorcerer warlock wizard"),
    ("divination", 4, "1 action", "VSM", False, True, "cleric"),
    ("divine-favor", 1, "1 bonus action", "VS", True, False, "paladin"),
    ("dominate-beast", 4, "1 action", "VS", True, False, "druid sorcerer"),
    ("dominate-monster", 8, "1 action", "VS", True, False, "bard sorcerer warlock wizard"),
    ("dominate-person", 5, "1 action", "VS", True, False, "bard sorcerer wizard"),
    ("instant-summons", 6, "1 minute", "VSM", False, True, "wizard"),
    ("eldritch-blast", 0, "1 action", "VS", False, False, "warlock"),
    ("enthrall", 2, "1 action", "VS", False, False, "bard warlock"),
    ("etherealness", 7, "1 action", "VS", False, False, "bard cleric sorcerer warlock wizard"),
    ("fabricate", 4, "10 minutes", "VS", False, False, "wizard"),
    ("finger-of-death", 7, "1 action", "VS", False, False, "sorcerer warlock wizard"),
    ("fire-bolt", 0, "1 action", "VS", False, False, "sorcerer wizard"),
    ("gaseous-form", 3, "1 action", "VSM", True, False, "sorcerer warlock wizard"),
    ("guiding-bolt", 1, "1 action", "VS", False, False, "cleric"),
    ("gust-of-wind", 2, "1 action", "VSM", True, False, "druid sorcerer wizard"),
    ("harm", 6, "1 action", "VS", False, False, "cleric"),
    ("heroism", 1, "1 action", "VS", True, False, "bard paladin"),
    ("hunger-of-hadar", 3, "1 action", "VSM", True, False, "warlock"),
    ("lightning-arrow", 3, "1 bonus action", "VS", True, False, "ranger"),
    ("lightning-bolt", 3, "1 action", "VSM", False, False, "sorcerer wizard"),
    ("magic-missile", 1, "1 action", "VS", False, False, "sorcerer wizard"),
    ("meld-into-stone", 3, "1 action", "VS", False, True, "cleric druid"),
    ("acid-arrow", 2, "1 action", "VSM", False, False, "wizard"),
    ("mislead", 5, "1 action", "S", True, False, "bard wizard"),
    ("irresistible-dance", 6, "1 action", "V", True, False, "bard wizard"),
    ("phantom-steed", 3, "1 minute", "VS", False, True, "wizard"),
    ("sacred-flame", 0, "1 action", "VS", False, False, "cleric"),
    ("shatter", 2, "1 action", "VSM", False, False, "bard sorcerer warlock wizard"),
    ("sunburst", 8, "1 action", "VSM", False, False, "druid sorcerer wizard"),
    ("swift-quiver", 5, "1 bonus action", "VSM", True, False, "ranger"),
    ("floating-disk", 1, "1 action", "VSM", False, True, "wizard"),
    ("thorn-whip", 0, "1 action", "VSM", False, False, "druid"),
    ("time-stop", 9, "1 action", "V", False, False, "sorcerer wizard"),
    ("weird", 9, "1 action", "VS", True, False, "wizard"),
    ("wish", 9, "1 action", "V", False, False, "sorcerer wizard"),
    ("witch-bolt", 1, "1 action", "VSM", True, False, "sorcerer warlock wizard"),
])
def test_catalogo_2014_dati_meccanici_come_le_carte(indice, livello, lancio, componenti, concentrazione, rituale, classi):
    e = SRD[indice]
    assert (e["level"], e["casting_time"]["en"], "".join(e["components"]), e["concentration"], e["ritual"], " ".join(sorted(e["classes"]))) == \
        (livello, lancio, componenti, concentrazione, rituale, classi)


@pytest.mark.caccia(id="CB-3266", fonte="2014 · Incantesimi · Dardo di Fuoco, Fiamma Sacra, Fiotto Acido, Frusta di Spine, Deflagrazione Occulta (trucchetti al 5°, 11°, 17°) · pag. 228-238",
                    zona="regola:2014/incantesimi-D-F", voce="limiti",
                    copre=["carta:2014/spells.md#Dardo di Fuoco", "carta:2014/spells.md#Fiamma Sacra", "carta:2014/spells.md#Fiotto Acido",
                           "carta:2014/spells.md#Frusta di Spine", "carta:2014/spells.md#Deflagrazione Occulta",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("indice, classe, livello, dadi, facce", [
    ("fire-bolt", "wizard", 4, 1, 10), ("fire-bolt", "wizard", 5, 2, 10), ("fire-bolt", "wizard", 10, 2, 10),
    ("fire-bolt", "wizard", 11, 3, 10), ("fire-bolt", "wizard", 16, 3, 10), ("fire-bolt", "wizard", 17, 4, 10),
    ("sacred-flame", "cleric", 5, 2, 8), ("acid-splash", "sorcerer", 11, 3, 6), ("thorn-whip", "druid", 17, 4, 6),
    ("eldritch-blast", "warlock", 20, 4, 10),
])
async def test_i_trucchetti_crescono_al_5_11_17_livello(client, indice, classe, livello, dadi, facce):
    cid = await _pg(client, classe, livello)
    sid = await _impara(client, cid, indice)
    esito = await _danni(client, cid, sid)
    assert (len(esito["main_rolls"]), esito["main_kind"]) == (dadi, f"d{facce}")


@pytest.mark.caccia(id="CB-3267", fonte="2014 · Incantesimi · Deflagrazione Occulta (raggi secondo il livello del personaggio) · pag. 229",
                    zona="regola:2014/incantesimi-D-F", voce="interazione",
                    copre=["carta:2014/spells.md#Deflagrazione Occulta", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_deflagrazione_occulta_in_multiclasse_conta_il_livello_del_personaggio(client):
    cid = await _pg(client, "warlock", 1)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 4, "hit_die": 10})
    assert r.status_code == 201, r.text
    sid = await _impara(client, cid, "eldritch-blast")
    assert len((await _danni(client, cid, sid))["main_rolls"]) == 2  # personaggio di 5° livello: due raggi


@pytest.mark.caccia(id="CB-3268", fonte="2014 · Incantesimi · Disintegrazione (10d6 + 40, niente a TS superato, +3d6 per slot) · pag. 230",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Disintegrazione", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi", [(6, 10), (7, 13), (9, 19)])
async def test_disintegrazione_dieci_d6_piu_quaranta_e_tre_d6_per_slot(client, slot, dadi):
    cid = await _pg(client, "sorcerer", 17)
    sid = await _impara(client, cid, "disintegrate")
    esito = await _danni(client, cid, sid, casting_level=slot, main_rolls=[1] * dadi)
    assert (esito["total"], esito["main_kind"], esito["save_halves"]) == (dadi + 40, "d6", False)


@pytest.mark.caccia(id="CB-3269", fonte="2014 · Incantesimi · Dardo Incantato (3 dardi da 1d4 + 1, uno in più per slot) · pag. 228",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Dardo Incantato", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dardi", [(1, 3), (3, 5)])
async def test_dardo_incantato_un_dardo_in_piu_per_slot(client, slot, dardi):
    cid = await _pg(client, "sorcerer", 5)
    sid = await _impara(client, cid, "magic-missile")
    esito = await _danni(client, cid, sid, casting_level=slot, main_rolls=[2] * dardi)
    assert (len(esito["main_rolls"]), esito["total"]) == (dardi, dardi * 3)  # ogni dardo 2 + 1


@pytest.mark.caccia(id="CB-3270", fonte="2014 · Incantesimi · TS per metà danni o niente (Fame di Hadar, trucchetti; Fulmine, Frantumare, Dito della Morte, Ferire, Esplosione Solare, Evoca Raffica, Evoca Pioggia di Armi) · pag. 228-237",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Fame di Hadar", "carta:2014/spells.md#Fulmine", "carta:2014/spells.md#Frantumare",
                           "carta:2014/spells.md#Dito della Morte", "carta:2014/spells.md#Ferire", "carta:2014/spells.md#Esplosione Solare",
                           "carta:2014/spells.md#Evoca Raffica", "carta:2014/spells.md#Evoca Pioggia di Armi",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("indice, dimezza", [
    ("hunger-of-hadar", False), ("sacred-flame", False), ("acid-splash", False), ("lightning-bolt", True), ("shatter", True),
    ("finger-of-death", True), ("harm", True), ("sunburst", True), ("conjure-barrage", True), ("conjure-volley", True),
])
async def test_tiro_salvezza_superato_dimezza_solo_dove_la_carta_lo_dice(client, indice, dimezza):
    cid = await _pg(client, "sorcerer", 17)
    sid = await _impara(client, cid, indice)
    assert (await _danni(client, cid, sid))["save_halves"] is dimezza


@pytest.mark.caccia(id="CB-3271", fonte="2014 · Incantesimi · Faro di Speranza (vantaggio ai TS contro la morte) · pag. 235",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Faro di Speranza", "POST /characters/{char_id}/death_saves/roll"])
async def test_faro_di_speranza_da_vantaggio_ai_ts_contro_la_morte(client, test_session_factory):
    eroe, cid, sid = await _serata(client, test_session_factory, "cleric", 5, "beacon-of-hope")
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 3, "targets": [eroe]})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{eroe}/hp", json={"op": "damage", "value": 20})).status_code == 200
    r = await client.post(f"/characters/{eroe}/death_saves/roll", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "advantage"


@pytest.mark.caccia(id="CB-3272", fonte="2014 · Incantesimi · Favore Divino (concentrazione), Fame di Hadar (nessuna scalata), Eroismo (+1 creatura per slot) · pag. 232-235",
                    zona="regola:2014/incantesimi-D-F", voce="edizioni",
                    copre=["carta:2014/spells.md#Favore Divino", "carta:2014/spells.md#Fame di Hadar", "carta:2014/spells.md#Eroismo",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_un_personaggio_2014_riceve_la_variante_2014(client):
    paladino = await _pg(client, "paladin", 5)
    favore = await _impara(client, paladino, "divine-favor")
    r = await client.post(f"/characters/{paladino}/spells/{favore}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == favore  # nel 2014 Favore Divino richiede concentrazione
    warlock = await _pg(client, "warlock", 5)
    fame = await _impara(client, warlock, "hunger-of-hadar")
    r = await client.post(f"/characters/{warlock}/spells/{fame}/use", json={"slot_level": 3})
    assert r.status_code == 200, r.text  # nessuna scelta del tipo dei dadi in più: il 2014 non scala
    assert [spell_effect("2014", "heroism")[0].max_targets("2014", s) for s in (1, 2, 5)] == [1, 2, 5]  # +1 creatura per slot oltre il 1°
