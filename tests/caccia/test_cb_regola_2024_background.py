"""Controlli della zona regola:2024/background."""
import json
from pathlib import Path

import pytest

from core.data.backgrounds_2024 import BACKGROUNDS_2024

_JSON = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "backgrounds-2024.json"
_ACCOLITO = {"key": "acolyte", "increases": {"wisdom": 2, "charisma": 1}}


async def _crea(client, background: dict, **extra) -> dict:
    r = await client.post("/characters", json={"name": "B", "rules_edition": "2024", "background_2024": background, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _scelta(pg: dict, gruppo: str) -> dict | None:
    return next((c for c in pg["pending_choices"] if c.get("group") == gruppo), None)


def _iniziato(pg: dict) -> dict:
    return next(a for a in pg["abilities"] if a["feature_key"] == "feat.2024_magic_initiate")


def _somma(pg: dict) -> dict[str, int]:
    totale: dict[str, int] = {}
    for i in pg["items"]:
        chiave = (i["item_metadata"] or {}).get("srd_index") or i["name"]
        totale[chiave] = totale.get(chiave, 0) + i["quantity"]
    return totale


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3561", fonte="2024 · Background · Accolito, Intrattenitore, Contadino: competenza nello strumento del background · pag. 178-180; Monaco · Competenze · pag. 101; Bardo · Tratti Base · pag. 59; Maestro di Battaglia · Studioso di Guerra · pag. 94",
                    zona="regola:2024/background", voce="interazione",
                    copre=["carta:2024/backgrounds.md#Accolito / Acolyte (pag. 178)",
                           "carta:2024/backgrounds.md#Intrattenitore / Entertainer (pag. 180)",
                           "carta:2024/backgrounds.md#Contadino / Farmer (pag. 180)",
                           "carta:2024/classes/monk.md#Competenze / Proficiencies (Monaco 1, pag. 101)",
                           "carta:2024/classes/bard.md#Tratti Base del Bardo / Core Bard Traits (Bardo 1, pag. 59)",
                           "carta:2024/classes/fighter.md#Studioso di Guerra / Student of War (Maestro di Battaglia 3, pag. 94)",
                           "POST /characters"])
@pytest.mark.parametrize("background, strumento, classe, gruppo, quanti", [
    ({"key": "acolyte", "increases": {"wisdom": 2, "charisma": 1}}, "calligraphers_supplies",
     {"class_name": "monk", "level": 1, "skill_choices": ["acrobatics", "athletics"]}, "monk_tool", 1),
    ({"key": "entertainer", "increases": {"dexterity": 2, "charisma": 1}, "tool": "lute"}, "lute",
     {"class_name": "bard", "level": 1, "skill_choices": ["arcana", "history", "nature"]}, "bard_instruments", 3),
    ({"key": "farmer", "increases": {"strength": 2, "wisdom": 1}}, "carpenters_tools",
     {"class_name": "fighter", "level": 3, "subclass": "Maestro di Battaglia", "skill_choices": ["acrobatics", "history"]},
     "student_of_war_tool", 1),
])
async def test_strumento_del_background_non_consuma_la_scelta_di_classe(client, background, strumento, classe, gruppo, quanti):
    pg = await _crea(client, background, initial_class=classe)
    assert pg["tool_proficiencies"].get(strumento), pg["tool_proficiencies"]  # precondizione: lo strumento del background c'è
    presi = (pg["classes"][0]["options"] or {}).get(gruppo, [])
    scelta = _scelta(pg, gruppo)
    # due fonti distinte: lo strumento del background non conta come scelta della classe, che resta tutta da fare
    assert scelta is not None and scelta["count"] == quanti, \
        f"scelta {gruppo}: {scelta and scelta['count']} su {quanti}; già segnati come scelti dalla classe: {presi}"


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3562", fonte="2024 · Background · Equipaggiamento A di ciascuno dei sedici background · pag. 178-185",
                    zona="regola:2024/background", voce="regola",
                    copre=["carta:2024/backgrounds.md#Accolito / Acolyte (pag. 178)",
                           "carta:2024/backgrounds.md#Artigiano / Artisan (pag. 178)",
                           "carta:2024/backgrounds.md#Ciarlatano / Charlatan (pag. 179)",
                           "carta:2024/backgrounds.md#Criminale / Criminal (pag. 179)",
                           "carta:2024/backgrounds.md#Intrattenitore / Entertainer (pag. 180)",
                           "carta:2024/backgrounds.md#Contadino / Farmer (pag. 180)",
                           "carta:2024/backgrounds.md#Guardia / Guard (pag. 181)",
                           "carta:2024/backgrounds.md#Guida / Guide (pag. 181)",
                           "carta:2024/backgrounds.md#Eremita / Hermit (pag. 182)",
                           "carta:2024/backgrounds.md#Mercante / Merchant (pag. 182)",
                           "carta:2024/backgrounds.md#Nobile / Noble (pag. 183)",
                           "carta:2024/backgrounds.md#Sapiente / Sage (pag. 183)",
                           "carta:2024/backgrounds.md#Marinaio / Sailor (pag. 184)",
                           "carta:2024/backgrounds.md#Scriba / Scribe (pag. 184)",
                           "carta:2024/backgrounds.md#Soldato / Soldier (pag. 185)",
                           "carta:2024/backgrounds.md#Viandante / Wayfarer (pag. 185)",
                           "POST /characters"])
@pytest.mark.parametrize("chiave, strumento, atteso", [
    ("acolyte", None, {"Scorte da calligrafo": 1, "Libro (preghiere)": 1, "Simbolo sacro": 1, "Pergamena (foglio)": 10, "Veste": 1}),
    ("artisan", "alchemists_supplies", {"Scorte da alchimista": 1, "Borsa": 2, "Abiti da viaggiatore": 1}),
    ("charlatan", None, {"Arnesi da falsario": 1, "Costume": 1, "Abiti raffinati": 1}),
    ("criminal", None, {"dagger": 2, "Arnesi da scasso": 1, "Piede di porco": 1, "Borsa": 2, "Abiti da viaggiatore": 1}),
    ("entertainer", "bagpipes", {"Cornamusa": 1, "Costume": 2, "Specchio": 1, "Profumo": 1, "Abiti da viaggiatore": 1}),
    ("farmer", None, {"sickle": 1, "Strumenti da falegname": 1, "Kit da guaritore": 1, "Pentola di ferro": 1, "Pala": 1,
                      "Abiti da viaggiatore": 1}),
    ("guard", "dice_set", {"spear": 1, "crossbow-light": 1, "Quadrelli": 20, "Dadi": 1, "Lanterna schermabile": 1, "Manette": 1,
                           "Faretra": 1, "Abiti da viaggiatore": 1}),
    ("guide", None, {"shortbow": 1, "Frecce": 20, "Strumenti da cartografo": 1, "Sacco a pelo": 1, "Faretra": 1, "Tenda": 1,
                     "Abiti da viaggiatore": 1}),
    ("hermit", None, {"quarterstaff": 1, "Borsa da erborista": 1, "Sacco a pelo": 1, "Libro (filosofia)": 1, "Lampada": 1,
                      "Olio (fiasca)": 3, "Abiti da viaggiatore": 1}),
    ("merchant", None, {"Strumenti da navigatore": 1, "Borsa": 2, "Abiti da viaggiatore": 1}),
    ("noble", "playing_card_set", {"Mazzo di carte": 1, "Abiti raffinati": 1, "Profumo": 1}),
    ("sage", None, {"quarterstaff": 1, "Scorte da calligrafo": 1, "Libro (storia)": 1, "Pergamena (foglio)": 8, "Veste": 1}),
    ("sailor", None, {"dagger": 1, "Strumenti da navigatore": 1, "Corda": 1, "Abiti da viaggiatore": 1}),
    ("scribe", None, {"Scorte da calligrafo": 1, "Abiti raffinati": 1, "Lampada": 1, "Olio (fiasca)": 3, "Pergamena (foglio)": 12}),
    ("soldier", "dragonchess_set", {"spear": 1, "shortbow": 1, "Frecce": 20, "Scacchi dei draghi": 1, "Kit da guaritore": 1,
                                    "Faretra": 1, "Abiti da viaggiatore": 1}),
    ("wayfarer", None, {"dagger": 2, "Arnesi da scasso": 1, "Set da gioco a scelta": 1, "Sacco a pelo": 1, "Borsa": 2,
                        "Abiti da viaggiatore": 1}),
])
async def test_pacchetto_a_del_background_come_nella_carta(client, chiave, strumento, atteso):
    caratteristiche = BACKGROUNDS_2024[chiave].abilities
    corpo = {"key": chiave, "increases": {c: 1 for c in caratteristiche}, "equipment": "pack",
             **({"tool": strumento} if strumento else {})}
    pg = await _crea(client, corpo)
    assert _somma(pg) == atteso


@pytest.mark.caccia(id="CB-3563", fonte="2024 · Background · pag. 177-185: la creazione guidata mostra e invia caratteristiche, talento, abilità, strumento e pacchetto del catalogo del server",
                    zona="regola:2024/background", voce="contratto",
                    copre=["carta:2024/backgrounds.md#Accolito / Acolyte (pag. 178)",
                           "carta:2024/backgrounds.md#Artigiano / Artisan (pag. 178)",
                           "carta:2024/backgrounds.md#Viandante / Wayfarer (pag. 185)"])
def test_catalogo_del_frontend_uguale_a_quello_del_server():
    dati = json.loads(_JSON.read_text(encoding="utf-8"))
    assert dati["gold_option"] == 50
    voci = {v["key"]: v for v in dati["items"]}
    assert set(voci) == set(BACKGROUNDS_2024)
    for chiave, bg in BACKGROUNDS_2024.items():
        v = voci[chiave]
        strumento = list(bg.tool) if isinstance(bg.tool, tuple) else bg.tool
        assert (v["abilities"], v["origin_feat"], v["skills"], v["tool"], v["equipment"], v["feat_list"]) == \
            (list(bg.abilities), bg.origin_feat, list(bg.skills), strumento, bg.equipment, bg.feat_list), chiave


@pytest.mark.caccia(id="CB-3564", fonte="2024 · Background · Accolito (Iniziato alla magia, Chierico) pag. 178, Guida (Druido) pag. 181, Sapiente (Mago) pag. 183",
                    zona="regola:2024/background", voce="regola",
                    copre=["carta:2024/backgrounds.md#Accolito / Acolyte (pag. 178)",
                           "carta:2024/backgrounds.md#Guida / Guide (pag. 181)",
                           "carta:2024/backgrounds.md#Sapiente / Sage (pag. 183)",
                           "carta:2024/feats.md#Iniziato alla magia / Magic Initiate (pag. 201) - Origine, ripetibile",
                           "POST /characters", "PUT /characters/{char_id}/feats/{ability_id}/options"])
@pytest.mark.parametrize("chiave, aumenti, lista, propri, altra, estranei", [
    ("acolyte", {"wisdom": 2, "charisma": 1}, "cleric",
     [("Fiamma Sacra", 0, "sacred-flame"), ("Taumaturgia", 0, "thaumaturgy"), ("Benedizione", 1, "bless")],
     "wizard", [("Dardo di fuoco", 0, "fire-bolt"), ("Mano Magica", 0, "mage-hand"), ("Dardo Incantato", 1, "magic-missile")]),
    ("guide", {"wisdom": 2, "dexterity": 1}, "druid",
     [("Druidismo", 0, "druidcraft"), ("Produrre Fiamma", 0, "produce-flame"), ("Intralciare", 1, "entangle")],
     "cleric", [("Fiamma Sacra", 0, "sacred-flame"), ("Taumaturgia", 0, "thaumaturgy"), ("Benedizione", 1, "bless")]),
    ("sage", {"intelligence": 2, "wisdom": 1}, "wizard",
     [("Dardo di fuoco", 0, "fire-bolt"), ("Mano Magica", 0, "mage-hand"), ("Dardo Incantato", 1, "magic-missile")],
     "druid", [("Druidismo", 0, "druidcraft"), ("Produrre Fiamma", 0, "produce-flame"), ("Intralciare", 1, "entangle")]),
])
async def test_iniziato_alla_magia_del_background_con_la_sua_lista(client, chiave, aumenti, lista, propri, altra, estranei):
    def incantesimi(righe):
        return [{"name": n, "level": lv, "srd_index": i, "casting_time": "1 azione"} for n, lv, i in righe]
    pg = await _crea(client, {"key": chiave, "increases": aumenti})
    riga = _iniziato(pg)
    assert riga["options"].get("list") == lista and riga["feat_status"] == "incomplete"
    url = f"/characters/{pg['id']}/feats/{riga['id']}/options"
    r = await client.put(url, json={"options": {"list": altra, "ability": "wisdom"}, "spells": incantesimi(estranei)})
    assert r.status_code == 422, r.status_code
    r = await client.put(url, json={"options": {"list": lista, "ability": "wisdom"}, "spells": incantesimi(propri)})
    assert r.status_code == 200, r.text
    riga = _iniziato(r.json())
    assert riga["feat_status"] == "active" and riga["options"]["list"] == lista


@pytest.mark.caccia(id="CB-3565", fonte="2024 · Background · aumenti: +2 a una e +1 a un'altra delle tre, oppure +1 a tutte e tre, nessuna sopra 20 · pag. 177",
                    zona="regola:2024/background", voce="limiti",
                    copre=["carta:2024/backgrounds.md#Guardia / Guard (pag. 181)", "POST /characters"])
@pytest.mark.parametrize("punteggi, aumenti, stato", [
    ({"wisdom": 19}, {"strength": 1, "intelligence": 1, "wisdom": 1}, 201),
    ({"wisdom": 20}, {"strength": 1, "intelligence": 1, "wisdom": 1}, 422),
    ({}, {"strength": 2}, 422),
    ({}, {"strength": 1, "wisdom": 1}, 422),
    ({}, {"strength": 2, "intelligence": 2}, 422),
    ({}, {"strength": 2, "intelligence": 1, "wisdom": 1}, 422),
])
async def test_aumenti_del_background_soglie(client, punteggi, aumenti, stato):
    r = await client.post("/characters", json={"name": "G", "rules_edition": "2024", "ability_scores": punteggi,
                                               "background_2024": {"key": "guard", "increases": aumenti, "tool": "dice_set"}})
    assert r.status_code == stato, r.text[:120]
    if stato == 201:
        assert {s["name"]: s["value"] for s in r.json()["ability_scores"]}["wisdom"] == 20


@pytest.mark.caccia(id="CB-3566", fonte="2024 · Background · Accolito: Iniziato alla magia (Chierico), Intuizione e Religione, Forniture da calligrafo · pag. 178",
                    zona="regola:2024/background", voce="persistenza",
                    copre=["carta:2024/backgrounds.md#Accolito / Acolyte (pag. 178)",
                           "GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/duplicate"])
async def test_export_e_duplica_tengono_cio_che_da_il_background(client):
    pg = await _crea(client, _ACCOLITO, ability_scores={"wisdom": 14, "charisma": 12})
    export = (await client.get(f"/characters/{pg['id']}/export")).json()
    importato = (await client.post("/characters/import", json=export)).json()
    copia = (await client.post(f"/characters/{pg['id']}/duplicate")).json()
    for scheda in (importato, copia):
        punteggi = {s["name"]: s["value"] for s in scheda["ability_scores"]}
        assert (punteggi["wisdom"], punteggi["charisma"]) == (16, 13)
        assert {k for k, v in scheda["skills"].items() if v} == {"insight", "religion"}
        assert scheda["tool_proficiencies"] == {"calligraphers_supplies": True}
        assert _iniziato(scheda)["options"] == {"list": "cleric"}
