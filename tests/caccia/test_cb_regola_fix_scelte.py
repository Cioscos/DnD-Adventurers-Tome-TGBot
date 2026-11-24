"""Controlli scritti dai correttori del gruppo scelte per i dubbi risolti come difetti (Q-…)."""
import pytest

SCORES = {"strength": 14, "dexterity": 14, "constitution": 12, "intelligence": 12, "wisdom": 14, "charisma": 14}
# tutte le abilità dell'elenco del ranger in multiclasse (pag. 164): l'elenco è esaurito
RANGER = ("animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival")


@pytest.mark.caccia(id="CB-4111", fonte="2014 · Personalità e Background · Regole generali dei background: la stessa competenza da due fonti, se ne sceglie un'altra dello stesso tipo · pag. 125",
                    zona="regola:2014/background", voce="limiti",
                    copre=["carta:2014/backgrounds.md#Regole generali dei background (pag. 125)",
                           "POST /characters/{char_id}/classes"])
async def test_elenco_della_seconda_classe_esaurito_si_sceglie_un_altra_abilita(client):
    r = await client.post("/characters", json={
        "name": "Esploratore", "rules_edition": "2014", "ability_scores": SCORES, "skills": {k: True for k in RANGER},
        "initial_class": {"class_name": "fighter", "level": 1, "skill_choices": ["acrobatics", "history"]}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    # un'abilità già posseduta resta rifiutata
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "ranger", "level": 1, "skill_choices": ["stealth"]})
    assert r.status_code == 422, f"doppione accettato ({r.status_code})"
    # con l'elenco del ranger tutto già posseduto, l'abilità si sceglie fuori dall'elenco e non va persa
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "ranger", "level": 1, "skill_choices": ["arcana"]})
    assert r.status_code == 201, r.json().get("detail")
    assert r.json()["skills"].get("arcana")
