"""Controlli della zona regola:2014/equipaggiamento."""
import json
from pathlib import Path

import pytest

_SRD = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "equipment.json"


async def _pg(client, classe="fighter", livello=1, **punteggi) -> int:
    corpo = {"name": "Prova", "rules_edition": "2014", "initial_class": {"class_name": classe, "level": livello}}
    if punteggi:
        corpo["ability_scores"] = punteggi
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _oggetto(client, cid, nome, tipo, **extra) -> int:
    r = await client.post(f"/characters/{cid}/items", json={"name": nome, "item_type": tipo, **extra})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _indossa(client, cid, iid, slot):
    return await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": slot})


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3161", fonte="2014 · Equipaggiamento · Proprietà delle armi: Versatile (danno tra parentesi a due mani in mischia) e Lancio · pag. 147",
                    zona="regola:2014/equipaggiamento", voce="interazione",
                    copre=["carta:2014/equipment.md#Proprieta delle Armi / Weapon Properties (pagg. 146-147)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.xfail(strict=True, reason="CB-3161: difforme dal manuale, confermato")
async def test_lancia_lanciata_a_due_mani_non_usa_il_dado_versatile(client, dadi):
    cid = await _pg(client, strength=14)
    lancia = await _oggetto(client, cid, "Lancia", "weapon", item_metadata={
        "damage_dice": "1d6", "versatile_dice": "1d8", "weapon_type": "melee", "weapon_category": "simple",
        "properties": ["prop_thrown", "prop_versatile"]})
    dadi(4)
    r = await client.post(f"/characters/{cid}/items/{lancia}/attack",
                          json={"die": 15, "attack_mode": "thrown", "grip": "two"})
    assert r.status_code == 200, r.text
    # il dado tra parentesi vale solo per l'attacco in mischia a due mani: lanciata resta 1d6
    assert r.json()["damage_dice"] == "1d6"


@pytest.mark.caccia(id="CB-3162", fonte="2014 · Equipaggiamento · Armi (Rete: nessun danno) · pag. 149; Armi Speciali · Rete · pag. 148",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Armi / Weapons (pag. 149)",
                           "carta:2014/equipment.md#Armi Speciali / Special Weapons (pag. 148)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.xfail(strict=True, reason="CB-3162: difforme dal manuale, confermato")
async def test_la_rete_del_catalogo_non_infligge_danni(client, dadi):
    cid = await _pg(client, dexterity=16)
    # i metadati che il catalogo SRD dà alla Rete: nessun dado di danno
    rete = await _oggetto(client, cid, "Rete", "weapon", weight=3, item_metadata={
        "srd_index": "net", "weapon_type": "ranged", "weapon_category": "martial", "damage_type": "dmg_slashing",
        "properties": ["prop_special", "prop_thrown"]})
    dadi(4)
    r = await client.post(f"/characters/{cid}/items/{rete}/attack", json={"die": 15})
    assert r.status_code == 200, r.text
    assert r.json()["damage_total"] == 0


@pytest.mark.caccia(id="CB-3163", fonte="2014 · Equipaggiamento · Proprietà delle armi: Due Mani (va impugnata a due mani per attaccare) · pag. 147",
                    zona="regola:2014/equipaggiamento", voce="interazione",
                    copre=["carta:2014/equipment.md#Proprieta delle Armi / Weapon Properties (pagg. 146-147)",
                           "carta:2014/equipment.md#Regole",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.xfail(strict=True, reason="CB-3163: difforme dal manuale, confermato")
async def test_non_si_attacca_con_un_arma_a_due_mani_imbracciando_lo_scudo(client, dadi):
    cid = await _pg(client, strength=16)
    scudo = await _oggetto(client, cid, "Scudo", "shield", item_metadata={"ac_bonus": 2})
    assert (await _indossa(client, cid, scudo, "off_hand")).status_code == 200
    spadone = await _oggetto(client, cid, "Spadone", "weapon", item_metadata={
        "damage_dice": "2d6", "weapon_type": "melee", "weapon_category": "martial",
        "properties": ["prop_heavy", "prop_two_handed"]})
    dadi(3, 3)
    r = await client.post(f"/characters/{cid}/items/{spadone}/attack", json={"die": 15})
    # stessa regola dell'impugnatura a due mani di un'arma versatile: la mano secondaria è occupata
    assert r.status_code == 422, r.text


@pytest.mark.caccia(id="CB-3164", fonte="2014 · Equipaggiamento · Proprietà delle armi: Due Mani · pag. 147",
                    zona="regola:2014/equipaggiamento", voce="interazione",
                    copre=["carta:2014/equipment.md#Proprieta delle Armi / Weapon Properties (pagg. 146-147)",
                           "PATCH /characters/{char_id}/items/{item_id}"])
async def test_un_arma_a_due_mani_nella_mano_secondaria_non_convive_con_un_arma_nella_principale(client):
    cid = await _pg(client, strength=16)
    spada = await _oggetto(client, cid, "Spada lunga", "weapon", item_metadata={
        "damage_dice": "1d8", "weapon_type": "melee", "weapon_category": "martial", "properties": ["prop_versatile"],
        "versatile_dice": "1d10"})
    assert (await _indossa(client, cid, spada, "main_hand")).status_code == 200
    spadone = await _oggetto(client, cid, "Spadone", "weapon", item_metadata={
        "damage_dice": "2d6", "weapon_type": "melee", "weapon_category": "martial",
        "properties": ["prop_heavy", "prop_two_handed"]})
    r = await _indossa(client, cid, spadone, "off_hand")
    # come nella mano principale: un'arma a due mani vuole libera l'altra mano
    assert r.status_code == 422, r.text


@pytest.mark.caccia(id="CB-3165", fonte="2014 · Equipaggiamento · Armature e Scudi: lo scudo imbracciato aggiunge il suo bonus alla CA · pag. 144-145",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Regole",
                           "carta:2014/equipment.md#Armature / Armor (pag. 145)",
                           "PATCH /characters/{char_id}/items/{item_id}", "GET /characters/{char_id}"])
@pytest.mark.xfail(strict=True, reason="CB-3165: difforme dal manuale, confermato")
async def test_correggere_il_bonus_dello_scudo_imbracciato_cambia_la_ca(client):
    cid = await _pg(client, "fighter", 1, dexterity=10)
    scudo = await _oggetto(client, cid, "Scudo", "shield", item_metadata={"ac_bonus": 2})
    r = await _indossa(client, cid, scudo, "off_hand")
    assert r.status_code == 200 and r.json()["ac"] == 12, r.text
    r = await client.patch(f"/characters/{cid}/items/{scudo}", json={"item_metadata": {"ac_bonus": 3}})
    assert r.status_code == 200, r.text
    # lo scudo resta imbracciato con il nuovo bonus: la CA deve seguirlo, senza toglierlo e rimetterlo
    assert (await _scheda(client, cid))["ac"] == 13


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

_ARMATURE_2014 = {  # indice SRD -> (tipo, CA base, Forza richiesta, svantaggio a Furtività, peso in lb)
    "padded-armor": ("light", 11, 0, True, 8), "leather-armor": ("light", 11, 0, False, 10),
    "studded-leather-armor": ("light", 12, 0, False, 13), "hide-armor": ("medium", 12, 0, False, 12),
    "chain-shirt": ("medium", 13, 0, False, 20), "scale-mail": ("medium", 14, 0, True, 45),
    "breastplate": ("medium", 14, 0, False, 20), "half-plate-armor": ("medium", 15, 0, True, 40),
    "ring-mail": ("heavy", 14, 0, True, 40), "chain-mail": ("heavy", 16, 13, True, 55),
    "splint-armor": ("heavy", 17, 15, True, 60), "plate-armor": ("heavy", 18, 15, True, 65),
    "shield": ("shield", 2, 0, False, 6),
}


@pytest.mark.caccia(id="CB-3167", fonte="2014 · Equipaggiamento · Armature (tabella: CA, Forza, Furtività, peso) · pag. 145",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Armature / Armor (pag. 145)"])
@pytest.mark.parametrize("indice", sorted(_ARMATURE_2014))
def test_tabella_delle_armature_del_catalogo_2014(indice):
    voce = next(e for e in json.loads(_SRD.read_text(encoding="utf-8"))["items"] if e["index"] == indice)
    atteso = _ARMATURE_2014[indice]
    assert (voce["armor_type"], voce["ac_value"], voce["strength_req"], voce["stealth_disadvantage"], voce["weight_lb"]) == atteso


@pytest.mark.caccia(id="CB-3168", fonte="2014 · Equipaggiamento · Armature: leggera + Des, media + Des massimo 2, pesante senza Des (anche se negativa) · pag. 144",
                    zona="regola:2014/equipaggiamento", voce="limiti",
                    copre=["carta:2014/equipment.md#Regole", "carta:2014/equipment.md#Armature / Armor (pag. 145)",
                           "PATCH /characters/{char_id}/items/{item_id}"])
@pytest.mark.parametrize("tipo, base, destrezza, ca", [
    ("light", 11, 18, 15), ("light", 11, 8, 10),
    ("medium", 15, 18, 17), ("medium", 15, 8, 14),
    ("heavy", 18, 18, 18), ("heavy", 18, 8, 18),
])
async def test_ca_dell_armatura_secondo_la_categoria_e_la_destrezza(client, tipo, base, destrezza, ca):
    cid = await _pg(client, "fighter", 1, dexterity=destrezza, strength=16)
    armatura = await _oggetto(client, cid, "Armatura", "armor", item_metadata={"armor_type": tipo, "ac_value": base})
    r = await _indossa(client, cid, armatura, "body")
    assert r.status_code == 200, r.text
    assert r.json()["ac"] == ca


@pytest.mark.caccia(id="CB-3169", fonte="2014 · Equipaggiamento · Armature: Forza inferiore a quella richiesta, velocità -3 m · pag. 144",
                    zona="regola:2014/equipaggiamento", voce="limiti",
                    copre=["carta:2014/equipment.md#Regole", "carta:2014/equipment.md#Armature / Armor (pag. 145)",
                           "PATCH /characters/{char_id}/items/{item_id}", "GET /characters/{char_id}"])
@pytest.mark.parametrize("forza, velocita", [(12, 20), (13, 30)])
async def test_cotta_di_maglia_e_forza_richiesta(client, forza, velocita):
    cid = await _pg(client, "fighter", 1, strength=forza)
    cotta = await _oggetto(client, cid, "Cotta di maglia", "armor", item_metadata={
        "armor_type": "heavy", "ac_value": 16, "strength_req": 13, "stealth_disadvantage": True})
    assert (await _indossa(client, cid, cotta, "body")).status_code == 200
    assert (await _scheda(client, cid))["computed"]["speed"] == velocita


@pytest.mark.caccia(id="CB-3170", fonte="2014 · Equipaggiamento · Armature: svantaggio a Furtività; senza competenza svantaggio ai tiri di Forza e Destrezza · pag. 144",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Regole", "PATCH /characters/{char_id}/items/{item_id}",
                           "POST /characters/{char_id}/skills/{skill_name}/roll",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
async def test_armatura_rumorosa_e_armatura_senza_competenza(client):
    guerriero = await _pg(client, "fighter", 1)
    imbottita = await _oggetto(client, guerriero, "Imbottita", "armor", item_metadata={
        "armor_type": "light", "ac_value": 11, "stealth_disadvantage": True})
    assert (await _indossa(client, guerriero, imbottita, "body")).status_code == 200
    r = await client.post(f"/characters/{guerriero}/skills/stealth/roll", json={"dice": [15, 4]})
    assert r.json()["mode_applied"] == "disadvantage"
    r = await client.post(f"/characters/{guerriero}/saving_throws/dexterity/roll", json={"die": 15})
    assert r.json()["mode_applied"] == "normal"  # competente nelle armature leggere: nessuna penalità ai TS

    mago = await _pg(client, "wizard", 1)
    cotta = await _oggetto(client, mago, "Cotta di maglia", "armor", item_metadata={"armor_type": "heavy", "ac_value": 16})
    assert (await _indossa(client, mago, cotta, "body")).status_code == 200
    r = await client.post(f"/characters/{mago}/saving_throws/dexterity/roll", json={"dice": [15, 4]})
    assert r.json()["mode_applied"] == "disadvantage"
    r = await client.post(f"/characters/{mago}/saving_throws/wisdom/roll", json={"die": 15})
    assert r.json()["mode_applied"] == "normal"


@pytest.mark.caccia(id="CB-3171", fonte="2014 · Equipaggiamento · Ricarica: una sola munizione per azione a prescindere dagli attacchi · pag. 147",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Proprieta delle Armi / Weapon Properties (pagg. 146-147)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_ricarica_un_solo_colpo_per_azione_anche_con_attacco_extra(client, dadi):
    cid = await _pg(client, "fighter", 5, dexterity=16)
    balestra = await _oggetto(client, cid, "Balestra leggera", "weapon", item_metadata={
        "damage_dice": "1d8", "weapon_type": "ranged", "weapon_category": "simple",
        "properties": ["prop_ammunition", "prop_loading", "prop_two_handed"]})
    await _oggetto(client, cid, "Quadrelli", "ammunition", quantity=10)
    dadi(4)
    assert (await client.post(f"/characters/{cid}/items/{balestra}/attack", json={"die": 15})).status_code == 200
    r = await client.post(f"/characters/{cid}/items/{balestra}/attack", json={"die": 15})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "attack_limit"


@pytest.mark.caccia(id="CB-3172", fonte="2014 · Equipaggiamento · Armature e Scudi: lo scudo senza competenza dà svantaggio ma tiene il +2 · pag. 144; 2024 · Armature · Scudo: senza addestramento solo niente CA · pag. 219",
                    zona="regola:2014/equipaggiamento", voce="edizioni",
                    copre=["carta:2014/equipment.md#Regole", "carta:2024/equipment.md#Armature / Armor (pag. 219)",
                           "PATCH /characters/{char_id}/items/{item_id}", "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("edizione, ca, modo", [("2014", 12, "disadvantage"), ("2024", 10, "normal")])
async def test_scudo_senza_competenza_per_edizione(client, edizione, ca, modo):
    r = await client.post("/characters", json={"name": "Mago", "rules_edition": edizione,
                                                "initial_class": {"class_name": "wizard", "level": 1}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    scudo = await _oggetto(client, cid, "Scudo", "shield", item_metadata={"ac_bonus": 2})
    r = await _indossa(client, cid, scudo, "off_hand")
    assert r.status_code == 200 and r.json()["ac"] == ca, r.text
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"dice": [15, 4]})
    assert r.json()["mode_applied"] == modo


@pytest.mark.caccia(id="CB-3173", fonte="2014 · Equipaggiamento · Valuta, Valori di Scambio (1 mp = 10 mo, 1 mo = 2 me, 1 me = 5 ma) · pag. 143",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Valuta / Currency (pag. 143)",
                           "carta:2014/equipment.md#Valori di Scambio / Standard Exchange Rates (pag. 143)",
                           "POST /characters/{char_id}/currency/convert"])
@pytest.mark.parametrize("da, a, ottenuto", [("platinum", "gold", 10), ("gold", "electrum", 2), ("electrum", "silver", 5),
                                             ("silver", "copper", 10)])
async def test_cambio_delle_monete(client, da, a, ottenuto):
    cid = await _pg(client)
    r = await client.patch(f"/characters/{cid}/currency", json={da: 1})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/currency/convert", json={"source": da, "target": a, "amount": 1})
    assert r.status_code == 200, r.text
    assert r.json()[da] == 0 and r.json()[a] == ottenuto


_ARMI_2014 = {  # indice SRD -> (dadi, tipo di danno, proprietà, dado versatile, peso in lb)
    "handaxe": ("1d6", "slashing", ("light", "thrown"), None, 2),
    "quarterstaff": ("1d6", "bludgeoning", ("versatile",), "1d8", 4),
    "sickle": ("1d4", "slashing", ("light",), None, 2),
    "javelin": ("1d6", "piercing", ("thrown",), None, 2),
    "spear": ("1d6", "piercing", ("thrown", "versatile"), "1d8", 3),
    "light-hammer": ("1d4", "bludgeoning", ("light", "thrown"), None, 2),
    "mace": ("1d6", "bludgeoning", (), None, 4),
    "dagger": ("1d4", "piercing", ("finesse", "light", "thrown"), None, 1),
    "club": ("1d4", "bludgeoning", ("light",), None, 2),
    "greatclub": ("1d8", "bludgeoning", ("two_handed",), None, 10),
    "shortbow": ("1d6", "piercing", ("ammunition", "two_handed"), None, 2),
    "crossbow-light": ("1d8", "piercing", ("ammunition", "loading", "two_handed"), None, 5),
    "dart": ("1d4", "piercing", ("finesse", "thrown"), None, 0.25),
    "sling": ("1d4", "bludgeoning", ("ammunition",), None, 0),
    "halberd": ("1d10", "slashing", ("heavy", "reach", "two_handed"), None, 6),
    "greataxe": ("1d12", "slashing", ("heavy", "two_handed"), None, 7),
    "battleaxe": ("1d8", "slashing", ("versatile",), "1d10", 4),
    "glaive": ("1d10", "slashing", ("heavy", "reach", "two_handed"), None, 6),
    "whip": ("1d4", "slashing", ("finesse", "reach"), None, 3),
    "lance": ("1d12", "piercing", ("reach", "special"), None, 6),
    "maul": ("2d6", "bludgeoning", ("heavy", "two_handed"), None, 10),
    "warhammer": ("1d8", "bludgeoning", ("versatile",), "1d10", 2),
    "flail": ("1d8", "bludgeoning", (), None, 2),
    "morningstar": ("1d8", "piercing", (), None, 4),
    "pike": ("1d10", "piercing", ("heavy", "reach", "two_handed"), None, 18),
    "war-pick": ("1d8", "piercing", (), None, 2),
    "scimitar": ("1d6", "slashing", ("finesse", "light"), None, 3),
    "shortsword": ("1d6", "piercing", ("finesse", "light"), None, 2),
    "longsword": ("1d8", "slashing", ("versatile",), "1d10", 3),
    "greatsword": ("2d6", "slashing", ("heavy", "two_handed"), None, 6),
    "rapier": ("1d8", "piercing", ("finesse",), None, 2),
    "trident": ("1d6", "piercing", ("thrown", "versatile"), "1d8", 4),
    "longbow": ("1d8", "piercing", ("ammunition", "heavy", "two_handed"), None, 2),
    "crossbow-hand": ("1d6", "piercing", ("ammunition", "light", "loading"), None, 3),
    "crossbow-heavy": ("1d10", "piercing", ("ammunition", "heavy", "loading", "two_handed"), None, 18),
    "blowgun": ("1", "piercing", ("ammunition", "loading"), None, 1),
    "net": (None, None, ("special", "thrown"), None, 3),
}


@pytest.mark.caccia(id="CB-3174", fonte="2014 · Equipaggiamento · Armi (tabella: danni, tipo, proprietà, peso) · pag. 149",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Armi / Weapons (pag. 149)",
                           "carta:2014/equipment.md#Proprieta delle Armi / Weapon Properties (pagg. 146-147)"])
@pytest.mark.parametrize("indice", sorted(_ARMI_2014))
def test_tabella_delle_armi_del_catalogo_2014(indice):
    voce = next(e for e in json.loads(_SRD.read_text(encoding="utf-8"))["items"] if e["index"] == indice)
    proprieta = tuple(sorted(p.removeprefix("prop_") for p in voce["properties"]))
    assert (voce["damage_dice"], voce["damage_type"], proprieta, voce["versatile_dice"], voce["weight_lb"]) == _ARMI_2014[indice]
