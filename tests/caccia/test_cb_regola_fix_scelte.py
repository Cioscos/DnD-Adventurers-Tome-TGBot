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


@pytest.mark.caccia(id="CB-4114", fonte="2014 · Talenti · Incantatore da Guerra: capacità di lanciare almeno un incantesimo, da qualsiasi fonte · pag. 168; Razze · Elfo Alto pag. 21, Tiefling pag. 43",
                    zona="regola:2014/talenti", voce="interazione",
                    copre=["carta:2014/feats.md#Incantatore da Guerra / War Caster (pag. 168)",
                           "carta:2014/races.md#Elfo Alto / High Elf (pag. 21)", "carta:2014/races.md#Tiefling / Tiefling (pag. 43)",
                           "POST /characters/{char_id}/feats"])
@pytest.mark.parametrize(("razza", "atteso"), [("Tiefling", 201), ("Elfo alto", 201), ("Umano", 422)])
async def test_chi_conosce_un_trucchetto_di_razza_sa_lanciare_incantesimi(client, razza, atteso):
    r = await client.post("/characters", json={
        "name": "Guerriero", "rules_edition": "2014", "identity": {"race": razza}, "ability_scores": SCORES,
        "initial_class": {"class_name": "fighter", "level": 4}})
    assert r.status_code == 201 and r.json()["race"] == razza, r.text
    # Eredità Infernale (taumaturgia) e il trucchetto dell'Elfo Alto: il guerriero sa lanciare almeno un incantesimo
    r = await client.post(f"/characters/{r.json()['id']}/feats", json={"feat_key": "war_caster", "ability": None})
    assert r.status_code == atteso, r.text


@pytest.mark.caccia(id="CB-4115", fonte="2024 · Guerriero · Dono Epico: un Dono o un altro talento per cui si è qualificati · pag. 92; Talenti · Aumento di caratteristica (Generale) · pag. 202",
                    zona="regola:2024/talenti", voce="regola",
                    copre=["carta:2024/classes/fighter.md#Dono Epico / Epic Boon (Guerriero 19, pag. 92)",
                           "carta:2024/feats.md#Aumento di caratteristica / Ability Score Improvement (pag. 202) - Generale (livello 4+)",
                           "POST /characters/{char_id}/choices/{choice_id}/resolve"])
async def test_il_dono_epico_del_19_ammette_l_aumento_di_caratteristica(client):
    r = await client.post("/characters", json={"name": "Campione", "rules_edition": "2024", "ability_scores": SCORES,
                                               "initial_class": {"class_name": "fighter", "level": 1}})
    assert r.status_code == 201, r.text
    r = await client.patch(f"/characters/{r.json()['id']}/xp", json={"set": 305000})
    assert r.status_code == 200, r.text
    scelta = next(c for c in r.json()["pending_choices"] if c["kind"] == "epic_boon")
    # nel 2024 l'Aumento di caratteristica è un talento Generale: al 19° se ne hanno i requisiti
    r = await client.post(f"/characters/{r.json()['id']}/choices/{scelta['id']}/resolve",
                          json={"kind": "asi", "increases": {"strength": 2}})
    assert r.status_code == 200, r.text
    assert next(s["value"] for s in r.json()["ability_scores"] if s["name"] == "strength") == 16
    assert all(c["id"] != scelta["id"] for c in r.json()["pending_choices"])
