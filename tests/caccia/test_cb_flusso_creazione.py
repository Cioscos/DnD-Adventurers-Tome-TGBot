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


@pytest.mark.xfail(strict=True, reason="CB-658 al cambio di specie gli incantesimi della vecchia specie restano sulla scheda e non sono nel riepilogo")
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
