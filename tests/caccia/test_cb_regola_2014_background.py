"""Controlli della zona regola:2014/background."""
import json
from pathlib import Path

import pytest

from core.data.skills import SKILL_ABILITY_MAP

_BACKGROUNDS = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "backgrounds.json"
# Abilità dell'Accolito (pag. 127), scritte alla creazione come fa la webapp dopo la scelta dal catalogo
ACCOLITO = {"insight": True, "religion": True}
SCORES = {"strength": 14, "dexterity": 14, "constitution": 12, "intelligence": 12, "wisdom": 14, "charisma": 14}


async def _pg_accolito(client, classe: str = "fighter", scelte: list[str] | None = None, livello: int = 1,
                       sottoclasse: str | None = None) -> dict:
    corpo = {"name": "Accolito", "rules_edition": "2014", "ability_scores": SCORES, "skills": ACCOLITO,
             "initial_class": {"class_name": classe, "level": livello, "subclass": sottoclasse,
                               "skill_choices": scelte if scelte is not None else ["acrobatics", "athletics"]}}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def _competenti(pg: dict) -> set[str]:
    return {k for k, v in (pg["skills"] or {}).items() if v}


def _scelta(pg: dict, gruppo: str) -> dict | None:
    return next((c for c in pg["pending_choices"] if c.get("group") == gruppo), None)


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3111", fonte="2014 · Personalità e Background · Competenze: la stessa competenza da due fonti, se ne sceglie un'altra dello stesso tipo · pag. 125; decisione D-012",
                    zona="regola:2014/background", voce="interazione",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "carta:2014/backgrounds.md#Accolito / Acolyte (pag. 127)",
                           "POST /characters/{char_id}/classes"])
@pytest.mark.parametrize("classe, doppia", [
    ("ranger", "insight"),
    ("rogue", "insight"),
    ("bard", "religion"),
])
async def test_abilita_della_seconda_classe_gia_data_dal_background(client, classe, doppia):
    pg = await _pg_accolito(client)
    prima = _competenti(pg)
    r = await client.post(f"/characters/{pg['id']}/classes",
                          json={"class_name": classe, "level": 1, "skill_choices": [doppia]})
    dopo = _competenti((await client.get(f"/characters/{pg['id']}")).json())
    # la competenza doppia non deve andare persa in silenzio: rifiutata come alla creazione (class_skill_taken)
    assert r.status_code == 422, f"accettata ({r.status_code}): competenze {sorted(prima)} -> {sorted(dopo)}"


@pytest.mark.caccia(id="CB-3112", fonte="2014 · Personalità e Background · Competenze: la stessa competenza da due fonti, se ne sceglie un'altra dello stesso tipo · pag. 125; decisione D-012",
                    zona="regola:2014/background", voce="interazione",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "POST /characters/{char_id}/feats", "PUT /characters/{char_id}/feats/{ability_id}/options"])
async def test_talento_abile_su_abilita_gia_data_dal_background(client):
    pg = await _pg_accolito(client, livello=4)
    r = await client.post(f"/characters/{pg['id']}/feats", json={"feat_key": "skilled", "ability": None})
    assert r.status_code == 201, r.text
    riga = next(a for a in r.json()["abilities"] if a["feature_key"] == "feat.skilled" and a["feat_status"] == "incomplete")
    prima = _competenti(r.json())
    r = await client.put(f"/characters/{pg['id']}/feats/{riga['id']}/options",
                         json={"options": {"picks": ["religion", "arcana", "history"]}, "spells": []})
    guadagnate = _competenti(r.json()) - prima if r.status_code == 200 else set()
    # Religione viene già dall'Accolito: la scelta sprecata va rifiutata, non tre competenze ridotte a due
    assert r.status_code == 422, f"accettata: competenze nuove {sorted(guadagnate)} su tre scelte"


@pytest.mark.caccia(id="CB-3113", fonte="2014 · Personalità e Background · competenza da due fonti · pag. 125; Forestiero: Atletica e Sopravvivenza · pag. 133; Chierico · Accolito della Natura · pag. 62",
                    zona="regola:2014/background", voce="interazione",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "carta:2014/backgrounds.md#Forestiero / Outlander (pag. 133)",
                           "POST /characters/{char_id}/choices/{choice_id}/resolve"])
async def test_accolito_della_natura_su_abilita_gia_data_dal_background(client):
    r = await client.post("/characters", json={
        "name": "Forestiero", "rules_edition": "2014", "ability_scores": SCORES,
        "skills": {"athletics": True, "survival": True},
        "initial_class": {"class_name": "cleric", "level": 1, "subclass": "nature", "skill_choices": ["history", "medicine"]}})
    assert r.status_code == 201, r.text
    pg = r.json()
    scelta = _scelta(pg, "nature_skill")
    assert scelta is not None, [c.get("group") for c in pg["pending_choices"]]
    r = await client.post(f"/characters/{pg['id']}/choices/{scelta['id']}/resolve",
                          json={"kind": "class_option", "options": ["survival"]})
    offerte = sorted(o["key"] for o in scelta["options"])
    # come le Competenze Bonus della Sapienza (CB-3116): l'abilità già data dal background non si spreca
    assert r.status_code == 422, f"accettata ({r.status_code}); opzioni offerte {offerte}"


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3114", fonte="2014 · Personalità e Background · ogni background dà competenza in 2 abilità · pag. 125; Accolito: Intuizione e Religione · pag. 127",
                    zona="regola:2014/background", voce="regola",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "carta:2014/backgrounds.md#Accolito / Acolyte (pag. 127)"])
def test_catalogo_background_2014_due_abilita_e_accolito():
    voci = json.loads(_BACKGROUNDS.read_text(encoding="utf-8"))["items"]
    for v in voci:
        abilita = [s.replace("-", "_") for s in v["skill_proficiencies"]]
        assert len(abilita) == 2 and set(abilita) <= set(SKILL_ABILITY_MAP), (v["index"], abilita)
    accolito = next(v for v in voci if v["index"] == "acolyte")
    assert sorted(accolito["skill_proficiencies"]) == ["insight", "religion"]


@pytest.mark.caccia(id="CB-3115", fonte="2014 · Personalità e Background · Competenze · pag. 125; Multiclasse, Competenze (Ranger: un'abilità della sua lista) · pag. 164",
                    zona="regola:2014/background", voce="interazione",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "POST /characters/{char_id}/classes"])
async def test_seconda_classe_con_abilita_nuova_somma_a_quelle_del_background(client):
    pg = await _pg_accolito(client)
    r = await client.post(f"/characters/{pg['id']}/classes",
                          json={"class_name": "ranger", "level": 1, "skill_choices": ["survival"]})
    assert r.status_code == 201, r.text
    assert _competenti(r.json()) == {"insight", "religion", "acrobatics", "athletics", "survival"}


@pytest.mark.caccia(id="CB-3116", fonte="2014 · Personalità e Background · competenza da due fonti · pag. 125; Bardo · Collegio della Sapienza, Competenze Bonus · pag. 54",
                    zona="regola:2014/background", voce="interazione",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "POST /characters/{char_id}/choices/{choice_id}/resolve"])
async def test_competenze_bonus_della_sapienza_escludono_quelle_del_background(client):
    pg = await _pg_accolito(client, "bard", ["acrobatics", "arcana", "history"], livello=3, sottoclasse="lore")
    scelta = _scelta(pg, "lore_skills")
    assert scelta is not None and scelta["count"] == 3
    assert not {"insight", "religion"} & {o["key"] for o in scelta["options"]}
    r = await client.post(f"/characters/{pg['id']}/choices/{scelta['id']}/resolve",
                          json={"kind": "class_option", "options": ["religion", "nature", "medicine"]})
    assert r.status_code == 422, r.status_code


@pytest.mark.caccia(id="CB-3117", fonte="2014 · Personalità e Background · pag. 125-141: il background 2014 dà abilità, strumenti e linguaggi, nessun aumento di caratteristica né talento (2024 · Background · pag. 177)",
                    zona="regola:2014/background", voce="edizioni",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "carta:2014/backgrounds.md#Accolito / Acolyte (pag. 127)", "POST /characters"])
async def test_background_2014_non_da_aumenti_ne_talento(client):
    r = await client.post("/characters", json={"name": "Accolito", "rules_edition": "2014", "ability_scores": SCORES,
                                                "skills": ACCOLITO, "identity": {"background": "Accolito"}})
    assert r.status_code == 201, r.text
    pg = r.json()
    assert {s["name"]: s["value"] for s in pg["ability_scores"]} == SCORES
    assert not [a for a in pg["abilities"] if (a["feature_key"] or "").startswith("feat.")]
    assert _competenti(pg) == {"insight", "religion"} and pg["background"] == "Accolito"
