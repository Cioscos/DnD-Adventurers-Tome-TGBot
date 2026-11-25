"""Controlli della zona regola:2014/razze.

Le razze 2014 vivono nel catalogo del frontend (webapp/src/data/srd/races.json): il wizard di creazione costruisce il
corpo di POST /characters con ``buildSpecies`` (webapp/src/lib/species.ts). ``_specie`` qui sotto rifà lo stesso corpo
leggendo lo stesso file, così i controlli partono da ciò che il giocatore manda davvero.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.rules.weapons import small_race

_RAZZE = json.loads((Path(__file__).resolve().parents[2] / "webapp/src/data/srd/races.json").read_text(encoding="utf-8"))["items"]
_NOTE = {"poison_save": "save.constitution", "charm_save": "save.wisdom", "frightened_save": "save.wisdom"}  # species.ts NOTE_KEY
_LINGUE = {"common": "Comune", "dwarvish": "Nanico", "elvish": "Elfico", "gnomish": "Gnomesco", "halfling": "Halfling",
           "orc": "Orchesco", "draconic": "Draconico", "infernal": "Infernale"}


def _specie(indice: str, sotto: str | None = None, lingua: str = "it") -> dict:
    """Il campo ``species`` che il wizard 2014 manda per la razza ``indice`` (e la sottorazza ``sotto``)."""
    razza = next(r for r in _RAZZE if r["index"] == indice)
    sub = next(s for s in razza["subraces"] if s["index"] == sotto) if sotto else {}
    bonus = dict(razza["ability_bonuses"])
    for k, v in (sub.get("ability_bonuses") or {}).items():
        bonus[k] = bonus.get(k, 0) + v
    sensi: dict[str, int] = {}
    for s in [*razza["senses"], *(sub.get("senses") or [])]:
        sensi[s["type"]] = max(sensi.get(s["type"], 0), s["range_ft"])
    note: dict[str, str] = {}
    for nid, testo in {**razza["roll_notes"], **(sub.get("roll_notes") or {})}.items():
        if nid in _NOTE:
            note[_NOTE[nid]] = " ".join(x for x in (note.get(_NOTE[nid]), testo[lingua]) if x)[:120]
    return {
        "name": (sub or razza)["name"][lingua],
        "speed_ft": sub.get("speed_ft", razza["speed_ft"]),
        "senses": [{"type": t, "range_ft": r} for t, r in sensi.items()],
        "languages": [_LINGUE.get(x, x) for x in dict.fromkeys([*razza["languages"], *(sub.get("languages") or [])])],
        "ability_bonuses": bonus,
        "roll_notes": note,
        "traits": [{"name": t["name"][lingua], "description": t["desc"][lingua]} for t in [*razza["traits"], *(sub.get("traits") or [])]],
    }


async def _crea(client, edizione="2014", **corpo) -> dict:
    r = await client.post("/characters", json={"name": "R", "rules_edition": edizione, **corpo})
    assert r.status_code == 201, r.text
    return r.json()


async def _indossa_piastre(client, cid: int) -> None:
    """Armatura completa (For 15) indossata: con Forza 10 toglie 3 m a chi non ne è esentato."""
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Armatura completa", "item_type": "armor", "is_equipped": True, "weight": 1,
        "item_metadata": {"armor_type": "heavy", "ac_value": 18, "strength_req": 15}})
    assert r.status_code == 201, r.text


async def _scheda(client, cid: int) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3061", fonte="2014 · Razze · Nano, tratti base: Velocità 7,5 m non ridotta dall'armatura pesante · pag. 28; Equipaggiamento · Armature, colonna Forza · pag. 145",
                    zona="regola:2014/razze", voce="regola",
                    copre=["carta:2014/races.md#Nano / Dwarf - tratti base (pag. 28)",
                           "carta:2014/races.md#Nano delle Colline / Hill Dwarf (pag. 28)",
                           "carta:2014/equipment.md#Armature / Armor (pag. 145)",
                           "POST /characters", "POST /characters/{char_id}/items", "GET /characters/{char_id}"])
@pytest.mark.parametrize("indice,sotto,lingua", [("dwarf", None, "it"), ("dwarf", "hill-dwarf", "en")])
async def test_nano_2014_in_armatura_pesante_senza_forza_non_perde_velocita(client, indice, sotto, lingua):
    pg = await _crea(client, species=_specie(indice, sotto, lingua),
                     initial_class={"class_name": "fighter", "level": 1})  # Forza 10, addestrato alle armature pesanti
    senza = (await _scheda(client, pg["id"]))["computed"]["speed"]
    assert senza == 25
    await _indossa_piastre(client, pg["id"])
    # il nano ignora la colonna Forza: resta a 7,5 m
    assert (await _scheda(client, pg["id"]))["computed"]["speed"] == 25


@pytest.mark.caccia(id="CB-3062", fonte="2014 · Razze · Nano delle Colline, Robustezza Nanica: PF massimi +1 e +1 a ogni livello · pag. 28",
                    zona="regola:2014/razze", voce="limiti",
                    copre=["carta:2014/races.md#Nano delle Colline / Hill Dwarf (pag. 28)", "POST /characters", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello", [1, 20])
async def test_nano_delle_colline_2014_ha_un_pf_massimo_in_piu_per_livello(client, livello):
    pg = await _crea(client, species=_specie("dwarf", "hill-dwarf"), ability_scores={"constitution": 8},  # +2 di razza: Cos 10
                     initial_class={"class_name": "fighter", "level": livello, "hit_die": 10})
    senza_tratto = 10 + 6 * (livello - 1)  # d10, Cos 10: 10 al 1°, 6 ai successivi
    scheda = await _scheda(client, pg["id"])
    assert scheda["computed"]["hp_max_effective"] == senza_tratto + livello
    assert scheda["current_hit_points"] == senza_tratto + livello  # nasce a PF pieni


@pytest.mark.caccia(id="CB-3072", fonte="2014 · Razze · Nano delle Colline, Robustezza Nanica: +1 PF ogni volta che sale di livello, anche in un'altra classe · pag. 28",
                    zona="regola:2014/razze", voce="interazione",
                    copre=["carta:2014/races.md#Nano delle Colline / Hill Dwarf (pag. 28)", "POST /characters",
                           "POST /characters/{char_id}/classes", "GET /characters/{char_id}"])
async def test_nano_delle_colline_2014_multiclasse_un_pf_in_piu_per_ogni_livello_preso_dopo(client):
    massimi = []
    for specie, cos in ((_specie("human"), 9), (_specie("dwarf", "hill-dwarf"), 8)):  # Cos 10 per entrambi dopo la razza
        pg = await _crea(client, species=specie, ability_scores={"constitution": cos},
                         initial_class={"class_name": "fighter", "level": 1, "hit_die": 10})
        r = await client.post(f"/characters/{pg['id']}/classes", json={"class_name": "wizard", "level": 2})
        assert r.status_code == 201, r.text
        massimi.append((await _scheda(client, pg["id"]))["computed"]["hp_max_effective"])
    umano, nano = massimi
    assert nano - umano == 3  # guerriero 1 e mago 2: tre livelli, tre punti ferita in più


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3063", fonte="2014 · Razze · Nano, tratti base · pag. 28 contro 2024 · Specie · Nano · pag. 188 e Armature · pag. 219: nel 2024 il nano non ignora la Forza dell'armatura",
                    zona="regola:2014/razze", voce="edizioni",
                    copre=["carta:2014/races.md#Nano / Dwarf - tratti base (pag. 28)", "carta:2024/races.md#Nano / Dwarf (pag. 188)",
                           "carta:2024/equipment.md#Regole delle armature (pag. 219)",
                           "POST /characters", "POST /characters/{char_id}/items", "GET /characters/{char_id}"])
async def test_nano_2024_in_armatura_pesante_senza_forza_perde_3_metri(client):
    pg = await _crea(client, "2024", species_2024={"key": "2024_dwarf", "options": {}},
                     initial_class={"class_name": "fighter", "level": 1})
    assert (await _scheda(client, pg["id"]))["computed"]["speed"] == 30
    await _indossa_piastre(client, pg["id"])
    assert (await _scheda(client, pg["id"]))["computed"]["speed"] == 20


@pytest.mark.caccia(id="CB-3064", fonte="2014 · Razze · Tratti Razziali: taglia Piccola e armi pesanti · pag. 17; Halfling e Gnomo Piccoli (pag. 25, 36), le altre Medie",
                    zona="regola:2014/razze", voce="regola",
                    copre=["carta:2014/races.md#Tratti Razziali / Racial Traits (pag. 17)",
                           "carta:2014/races.md#Halfling / Halfling - tratti base (pag. 25)",
                           "carta:2014/races.md#Gnomo / Gnome - tratti base (pag. 36-37)"])
def test_la_taglia_di_ogni_razza_e_sottorazza_del_catalogo_e_quella_del_manuale():
    piccole = {"halfling", "gnome"}
    letti = {}
    for razza in _RAZZE:
        for voce in [razza, *razza["subraces"]]:
            for nome in voce["name"].values():
                letti[nome] = small_race(SimpleNamespace(race=nome))
                assert letti[nome] is (razza["index"] in piccole), nome
    assert len(letti) == 24  # 9 razze e 4 sottorazze, in italiano e in inglese (Halfling e Tiefling uguali)


@pytest.mark.caccia(id="CB-3065", fonte="2014 · Razze · pag. 17-43: aumenti, velocità, scurovisione e tratti della razza scelta nel catalogo",
                    zona="regola:2014/razze", voce="normale",
                    copre=["carta:2014/races.md#Elfo / Elf (pag. 18-22)", "carta:2014/races.md#Halfling / Halfling (pag. 23-25)",
                           "carta:2014/races.md#Nano / Dwarf (pag. 26-28)", "carta:2014/races.md#Umano / Human (pag. 29-32)",
                           "carta:2014/races.md#Dragonide / Dragonborn (pag. 32-34)", "carta:2014/races.md#Gnomo / Gnome (pag. 35-37)",
                           "carta:2014/races.md#Mezzelfo / Half-Elf (pag. 38-39)", "carta:2014/races.md#Mezzorco / Half-Orc (pag. 40-41)",
                           "carta:2014/races.md#Tiefling / Tiefling (pag. 42-43)", "POST /characters"])
@pytest.mark.parametrize("indice,sotto", [(r["index"], s) for r in _RAZZE for s in [None, *(x["index"] for x in r["subraces"])]])
async def test_ogni_razza_del_catalogo_crea_il_personaggio_con_i_suoi_valori(client, indice, sotto):
    specie = _specie(indice, sotto)
    pg = await _crea(client, species=specie, ability_scores={a: 10 for a in ("strength", "dexterity", "constitution",
                                                                                "intelligence", "wisdom", "charisma")})
    punteggi = {s["name"][:3]: s["value"] - 10 for s in pg["ability_scores"] if s["value"] != 10}
    buio = next((s["range_ft"] for s in (pg["settings"] or {}).get("senses") or [] if s["type"] == "darkvision"), None)
    assert (pg["race"], pg["speed"], punteggi, buio) == (specie["name"], specie["speed_ft"], specie["ability_bonuses"],
                                                         next((s["range_ft"] for s in specie["senses"]), None))
    assert {a["name"] for a in pg["abilities"] if a["is_passive"]} == {t["name"] for t in specie["traits"]}


@pytest.mark.caccia(id="CB-3066", fonte="2014 · Razze · Gnomo delle Rocce (pag. 37): la razza scelta resta uguale dopo esportazione, importazione e duplicazione",
                    zona="regola:2014/razze", voce="persistenza",
                    copre=["carta:2014/races.md#Gnomo delle Rocce / Rock Gnome (pag. 37)", "POST /characters",
                           "GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/duplicate"])
async def test_la_razza_2014_sopravvive_a_export_import_e_duplica(client):
    pg = await _crea(client, species=_specie("gnome", "rock-gnome"), ability_scores={"intelligence": 13, "constitution": 12})

    def razza(c: dict) -> tuple:
        return (c["race"], c["speed"], (c["settings"] or {}).get("senses"), (c["settings"] or {}).get("roll_notes"),
                sorted((a["name"], a["value"]) for a in c["ability_scores"]), sorted(c["languages"] or []),
                sorted(a["name"] for a in c["abilities"]))
    dati = (await client.get(f"/characters/{pg['id']}/export")).json()
    nuovo = (await client.post("/characters/import", json=dati)).json()
    dup = (await client.post(f"/characters/{pg['id']}/duplicate")).json()
    assert razza(nuovo) == razza(pg) == razza(dup)
    assert razza(pg)[:3] == ("Gnomo delle rocce", 25, [{"type": "darkvision", "range_ft": 60}])
