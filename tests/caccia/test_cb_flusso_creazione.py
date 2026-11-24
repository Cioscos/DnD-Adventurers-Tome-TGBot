"""Controlli della zona flusso:creazione."""
import asyncio

import pytest

from core.rules.starting_equipment import STARTING_EQUIPMENT


def _classi(edizione):
    return sorted({c for (e, c) in STARTING_EQUIPMENT if e == edizione})


async def _lista(client):
    return (await client.get("/characters")).json()


@pytest.mark.caccia(id="CB-637", fonte="invariante: il livello di una classe va da 1 a 20 (CLAUDE.md · limiti livello 1 e 20)", zona="flusso:creazione",
                    voce="limiti", copre=["POST /characters"])
@pytest.mark.parametrize("livello", [0, -3, 21, 25])
async def test_livello_iniziale_fuori_da_1_20_rifiutato(client, livello):
    r = await client.post("/characters", json={"name": "L", "initial_class": {"class_name": "fighter", "level": livello}})
    assert r.status_code == 422, f"livello {livello}: {r.status_code} {r.text[:120]}"
    assert await _lista(client) == []


@pytest.mark.caccia(id="CB-638", fonte="invariante: un dado vita è un dado vero (2014 · Punti ferita e Dadi Vita · pag. 163): mai zero o negativo",
                    zona="flusso:creazione", voce="limiti", copre=["POST /characters"])
@pytest.mark.parametrize("dado", [0, -8])
async def test_dado_vita_non_positivo_rifiutato(client, dado):
    try:
        r = await client.post("/characters", json={"name": "D", "initial_class": {"class_name": "fighter", "hit_die": dado}})
    except Exception as e:  # il server esplode invece di rispondere
        pytest.fail(f"crash del server con hit_die={dado}: {e!r}")
    assert r.status_code == 422, f"hit_die {dado}: {r.status_code}"
    assert await _lista(client) == []


@pytest.mark.caccia(id="CB-639", fonte="2024 · Background · pag. 177-185 e Paladino · Equipaggiamento di Partenza (pag. 117)", zona="flusso:creazione",
                    voce="normale", copre=["POST /characters"])
async def test_creazione_2024_umano_soldato_paladino(client):
    corpo = {
        "name": "Z", "rules_edition": "2024",
        "species_2024": {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_lucky"}},
        "background_2024": {"key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "dice_set"},
        "initial_class": {"class_name": "paladin", "skill_choices": ["insight", "persuasion"]}, "starting_equipment": [0],
        "ability_scores": {"strength": 15, "dexterity": 10, "constitution": 14, "intelligence": 8, "wisdom": 10, "charisma": 13},
    }
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201
    pg = r.json()
    assert {a["name"]: a["value"] for a in pg["ability_scores"]}["strength"] == 17
    assert {a["name"]: a["value"] for a in pg["ability_scores"]}["dexterity"] == 11
    assert (pg["hit_points"], pg["current_hit_points"]) == (12, 12)  # d10 + COS 14 (+2)
    assert pg["currency"]["gold"] == 14 + 9  # soldato + paladino
    assert pg["background"] == "Soldato" and pg["race"] == "Umano" and pg["species_key"] == "2024_human"
    assert {"arcana", "athletics", "persuasion", "intimidation"} <= {k for k, v in pg["skills"].items() if v}
    nomi = {a["name"] for a in pg["abilities"]}
    assert {"Fortunato", "Attaccante selvaggio"} <= nomi
    assert pg["tool_proficiencies"] == {"dice_set": True}
    assert [s["total"] for s in pg["spell_slots"]] == [2]  # il Paladino 2024 lancia dal livello 1
    # niente è equipaggiato: CA senza armatura, 10 + modificatore di DES 11 (0)
    assert pg["ac"] == 10 and not any(i["is_equipped"] for i in pg["items"])


@pytest.mark.caccia(id="CB-640", fonte="2014 · Armature · pag. 145 e 2024 · Armature · pag. 219: CA dell'armatura e dello scudo con DES 18", zona="flusso:creazione",
                    voce="interazione", copre=["POST /characters", "PATCH /characters/{char_id}/items/{item_id}"])
@pytest.mark.parametrize("ed, classe, scelte, atteso", [
    ("2024", "cleric", [0], {"Giaco di maglia": 15, "Scudo": 17}),
    ("2024", "ranger", [0], {"Armatura di cuoio borchiato": 16}),
    ("2014", "ranger", [0, 0, 0, 0], {"Cotta di scaglie": 16}),
    ("2014", "cleric", [0, 2, 0, 0, 0], {"Cotta di maglia": 16, "Scudo": 18}),
    ("2014", "druid", [0, 0, 0], {"Scudo di legno": 16, "Armatura di cuoio": 17}),
])
async def test_armature_di_partenza_danno_la_ca_giusta(client, ed, classe, scelte, atteso):
    pg = (await client.post("/characters", json={"name": "A", "rules_edition": ed, "initial_class": {"class_name": classe},
                                                  "starting_equipment": scelte, "ability_scores": {"dexterity": 18}})).json()
    assert pg["ac"] == 14  # 10 + DES +4, nulla equipaggiato
    visti = {}
    for it in pg["items"]:
        if it["item_type"] in ("armor", "shield"):
            slot = "off_hand" if it["item_type"] == "shield" else "body"
            p = await client.patch(f"/characters/{pg['id']}/items/{it['id']}", json={"is_equipped": True, "equipment_slot": slot})
            visti[it["name"]] = p.json()["ac"]
    assert visti == atteso


@pytest.mark.caccia(id="CB-641", fonte="invariante: una creazione rifiutata non lascia personaggi a metà (CLAUDE.md · POST /characters atomico)", zona="flusso:creazione",
                    voce="annullamento", copre=["POST /characters", "GET /characters"])
@pytest.mark.parametrize("corpo", [
    {"rules_edition": "2024", "origin_feat": "bogus", "initial_class": {"class_name": "fighter"}},
    {"initial_class": {"class_name": "fighter", "skill_choices": ["foo"]}},
    {"initial_class": {"class_name": "fighter"}, "starting_equipment": [0, 0, 0, 9]},
    {"initial_class": {"class_name": "fighter"}, "starting_equipment": [0, 0, 0, -1]},
    {"rules_edition": "2024", "species_2024": {"key": "2024_elf", "options": {"lineage": "drow"}}},
])
async def test_creazione_rifiutata_non_lascia_orfani(client, corpo):
    r = await client.post("/characters", json={"name": "O", **corpo})
    assert r.status_code == 422
    assert await _lista(client) == []


@pytest.mark.caccia(id="CB-642", fonte="2024 · Specie · pag. 186 e invariante: cambiare specie toglie ciò che la vecchia specie aveva dato", zona="flusso:creazione",
                    voce="annullamento", copre=["PUT /characters/{char_id}/species", "POST /characters/{char_id}/species/preview"])
async def test_cambio_specie_toglie_abilita_e_talento_dati(client):
    corpo = {"name": "H", "rules_edition": "2024", "initial_class": {"class_name": "fighter", "skill_choices": ["athletics", "history"]},
             "species_2024": {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_lucky"}}}
    pg = (await client.post("/characters", json=corpo)).json()
    assert "Fortunato" in {a["name"] for a in pg["abilities"]} and pg["skills"]["arcana"] is True
    anteprima = await client.post(f"/characters/{pg['id']}/species/preview", json={"key": "2024_dwarf", "options": {}})
    assert set(anteprima.json()["changes"]) >= {"skill_removed:arcana", "feat_removed:2024_lucky"}
    assert (await client.get(f"/characters/{pg['id']}")).json()["race"] == "Umano"  # l'anteprima non scrive
    for _ in range(2):  # anche ripetuto
        nuovo = (await client.put(f"/characters/{pg['id']}/species", json={"key": "2024_dwarf", "options": {}})).json()
        assert nuovo["race"] == "Nano" and not nuovo["skills"].get("arcana")
        assert "Fortunato" not in {a["name"] for a in nuovo["abilities"]}
        assert {"athletics", "history"} <= {k for k, v in nuovo["skills"].items() if v}
        assert [a["name"] for a in nuovo["abilities"]].count("Robustezza nanica") == 1


@pytest.mark.caccia(id="CB-643", fonte="CLAUDE.md · API: ogni endpoint verifica il proprietario", zona="flusso:creazione",
                    voce="permessi", copre=["PUT /characters/{char_id}/species", "POST /characters/{char_id}/species/preview", "GET /characters"])
async def test_specie_e_lista_di_un_altro_utente(client, come_utente):
    pg = (await client.post("/characters", json={"name": "M", "rules_edition": "2024"})).json()
    come_utente(9999)
    assert (await client.put(f"/characters/{pg['id']}/species", json={"key": "2024_dwarf", "options": {}})).status_code in (403, 404)
    assert (await client.post(f"/characters/{pg['id']}/species/preview", json={"key": "2024_dwarf", "options": {}})).status_code in (403, 404)
    assert await _lista(client) == []
    come_utente(1234)
    assert (await client.get(f"/characters/{pg['id']}")).json()["race"] is None


@pytest.mark.caccia(id="CB-644", fonte="invariante: export, import e duplica conservano ciò che la creazione ha dato", zona="flusso:creazione",
                    voce="persistenza", copre=["POST /characters", "GET /characters/{char_id}/export", "POST /characters/import", "PUT /characters/{char_id}/species"])
async def test_creazione_sopravvive_a_export_import_e_cambio_specie(client):
    corpo = {"name": "Z", "rules_edition": "2024",
             "species_2024": {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_lucky"}},
             "background_2024": {"key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "dice_set"},
             "initial_class": {"class_name": "paladin", "skill_choices": ["insight", "persuasion"]}, "starting_equipment": [0]}
    pg = (await client.post("/characters", json=corpo)).json()

    def riassunto(c):
        return (c["race"], c["species_key"], c["background"], c["currency"]["gold"], sorted((a["name"], a["value"]) for a in c["ability_scores"]),
                sorted((i["name"], i["quantity"]) for i in c["items"]), sorted(a["name"] for a in c["abilities"]),
                sorted(k for k, v in c["skills"].items() if v), c["tool_proficiencies"])
    dati = (await client.get(f"/characters/{pg['id']}/export")).json()
    nuovo = (await client.post("/characters/import", json=dati)).json()
    dup = (await client.post(f"/characters/{pg['id']}/duplicate")).json()
    assert riassunto(nuovo) == riassunto(pg) == riassunto(dup)
    for copia in (nuovo, dup):  # il cambio di specie su una copia toglie ancora ciò che la vecchia specie aveva dato
        cambiato = (await client.put(f"/characters/{copia['id']}/species", json={"key": "2024_dwarf", "options": {}})).json()
        assert "Fortunato" not in {a["name"] for a in cambiato["abilities"]}
        assert not cambiato["skills"].get("arcana")
        assert "Attaccante selvaggio" in {a["name"] for a in cambiato["abilities"]}


@pytest.mark.caccia(id="CB-645", fonte="2014 · Ricchezza di Partenza delle Classi · pag. 143", zona="flusso:creazione", voce="regola",
                    copre=["POST /characters"])
@pytest.mark.parametrize("classe, dadi_n, moltiplicatore", [
    ("barbarian", 2, 10), ("bard", 5, 10), ("cleric", 5, 10), ("druid", 2, 10), ("fighter", 5, 10), ("rogue", 4, 10),
    ("wizard", 4, 10), ("monk", 5, 1), ("paladin", 5, 10), ("ranger", 5, 10), ("sorcerer", 3, 10), ("warlock", 4, 10),
])
async def test_ricchezza_di_partenza_2014(client, dadi, classe, dadi_n, moltiplicatore):
    dadi(*([3] * dadi_n))
    pg = (await client.post("/characters", json={"name": "W", "initial_class": {"class_name": classe}, "starting_wealth": True})).json()
    assert pg["currency"]["gold"] == dadi_n * 3 * moltiplicatore
    assert pg["items"] == []


@pytest.mark.caccia(id="CB-646", fonte="2024 · Equipaggiamento di Partenza delle classi (A in oggetti e monete, B solo monete)", zona="flusso:creazione",
                    voce="regola", copre=["POST /characters"])
@pytest.mark.parametrize("classe, oro_a, oro_b", [
    ("barbarian", 15, 75), ("bard", 19, 90), ("cleric", 7, 110), ("druid", 9, 50), ("fighter", 4, 155), ("monk", 11, 50),
    ("paladin", 9, 150), ("ranger", 7, 150), ("rogue", 8, 100), ("sorcerer", 28, 50), ("warlock", 15, 100), ("wizard", 5, 55),
])
async def test_equipaggiamento_2024_oro_per_classe(client, classe, oro_a, oro_b):
    base = {"name": "E", "rules_edition": "2024", "initial_class": {"class_name": classe}}
    gruppi = (await client.get(f"/rules/starting-equipment?edition=2024&class_key={classe}")).json()["groups"]
    assert len(gruppi) == 1
    a = (await client.post("/characters", json={**base, "starting_equipment": [0]})).json()
    b = (await client.post("/characters", json={**base, "starting_equipment": [len(gruppi[0]) - 1]})).json()
    assert a["currency"]["gold"] == oro_a and a["items"]
    assert b["currency"]["gold"] == oro_b and b["items"] == []


@pytest.mark.caccia(id="CB-647", fonte="2024 · Background · pag. 178-185: pacchetto A con le sue monete, B = 50 mo", zona="flusso:creazione",
                    voce="regola", copre=["POST /characters"])
@pytest.mark.parametrize("chiave, oro", [
    ("acolyte", 8), ("artisan", 32), ("charlatan", 15), ("criminal", 16), ("entertainer", 11), ("farmer", 30), ("guard", 12),
    ("guide", 3), ("hermit", 16), ("merchant", 22), ("noble", 29), ("sage", 8), ("sailor", 20), ("scribe", 23), ("soldier", 14), ("wayfarer", 16),
])
async def test_background_2024_oro_del_pacchetto(client, chiave, oro):
    from core.data.backgrounds_2024 import BACKGROUNDS_2024
    bg = BACKGROUNDS_2024[chiave]
    attrezzo = bg.tool[0] if isinstance(bg.tool, tuple) else None
    inc = {bg.abilities[0]: 2, bg.abilities[1]: 1}
    scelta = {"key": chiave, "increases": inc, **({"tool": attrezzo} if attrezzo else {})}
    pacchetto = (await client.post("/characters", json={"name": "B", "rules_edition": "2024", "background_2024": {**scelta, "equipment": "pack"}})).json()
    monete = (await client.post("/characters", json={"name": "B", "rules_edition": "2024", "background_2024": {**scelta, "equipment": "gold"}})).json()
    assert pacchetto["currency"]["gold"] == oro and pacchetto["items"]
    assert monete["currency"]["gold"] == 50 and monete["items"] == []


@pytest.mark.caccia(id="CB-648", fonte="CLAUDE.md · contratto del frontend: GET /rules/starting-equipment e scelte di POST /characters", zona="flusso:creazione",
                    voce="contratto", copre=["GET /rules/starting-equipment", "POST /characters"])
async def test_opzioni_equipaggiamento_accettate_da_creazione(client):
    for ed in ("2014", "2024"):
        for classe in _classi(ed):
            r = (await client.get(f"/rules/starting-equipment?edition={ed}&class_key={classe}")).json()
            assert r["groups"] and all(g for g in r["groups"])
            assert (r["wealth"] is None) == (ed == "2024")
            for scelte in ([0] * len(r["groups"]), [len(g) - 1 for g in r["groups"]]):
                p = await client.post("/characters", json={"name": "C", "rules_edition": ed, "initial_class": {"class_name": classe}, "starting_equipment": scelte})
                assert p.status_code == 201, (ed, classe, scelte, p.text[:100])
    vuoto = (await client.get("/rules/starting-equipment?edition=2014&class_key=Cacciatore di Taglie")).json()
    assert vuoto == {"groups": [], "wealth": None}
    assert (await client.get("/rules/starting-equipment?edition=2014&class_key=monk")).json()["wealth"] == {"dice": "5d4", "multiplier": 1}


@pytest.mark.caccia(id="CB-649", fonte="CLAUDE.md · specie, background e talento d'Origine dei cataloghi sono solo 2024", zona="flusso:creazione",
                    voce="edizioni", copre=["POST /characters"])
@pytest.mark.parametrize("extra, codice", [
    ({"species_2024": {"key": "2024_dwarf", "options": {}}}, "species_edition"),
    ({"background_2024": {"key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "dice_set"}}, "background_edition"),
])
async def test_cataloghi_2024_rifiutati_nel_2014(client, extra, codice):
    r = await client.post("/characters", json={"name": "E", "rules_edition": "2014", **extra})
    assert (r.status_code, r.json()["detail"]) == (422, codice)
    assert (await client.post("/characters", json={"name": "E", "origin_feat": "2024_alert"})).status_code == 422
    assert await _lista(client) == []


@pytest.mark.caccia(id="CB-650", fonte="2024 · Punteggi di caratteristica · pag. 10 e Background · pag. 177 (massimo 20)", zona="flusso:creazione",
                    voce="limiti", copre=["POST /characters"])
async def test_punteggi_e_aumenti_del_background_al_massimo_20(client):
    bg = {"key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "dice_set"}
    for forza, atteso in ((18, 201), (19, 422)):
        r = await client.post("/characters", json={"name": "M", "rules_edition": "2024", "ability_scores": {"strength": forza}, "background_2024": bg})
        assert r.status_code == atteso, forza
    assert (await client.post("/characters", json={"name": "M", "ability_scores": {"strength": 2}})).status_code == 422
    assert (await client.post("/characters", json={"name": "M", "ability_scores": {"strength": 21}})).status_code == 422
    assert (await client.post("/characters", json={"name": "M", "ability_scores": {"strength": 3, "dexterity": 20}})).status_code == 201


@pytest.mark.caccia(id="CB-651", fonte="2024 · Nano · Robustezza nanica (pag. 191) e Contadino · Robusto: +1 / +2 PF per livello", zona="flusso:creazione",
                    voce="interazione", copre=["POST /characters", "GET /characters"])
async def test_pf_massimi_in_lista_con_specie_e_talento(client):
    nano = (await client.post("/characters", json={"name": "N", "rules_edition": "2024", "species_2024": {"key": "2024_dwarf", "options": {}},
                                                    "initial_class": {"class_name": "fighter", "level": 3}})).json()["id"]
    contadino = (await client.post("/characters", json={"name": "C", "rules_edition": "2024",
                                                         "background_2024": {"key": "farmer", "increases": {"strength": 2, "constitution": 1}},
                                                         "initial_class": {"class_name": "fighter", "level": 2}})).json()["id"]
    righe = {r["id"]: r for r in await _lista(client)}
    # d10 al 1, 6 per livello successivo, COS 10 (nano) / 11 (contadino, +0)
    assert (righe[nano]["hit_points"], righe[nano]["hp_max_effective"], righe[nano]["current_hit_points"]) == (22, 25, 25)
    assert (righe[contadino]["hit_points"], righe[contadino]["hp_max_effective"], righe[contadino]["current_hit_points"]) == (16, 20, 20)


@pytest.mark.caccia(id="CB-652", fonte="invariante: una scelta della specie che andrebbe persa in silenzio si rifiuta", zona="flusso:creazione",
                    voce="limiti", copre=["POST /characters", "PUT /characters/{char_id}/species"])
async def test_abilita_della_specie_gia_presa_dalla_classe(client):
    elfo = {"key": "2024_elf", "options": {"lineage": "high", "spell_ability": "intelligence", "skill": "perception"}}
    r = await client.post("/characters", json={"name": "E", "rules_edition": "2024", "species_2024": elfo,
                                               "initial_class": {"class_name": "ranger", "skill_choices": ["perception", "stealth", "survival"]}})
    assert (r.status_code, r.json()["detail"]) == (422, "species_skill_taken")
    pg = (await client.post("/characters", json={"name": "E", "rules_edition": "2024"})).json()
    cattiva = {"key": "2024_elf", "options": {"lineage": "high", "spell_ability": "intelligence", "skill": "stealth"}}
    assert (await client.put(f"/characters/{pg['id']}/species", json=cattiva)).status_code == 422
    assert (await client.get(f"/characters/{pg['id']}")).json()["species_key"] is None


@pytest.mark.caccia(id="CB-656", fonte="invariante: due richieste uguali insieme non spendono né creano due volte", zona="flusso:creazione",
                    voce="ripetizione", copre=["PUT /characters/{char_id}/species"])
async def test_due_cambi_specie_insieme(client):
    corpo = {"name": "H", "rules_edition": "2024", "initial_class": {"class_name": "fighter", "skill_choices": ["athletics", "history"]},
             "species_2024": {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_lucky"}}}
    cid = (await client.post("/characters", json=corpo)).json()["id"]
    r = await asyncio.gather(*[client.put(f"/characters/{cid}/species", json={"key": "2024_dwarf", "options": {}}) for _ in range(2)],
                             return_exceptions=True)
    assert all(not isinstance(x, Exception) and x.status_code == 200 for x in r), [getattr(x, "status_code", repr(x)) for x in r]
    pg = (await client.get(f"/characters/{cid}")).json()
    nomi = [a["name"] for a in pg["abilities"]]
    assert nomi.count("Robustezza nanica") == 1 and "Fortunato" not in nomi
    assert not pg["skills"].get("arcana")


@pytest.mark.caccia(id="CB-657", fonte="invariante: il nome è salvato ripulito dagli spazi ai bordi, alla creazione come alla modifica", zona="flusso:creazione",
                    voce="limiti", copre=["POST /characters", "PATCH /characters/{char_id}"])
async def test_nome_ripulito_alla_creazione_come_alla_modifica(client):
    cid = (await client.post("/characters", json={"name": "X"})).json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"name": "  Q  "})).json()["name"] == "Q"
    r = await client.post("/characters", json={"name": "  Pippo  "})
    assert r.status_code == 201
    assert r.json()["name"] == "Pippo"


@pytest.mark.caccia(id="CB-658", fonte="decisione D-005 (2024 · Specie · Elfo · pag. 190)", zona="flusso:creazione", voce="annullamento",
                    copre=["PUT /characters/{char_id}/species", "POST /characters/{char_id}/species/preview"])
async def test_cambio_specie_toglie_gli_incantesimi_della_vecchia(client):
    elfo = {"key": "2024_elf", "options": {"lineage": "high", "spell_ability": "intelligence", "skill": "insight"}}
    cid = (await client.post("/characters", json={"name": "E", "rules_edition": "2024", "species_2024": elfo,
                                                  "initial_class": {"class_name": "wizard", "level": 5, "skill_choices": ["arcana", "history"]}})).json()["id"]
    nomi = lambda pg: {s["name"] for s in pg["spells"]}  # noqa: E731
    dati = {"Prestidigitazione", "Individuazione del magico", "Passo velato"}
    assert dati <= nomi((await client.get(f"/characters/{cid}")).json())
    manuale = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo incantato", "level": 1})
    assert manuale.status_code in (200, 201)
    cambi = (await client.post(f"/characters/{cid}/species/preview", json={"key": "2024_halfling", "options": {}})).json()["changes"]
    pg = (await client.put(f"/characters/{cid}/species", json={"key": "2024_halfling", "options": {}})).json()
    assert "Dardo incantato" in nomi(pg)  # quello aggiunto a mano resta
    assert not dati & nomi(pg), f"restano {dati & nomi(pg)}"
    assert sum("spell" in c for c in cambi) >= 3, cambi


@pytest.mark.caccia(id="CB-659", fonte="decisione D-006 (2024 · Competenze nelle abilità · pag. 13-14)", zona="flusso:creazione", voce="limiti",
                    copre=["POST /characters"])
async def test_abilita_di_classe_gia_data_dal_background(client):
    soldato = {"key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "dice_set"}
    base = {"name": "S", "rules_edition": "2024", "background_2024": soldato}
    bene = await client.post("/characters", json={**base, "initial_class": {"class_name": "fighter", "skill_choices": ["acrobatics", "persuasion"]}})
    assert bene.status_code == 201  # precondizione verde
    assert {k for k, v in bene.json()["skills"].items() if v} == {"athletics", "intimidation", "acrobatics", "persuasion"}
    r = await client.post("/characters", json={**base, "initial_class": {"class_name": "fighter", "skill_choices": ["athletics", "persuasion"]}})
    assert r.status_code == 422, r.status_code
    assert len(await _lista(client)) == 1


@pytest.mark.caccia(id="CB-771", fonte="2014 · Background · competenza da due fonti: se ne sceglie un'altra; decisione D-012", zona="flusso:creazione", voce="regola",
                    copre=["POST /characters"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_abilita_di_classe_gia_fra_quelle_del_background_scritto(client, edizione):
    def corpo(scelte):
        return {"name": "Doppia", "rules_edition": edizione, "skills": {"insight": True, "religion": True, "history": False},
                "initial_class": {"class_name": "cleric", "level": 1, "hit_die": 8, "skill_choices": scelte}}
    r = await client.post("/characters", json=corpo(["insight", "history"]))
    assert (r.status_code, r.json()["detail"]) == (422, "class_skill_taken")
    r = await client.post("/characters", json=corpo(["medicine", "history"]))
    assert r.status_code == 201
    assert sorted(k for k, v in r.json()["skills"].items() if v) == ["history", "insight", "medicine", "religion"]


# ---------------------------------------------------------------------------
# Giro 3: classe, abilità, PF, specie, background, permessi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1373", fonte="invariante: una classe ha un nome, come il personaggio (CB-657): niente righe di classe vuote", zona="flusso:creazione",
                    voce="limiti", copre=["POST /characters"])
@pytest.mark.parametrize("nome", [
    "",
    "   ",
])
async def test_classe_senza_nome_rifiutata(client, nome):
    r = await client.post("/characters", json={"name": "N", "initial_class": {"class_name": nome, "hit_die": 8}})
    assert r.status_code == 422, f"class_name {nome!r}: {r.status_code} {r.text[:100]}"
    assert await _lista(client) == []


@pytest.mark.caccia(id="CB-1374", fonte="invariante: la caratteristica da incantatore è una delle sei caratteristiche", zona="flusso:creazione",
                    voce="limiti", copre=["POST /characters"])
async def test_caratteristica_da_incantatore_sconosciuta_rifiutata(client):
    r = await client.post("/characters", json={"name": "I", "initial_class": {"class_name": "wizard", "spellcasting_ability": "foo"}})
    assert r.status_code == 422, f"{r.status_code} {r.text[:100]}"
    assert await _lista(client) == []


_TUTTE = ["acrobatics", "animal_handling", "arcana", "athletics", "deception", "history", "insight", "intimidation", "investigation", "medicine",
          "nature", "perception", "performance", "persuasion", "religion", "sleight_of_hand", "stealth", "survival"]
_ABILITA_CLASSE = [
    ("2014", "barbarian", 2, "animal_handling athletics intimidation nature perception survival"),
    ("2014", "bard", 3, " ".join(_TUTTE)),
    ("2014", "cleric", 2, "history insight medicine persuasion religion"),
    ("2014", "druid", 2, "animal_handling arcana insight medicine nature perception religion survival"),
    ("2014", "fighter", 2, "acrobatics animal_handling athletics history insight intimidation perception survival"),
    ("2014", "monk", 2, "acrobatics athletics history insight religion stealth"),
    ("2014", "paladin", 2, "athletics insight intimidation medicine persuasion religion"),
    ("2014", "ranger", 3, "animal_handling athletics insight investigation nature perception stealth survival"),
    ("2014", "rogue", 4, "acrobatics athletics deception insight intimidation investigation perception performance persuasion sleight_of_hand stealth"),
    ("2014", "warlock", 2, "arcana deception history intimidation investigation nature religion"),
    ("2014", "wizard", 2, "arcana history insight investigation medicine religion"),
    ("2024", "barbarian", 2, "animal_handling athletics intimidation nature perception survival"),
    ("2024", "bard", 3, " ".join(_TUTTE)),
    ("2024", "cleric", 2, "history insight medicine persuasion religion"),
    ("2024", "druid", 2, "animal_handling arcana insight medicine nature perception religion survival"),
    ("2024", "fighter", 2, "acrobatics animal_handling athletics history insight intimidation perception persuasion survival"),
    ("2024", "monk", 2, "acrobatics athletics history insight religion stealth"),
    ("2024", "paladin", 2, "athletics insight intimidation medicine persuasion religion"),
    ("2024", "ranger", 3, "animal_handling athletics insight investigation nature perception stealth survival"),
    ("2024", "rogue", 4, "acrobatics athletics deception insight intimidation investigation perception persuasion sleight_of_hand stealth"),
    ("2024", "sorcerer", 2, "arcana deception insight intimidation persuasion religion"),
    ("2024", "warlock", 2, "arcana deception history intimidation investigation nature religion"),
    ("2024", "wizard", 2, "arcana history insight investigation medicine nature religion"),
]


@pytest.mark.caccia(id="CB-1375", fonte="2014 e 2024 · Classi · Competenze al 1° livello (abilità a scelta per classe): lista e numero, es. Guerriero 2024 con Persuasione, Mago 2024 con Natura, Ladro 2024 senza Intrattenere",
                    zona="flusso:creazione", voce="regola", copre=["GET /rules/proficiencies", "POST /characters"])
@pytest.mark.parametrize("ed, classe, n, lista", _ABILITA_CLASSE)
async def test_abilita_di_classe_per_edizione(client, ed, classe, n, lista):
    attese = lista.split()
    prof = (await client.get(f"/rules/proficiencies?edition={ed}&class_key={classe}&as_multiclass=false")).json()
    assert prof["skills_count"] == n
    assert sorted(prof["skills_from"] or _TUTTE) == sorted(attese)  # il contratto che legge il frontend
    base = {"name": "A", "rules_edition": ed}
    ok = await client.post("/characters", json={**base, "initial_class": {"class_name": classe, "skill_choices": sorted(attese)[:n]}})
    assert ok.status_code == 201, ok.text[:100]
    troppe = await client.post("/characters", json={**base, "initial_class": {"class_name": classe, "skill_choices": sorted(attese)[:n + 1]}})
    assert troppe.status_code == 422
    fuori = [s for s in _TUTTE if s not in attese]
    if fuori:
        r = await client.post("/characters", json={**base, "initial_class": {"class_name": classe, "skill_choices": [fuori[0]]}})
        assert r.status_code == 422, f"{fuori[0]} non è della lista di {classe} {ed}"


_DADO = {"barbarian": 12, "bard": 8, "cleric": 8, "druid": 8, "fighter": 10, "monk": 8, "paladin": 10, "ranger": 10,
         "rogue": 8, "sorcerer": 6, "warlock": 8, "wizard": 6}


@pytest.mark.caccia(id="CB-1376", fonte="2014 e 2024 · Classi · Punti Ferita: dado vita pieno + COS al 1° livello, poi media (dado/2 + 1) + COS; livello 19 con COS 14",
                    zona="flusso:creazione", voce="limiti", copre=["POST /characters", "GET /characters"])
@pytest.mark.parametrize("ed", ["2014", "2024"])
async def test_pf_massimi_al_livello_19_per_classe(client, ed):
    for classe, d in _DADO.items():
        pg = (await client.post("/characters", json={"name": "H", "rules_edition": ed, "ability_scores": {"constitution": 14},
                                                      "initial_class": {"class_name": classe, "level": 19}})).json()
        atteso = d + 2 + 18 * (d // 2 + 1 + 2)
        assert (pg["hit_points"], pg["current_hit_points"]) == (atteso, atteso), (ed, classe)
    righe = {r["id"]: r for r in await _lista(client)}
    assert all(r["hit_points"] == r["current_hit_points"] for r in righe.values())


@pytest.mark.caccia(id="CB-1377", fonte="2024 · Specie · Elfo (lignaggio alto, pag. 190) e Tiefling (eredità infernale, pag. 197): incantesimi extra ai livelli 3 e 5",
                    zona="flusso:creazione", voce="limiti", copre=["POST /characters"])
async def test_incantesimi_di_lignaggio_alle_soglie_di_livello(client):
    elfo = {"key": "2024_elf", "options": {"lineage": "high", "spell_ability": "intelligence", "skill": "insight"}}
    tiefling = {"key": "2024_tiefling", "options": {"size": "medium", "legacy": "infernal", "spell_ability": "charisma"}}
    atteso = {
        (elfo["key"], 1): {"Prestidigitazione"}, (elfo["key"], 2): {"Prestidigitazione"},
        (elfo["key"], 3): {"Prestidigitazione", "Individuazione del magico"},
        (elfo["key"], 4): {"Prestidigitazione", "Individuazione del magico"},
        (elfo["key"], 5): {"Prestidigitazione", "Individuazione del magico", "Passo velato"},
        (tiefling["key"], 2): {"Dardo di fuoco", "Taumaturgia"},
        (tiefling["key"], 3): {"Dardo di fuoco", "Taumaturgia", "Rimprovero infernale"},
        (tiefling["key"], 4): {"Dardo di fuoco", "Taumaturgia", "Rimprovero infernale"},
        (tiefling["key"], 5): {"Dardo di fuoco", "Taumaturgia", "Rimprovero infernale", "Oscurità"},
    }
    for (chiave, livello), nomi in atteso.items():
        specie = elfo if chiave == "2024_elf" else tiefling
        pg = (await client.post("/characters", json={"name": "L", "rules_edition": "2024", "species_2024": specie,
                                                      "initial_class": {"class_name": "fighter", "level": livello}})).json()
        assert {s["name"] for s in pg["spells"]} == nomi, (chiave, livello)


@pytest.mark.caccia(id="CB-1378", fonte="2024 · Specie · Goliath (pag. 192) e Elfo dei boschi (pag. 190): velocità 35 piedi; Nano e Drow scurovisione 120 piedi (pag. 188, 190)",
                    zona="flusso:creazione", voce="persistenza", copre=["POST /characters", "GET /characters/{char_id}/export", "POST /characters/import"])
async def test_velocita_e_sensi_di_specie_sopravvivono_a_import_e_copia(client):
    casi = [
        ({"key": "2024_goliath", "options": {"giant": "fire"}}, 35, None),
        ({"key": "2024_elf", "options": {"lineage": "wood", "spell_ability": "wisdom", "skill": "insight"}}, 35, 60),
        ({"key": "2024_elf", "options": {"lineage": "drow", "spell_ability": "wisdom", "skill": "insight"}}, 30, 120),
        ({"key": "2024_dwarf", "options": {}}, 30, 120),
    ]
    for specie, velocita, buio in casi:
        pg = (await client.post("/characters", json={"name": "V", "rules_edition": "2024", "species_2024": specie, "initial_class": {"class_name": "fighter"}})).json()
        export = (await client.get(f"/characters/{pg['id']}/export")).json()
        copie = [pg, (await client.get(f"/characters/{pg['id']}")).json(), (await client.post("/characters/import", json=export)).json(),
                 (await client.post(f"/characters/{pg['id']}/duplicate")).json()]
        for c in copie:
            visti = {s["type"]: s["range_ft"] for s in c["computed"]["senses"]}
            assert (c["computed"]["speed"], visti.get("darkvision")) == (velocita, buio), (specie, c["name"])


@pytest.mark.caccia(id="CB-1379", fonte="invariante: i PF correnti non superano mai il massimo (2014 · Punti ferita pag. 196, 2024 · Punti ferita), anche dopo un cambio di specie o la rimozione di Robusto che abbassa il massimo",
                    zona="flusso:creazione", voce="annullamento", copre=["PUT /characters/{char_id}/species", "DELETE /characters/{char_id}/abilities/{ability_id}", "GET /characters/{char_id}"])
@pytest.mark.parametrize("modo", ["nano", "halfling", "umano_altro_talento", "rimuovi_robusto"])
async def test_massimo_che_cala_non_lascia_pf_correnti_oltre(client, modo):
    umano = {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_tough"}}
    corpo = {"name": "R", "rules_edition": "2024", "species_2024": umano,
             "initial_class": {"class_name": "fighter", "level": 3, "skill_choices": ["athletics", "history"]}}
    pg = (await client.post("/characters", json=corpo)).json()  # d10 + 6 + 6 = 22, Robusto +6: 28 a PF pieni
    cid = pg["id"]
    if modo == "rimuovi_robusto":
        riga = next(a for a in pg["abilities"] if a["name"] == "Robusto")
        assert (await client.delete(f"/characters/{cid}/abilities/{riga['id']}")).status_code == 204
        massimo = 22
    else:
        nuova = {"nano": ("2024_dwarf", {}), "halfling": ("2024_halfling", {}),
                 "umano_altro_talento": ("2024_human", {"size": "medium", "skill": "arcana", "origin_feat": "2024_alert"})}[modo]
        r = await client.put(f"/characters/{cid}/species", json={"key": nuova[0], "options": nuova[1]})
        assert r.status_code == 200, r.text[:100]
        massimo = {"nano": 25, "halfling": 22, "umano_altro_talento": 22}[modo]
    letta = (await client.get(f"/characters/{cid}")).json()
    assert letta["computed"]["hp_max_effective"] == massimo
    assert letta["current_hit_points"] <= massimo, f"PF correnti {letta['current_hit_points']} oltre il massimo {massimo}"


@pytest.mark.caccia(id="CB-1383", fonte="2024 · Specie · Nano (Robustezza nanica, pag. 188) e Talenti · Robusto: PF massimi +1 / +2 per livello; cambiare specie e tornare indietro riporta lo stesso massimo e gli stessi tratti",
                    zona="flusso:creazione", voce="annullamento", copre=["PUT /characters/{char_id}/species", "GET /characters"])
async def test_cambio_specie_e_ritorno_riportano_massimo_e_tratti(client):
    umano = {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_tough"}}
    corpo = {"name": "R", "rules_edition": "2024", "species_2024": umano,
             "initial_class": {"class_name": "fighter", "level": 3, "skill_choices": ["athletics", "history"]}}
    cid = (await client.post("/characters", json=corpo)).json()["id"]

    async def stato():
        scheda = (await client.get(f"/characters/{cid}")).json()
        riga = next(r for r in await _lista(client) if r["id"] == cid)
        assert riga["hp_max_effective"] == scheda["computed"]["hp_max_effective"], "la lista e la scheda devono concordare"
        return scheda["computed"]["hp_max_effective"], sorted(a["name"] for a in scheda["abilities"]), scheda["skills"].get("arcana")
    inizio = await stato()
    assert inizio[0] == 28 and inizio[2] is True
    await client.put(f"/characters/{cid}/species", json={"key": "2024_dwarf", "options": {}})
    assert (await stato())[0] == 25 and not (await stato())[2]
    await client.put(f"/characters/{cid}/species", json=umano)
    assert await stato() == inizio


@pytest.mark.caccia(id="CB-1380", fonte="invariante: due creazioni identiche insieme danno due schede separate, ciascuna con un solo set di oggetti, monete e talenti", zona="flusso:creazione",
                    voce="ripetizione", copre=["POST /characters"])
async def test_due_creazioni_insieme_non_mescolano_oggetti_e_monete(client):
    corpo = {"name": "D", "rules_edition": "2024", "species_2024": {"key": "2024_dwarf", "options": {}},
             "background_2024": {"key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "dice_set"},
             "initial_class": {"class_name": "paladin", "skill_choices": ["insight", "persuasion"]}, "starting_equipment": [0]}
    r = await asyncio.gather(*[client.post("/characters", json=corpo) for _ in range(3)], return_exceptions=True)
    assert all(not isinstance(x, Exception) and x.status_code == 201 for x in r), [getattr(x, "status_code", repr(x)) for x in r]
    schede = [x.json() for x in r]
    assert len({s["id"] for s in schede}) == 3
    for s in await _lista(client):
        assert s["name"] == "D"
    for s in schede:
        s = (await client.get(f"/characters/{s['id']}")).json()
        assert s["currency"]["gold"] == 14 + 9
        assert len(s["items"]) == len({i["id"] for i in s["items"]})
        assert [a["name"] for a in s["abilities"]].count("Robustezza nanica") == 1
    assert len({tuple(sorted((i["name"], i["quantity"]) for i in s["items"])) for s in schede}) == 1


@pytest.mark.caccia(id="CB-1381", fonte="CLAUDE.md · API: ogni endpoint verifica il proprietario (export, duplica, import con un altro utente)", zona="flusso:creazione",
                    voce="permessi", copre=["GET /characters/{char_id}/export", "POST /characters/{char_id}/duplicate", "POST /characters/import"])
async def test_export_e_duplica_di_un_altro_utente(client, come_utente):
    pg = (await client.post("/characters", json={"name": "P", "rules_edition": "2024", "initial_class": {"class_name": "fighter"}})).json()
    export = (await client.get(f"/characters/{pg['id']}/export")).json()
    come_utente(9999)
    assert (await client.get(f"/characters/{pg['id']}/export")).status_code in (403, 404)
    assert (await client.post(f"/characters/{pg['id']}/duplicate")).status_code in (403, 404)
    assert await _lista(client) == []
    mio = (await client.post("/characters/import", json=export)).json()  # il file di un altro, importato da me, è mio
    assert [r["id"] for r in await _lista(client)] == [mio["id"]]
    come_utente(1234)
    assert [r["id"] for r in await _lista(client)] == [pg["id"]]


@pytest.mark.caccia(id="CB-1382", fonte="2014 · Paladino e Ranger · Incantesimi dal 2° livello; 2024 · Paladino e Ranger · Incantatore dal 1° livello", zona="flusso:creazione",
                    voce="edizioni", copre=["POST /characters"])
@pytest.mark.parametrize("classe", ["paladin", "ranger"])
async def test_slot_dei_mezzi_incantatori_alla_creazione(client, classe):
    def slot(pg):
        return [s["total"] for s in pg["spell_slots"]]
    for ed, livello, atteso in (("2014", 1, []), ("2014", 2, [2]), ("2024", 1, [2]), ("2024", 2, [2])):
        pg = (await client.post("/characters", json={"name": "S", "rules_edition": ed, "initial_class": {"class_name": classe, "level": livello}})).json()
        assert slot(pg) == atteso, (ed, classe, livello)


_TOOL = {"artisan": "alchemists_supplies", "instrument": "bagpipes", "gaming": "dice_set"}
_BACKGROUND = {  # chiave: (talento, abilità, strumento fisso o categoria, caratteristiche)
    "acolyte": ("Iniziato alla magia", ["insight", "religion"], "calligraphers_supplies", ["intelligence", "wisdom", "charisma"]),
    "artisan": ("Artigiano", ["investigation", "persuasion"], "artisan", ["strength", "dexterity", "intelligence"]),
    "charlatan": ("Abile", ["deception", "sleight_of_hand"], "forgery_kit", ["dexterity", "constitution", "charisma"]),
    "criminal": ("Allerta", ["sleight_of_hand", "stealth"], "thieves_tools", ["dexterity", "constitution", "intelligence"]),
    "entertainer": ("Musicista", ["acrobatics", "performance"], "instrument", ["strength", "dexterity", "charisma"]),
    "farmer": ("Robusto", ["animal_handling", "nature"], "carpenters_tools", ["strength", "constitution", "wisdom"]),
    "guard": ("Allerta", ["athletics", "perception"], "gaming", ["strength", "intelligence", "wisdom"]),
    "guide": ("Iniziato alla magia", ["stealth", "survival"], "cartographers_tools", ["dexterity", "constitution", "wisdom"]),
    "hermit": ("Guaritore", ["medicine", "religion"], "herbalism_kit", ["constitution", "wisdom", "charisma"]),
    "merchant": ("Fortunato", ["animal_handling", "persuasion"], "navigators_tools", ["constitution", "intelligence", "charisma"]),
    "noble": ("Abile", ["history", "persuasion"], "gaming", ["strength", "intelligence", "charisma"]),
    "sage": ("Iniziato alla magia", ["arcana", "history"], "calligraphers_supplies", ["constitution", "intelligence", "wisdom"]),
    "sailor": ("Attaccabrighe da taverna", ["acrobatics", "perception"], "navigators_tools", ["strength", "dexterity", "wisdom"]),
    "scribe": ("Abile", ["investigation", "perception"], "calligraphers_supplies", ["dexterity", "intelligence", "wisdom"]),
    "soldier": ("Attaccante selvaggio", ["athletics", "intimidation"], "gaming", ["strength", "dexterity", "constitution"]),
    "wayfarer": ("Fortunato", ["insight", "stealth"], "thieves_tools", ["dexterity", "wisdom", "charisma"]),
}


@pytest.mark.caccia(id="CB-1384", fonte="2024 · Background · pag. 177-185: caratteristiche, talento d'Origine, due abilità e strumento di ciascuno dei sedici background",
                    zona="flusso:creazione", voce="regola", copre=["POST /characters"])
@pytest.mark.parametrize("chiave", list(_BACKGROUND))
async def test_background_2024_come_nel_manuale(client, chiave):
    talento, abilita, strumento, caratteristiche = _BACKGROUND[chiave]
    scelto = _TOOL.get(strumento, strumento)
    base = {"name": "B", "rules_edition": "2024"}
    corpo = {"key": chiave, "increases": {c: 1 for c in caratteristiche}, **({"tool": scelto} if strumento in _TOOL else {})}
    pg = (await client.post("/characters", json={**base, "background_2024": corpo})).json()
    assert [a["name"] for a in pg["abilities"]] == [talento]
    assert sorted(k for k, v in pg["skills"].items() if v) == sorted(abilita)
    assert pg["tool_proficiencies"] == {scelto: True}
    assert sorted(a["name"] for a in pg["ability_scores"] if a["value"] == 11) == sorted(caratteristiche)
    estranea = next(a for a in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma") if a not in caratteristiche)
    r = await client.post("/characters", json={**base, "background_2024": {**corpo, "increases": {estranea: 2, caratteristiche[0]: 1}}})
    assert r.status_code == 422, f"{estranea} non è fra le caratteristiche di {chiave}"


def _somma(pg):
    totale = {}
    for i in pg["items"]:
        chiave = (i["item_metadata"] or {}).get("srd_index") or i["name"]
        totale[chiave] = totale.get(chiave, 0) + i["quantity"]
    return totale


@pytest.mark.caccia(id="CB-1385", fonte="2014 · Classi · Equipaggiamento (Barbaro pag. 48, Guerriero pag. 71, Ladro pag. 78, Monaco pag. 90): quantità e pezzi di ogni scelta",
                    zona="flusso:creazione", voce="regola", copre=["POST /characters"])
@pytest.mark.parametrize("classe, scelte, atteso", [
    ("barbarian", [0, 0, 0, 0], {"greataxe": 1, "handaxe": 2, "Dotazione da esploratore": 1, "javelin": 4}),
    ("barbarian", [1, 1, 0, 0], {"Arma da guerra da mischia a scelta": 1, "Arma semplice a scelta": 1, "Dotazione da esploratore": 1, "javelin": 4}),
    ("fighter", [1, 1, 1, 1], {"leather-armor": 1, "longbow": 1, "Frecce": 20, "Arma da guerra a scelta": 2, "handaxe": 2, "Dotazione da esploratore": 1}),
    ("fighter", [0, 0, 0, 0], {"chain-mail": 1, "Arma da guerra a scelta": 1, "shield": 1, "crossbow-light": 1, "Quadrelli": 20, "Dotazione da avventuriero": 1}),
    ("rogue", [1, 1, 2, 0], {"shortsword": 2, "Dotazione da esploratore": 1, "leather-armor": 1, "dagger": 2, "Arnesi da scasso": 1}),
    ("monk", [0, 0, 0], {"shortsword": 1, "Dotazione da avventuriero": 1, "dart": 10}),
])
async def test_equipaggiamento_2014_quantita_come_nel_manuale(client, classe, scelte, atteso):
    pg = (await client.post("/characters", json={"name": "Q", "initial_class": {"class_name": classe}, "starting_equipment": scelte})).json()
    assert _somma(pg) == atteso
    assert pg["currency"]["gold"] == 0


@pytest.mark.caccia(id="CB-1386", fonte="2014 · Guerriero, Ladro, Monaco · Equipaggiamento: «non si ottiene entrando nella classe come multiclasse (pag. 164)»; 2024 · Multiclasse",
                    zona="flusso:creazione", voce="interazione", copre=["POST /characters", "POST /characters/{char_id}/classes"])
@pytest.mark.parametrize("ed", ["2014", "2024"])
async def test_seconda_classe_non_da_equipaggiamento_di_partenza(client, ed):
    scelte = [0, 0, 0, 0] if ed == "2014" else [0]
    pg = (await client.post("/characters", json={"name": "M", "rules_edition": ed, "ability_scores": {"strength": 14, "dexterity": 14},
                                                  "initial_class": {"class_name": "fighter"}, "starting_equipment": scelte})).json()
    prima = (_somma(pg), pg["currency"]["gold"])
    r = await client.post(f"/characters/{pg['id']}/classes", json={"class_name": "rogue", "level": 1, "skill_choices": ["stealth"]})
    assert r.status_code == 201, r.text[:150]
    dopo = (await client.get(f"/characters/{pg['id']}")).json()
    assert (_somma(dopo), dopo["currency"]["gold"]) == prima
