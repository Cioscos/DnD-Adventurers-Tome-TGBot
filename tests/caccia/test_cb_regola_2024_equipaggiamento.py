"""Controlli della zona regola:2024/equipaggiamento."""
import json
import re
from pathlib import Path

import pytest

from core.data.tools import TOOLS
from core.rules.weapons import WEAPONS

_SRD_2024 = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "equipment-2024.json"
_KIND_FE = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "weaponMastery.ts"
_CHIAVE_CORE = {"crossbow-light": "light_crossbow", "crossbow-hand": "hand_crossbow", "crossbow-heavy": "heavy_crossbow"}


def _catalogo() -> dict[str, dict]:
    return {e["index"]: e for e in json.loads(_SRD_2024.read_text(encoding="utf-8"))["items"]}


async def _pg(client, classe="fighter", edizione="2024", **punteggi) -> dict:
    corpo = {"name": "Prova", "rules_edition": edizione, "initial_class": {"class_name": classe, "level": 1}}
    if punteggi:
        corpo["ability_scores"] = punteggi
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


async def _oggetto(client, cid, nome, tipo, **extra) -> int:
    r = await client.post(f"/characters/{cid}/items", json={"name": nome, "item_type": tipo, **extra})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

_PESI_ARMI_2024 = {  # indice del catalogo 2024 -> peso in lb della tabella delle armi
    "club": 2, "dagger": 1, "greatclub": 10, "handaxe": 2, "javelin": 2, "light-hammer": 2, "mace": 4,
    "quarterstaff": 4, "sickle": 2, "spear": 3, "dart": 0.25, "crossbow-light": 5, "shortbow": 2, "sling": 0,
    "battleaxe": 4, "flail": 2, "glaive": 6, "greataxe": 7, "greatsword": 6, "halberd": 6, "lance": 6, "longsword": 3,
    "maul": 10, "morningstar": 4, "pike": 18, "rapier": 2, "scimitar": 3, "shortsword": 2, "trident": 4,
    "warhammer": 5, "war-pick": 2, "whip": 3, "blowgun": 1, "crossbow-hand": 3, "crossbow-heavy": 18, "longbow": 2,
    "musket": 10, "pistol": 3,
}


@pytest.mark.caccia(id="CB-3611", fonte="2024 · Equipaggiamento · Tabella armi (colonna Peso) · pag. 215", zona="regola:2024/equipaggiamento",
                    voce="regola", copre=["carta:2024/equipment.md#Tabella armi / Weapons (pag. 215)"])
@pytest.mark.parametrize("indice", [pytest.param(i, marks=pytest.mark.xfail(strict=True, reason="CB-3611: difforme dal manuale, confermato")) if i == "warhammer" else i for i in sorted(_PESI_ARMI_2024)])
def test_peso_delle_armi_del_catalogo_2024(indice):
    # il Martello da guerra pesa 5 lb nel 2024 (2 lb era il peso del 2014)
    assert _catalogo()[indice]["weight_lb"] == _PESI_ARMI_2024[indice]


@pytest.mark.caccia(id="CB-3612", fonte="2024 · Equipaggiamento · Tabella costi e pesi pag. 223 (Kit, Faretra, Veste, Munizioni) e Strumenti pag. 220-221",
                    zona="regola:2024/equipaggiamento", voce="regola",
                    copre=["carta:2024/equipment.md#Tabella costi e pesi / Adventuring Gear (pag. 223)",
                           "carta:2024/equipment.md#Equipaggiamento da avventura / Adventuring Gear (pag. 222-229)",
                           "carta:2024/equipment.md#Altri strumenti / Other Tools (pag. 221)", "POST /characters"])
@pytest.mark.parametrize("classe, nomi, peso", [
    # i pacchetti restano da pesare; gli oggetti singoli pesano già come la tabella (pag. 221-223)
    pytest.param(*caso, marks=pytest.mark.xfail(strict=True, reason="CB-3612: difforme dal manuale, confermato"))
    if caso[1][0].startswith("Dotazione") else caso for caso in [
        ("barbarian", ("Dotazione da esploratore", "Explorer's pack"), 55),
        ("fighter", ("Dotazione da avventuriero", "Dungeoneer's pack"), 55),
        ("rogue", ("Dotazione da scassinatore", "Burglar's pack"), 42),
        ("rogue", ("Arnesi da scasso", "Thieves' tools"), 1),
        ("cleric", ("Dotazione da sacerdote", "Priest's pack"), 29),
        ("wizard", ("Dotazione da studioso", "Scholar's pack"), 22),
        ("wizard", ("Veste", "Robe"), 4),
        ("bard", ("Dotazione da intrattenitore", "Entertainer's pack"), 58.5),
        ("druid", ("Kit da erborista", "Herbalism kit"), 3),
        ("ranger", ("Faretra", "Quiver"), 1),
        ("ranger", ("Frecce", "Arrows"), 1),  # 20 frecce pesano 1 lb in tutto
    ]])
async def test_l_equipaggiamento_di_partenza_2024_pesa_come_la_tabella(client, classe, nomi, peso):
    r = await client.post("/characters", json={"name": "Prova", "rules_edition": "2024", "initial_class": {"class_name": classe},
                                               "starting_equipment": [0]})
    assert r.status_code == 201, r.text
    oggetto = next(i for i in r.json()["items"] if i["name"] in nomi)
    assert oggetto["weight"] * oggetto["quantity"] == pytest.approx(peso)


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

_ARMI_2024 = {  # indice -> (dadi, tipo di danno, proprietà, dado versatile, gittata normale in ft, a distanza, categoria, maestria)
    "club": ("1d4", "bludgeoning", ("light",), None, None, False, "simple", "slow"),
    "dagger": ("1d4", "piercing", ("finesse", "light", "thrown"), None, 20, False, "simple", "nick"),
    "greatclub": ("1d8", "bludgeoning", ("two_handed",), None, None, False, "simple", "push"),
    "handaxe": ("1d6", "slashing", ("light", "thrown"), None, 20, False, "simple", "vex"),
    "javelin": ("1d6", "piercing", ("thrown",), None, 30, False, "simple", "slow"),
    "light-hammer": ("1d4", "bludgeoning", ("light", "thrown"), None, 20, False, "simple", "nick"),
    "mace": ("1d6", "bludgeoning", (), None, None, False, "simple", "sap"),
    "quarterstaff": ("1d6", "bludgeoning", ("versatile",), "1d8", None, False, "simple", "topple"),
    "sickle": ("1d4", "slashing", ("light",), None, None, False, "simple", "nick"),
    "spear": ("1d6", "piercing", ("thrown", "versatile"), "1d8", 20, False, "simple", "sap"),
    "dart": ("1d4", "piercing", ("finesse", "thrown"), None, 20, True, "simple", "vex"),
    "crossbow-light": ("1d8", "piercing", ("ammunition", "loading", "two_handed"), None, 80, True, "simple", "slow"),
    "shortbow": ("1d6", "piercing", ("ammunition", "two_handed"), None, 80, True, "simple", "vex"),
    "sling": ("1d4", "bludgeoning", ("ammunition",), None, 30, True, "simple", "slow"),
    "battleaxe": ("1d8", "slashing", ("versatile",), "1d10", None, False, "martial", "topple"),
    "flail": ("1d8", "bludgeoning", (), None, None, False, "martial", "sap"),
    "glaive": ("1d10", "slashing", ("heavy", "reach", "two_handed"), None, None, False, "martial", "graze"),
    "greataxe": ("1d12", "slashing", ("heavy", "two_handed"), None, None, False, "martial", "cleave"),
    "greatsword": ("2d6", "slashing", ("heavy", "two_handed"), None, None, False, "martial", "graze"),
    "halberd": ("1d10", "slashing", ("heavy", "reach", "two_handed"), None, None, False, "martial", "cleave"),
    "lance": ("1d10", "piercing", ("heavy", "reach", "two_handed"), None, None, False, "martial", "topple"),
    "longsword": ("1d8", "slashing", ("versatile",), "1d10", None, False, "martial", "sap"),
    "maul": ("2d6", "bludgeoning", ("heavy", "two_handed"), None, None, False, "martial", "topple"),
    "morningstar": ("1d8", "piercing", (), None, None, False, "martial", "sap"),
    "pike": ("1d10", "piercing", ("heavy", "reach", "two_handed"), None, None, False, "martial", "push"),
    "rapier": ("1d8", "piercing", ("finesse",), None, None, False, "martial", "vex"),
    "scimitar": ("1d6", "slashing", ("finesse", "light"), None, None, False, "martial", "nick"),
    "shortsword": ("1d6", "piercing", ("finesse", "light"), None, None, False, "martial", "vex"),
    "trident": ("1d8", "piercing", ("thrown", "versatile"), "1d10", 20, False, "martial", "topple"),
    "warhammer": ("1d8", "bludgeoning", ("versatile",), "1d10", None, False, "martial", "push"),
    "war-pick": ("1d8", "piercing", ("versatile",), "1d10", None, False, "martial", "sap"),
    "whip": ("1d4", "slashing", ("finesse", "reach"), None, None, False, "martial", "slow"),
    "blowgun": ("1", "piercing", ("ammunition", "loading"), None, 25, True, "martial", "vex"),
    "crossbow-hand": ("1d6", "piercing", ("ammunition", "light", "loading"), None, 30, True, "martial", "vex"),
    "crossbow-heavy": ("1d10", "piercing", ("ammunition", "heavy", "loading", "two_handed"), None, 100, True, "martial", "push"),
    "longbow": ("1d8", "piercing", ("ammunition", "heavy", "two_handed"), None, 150, True, "martial", "slow"),
    "musket": ("1d12", "piercing", ("ammunition", "loading", "two_handed"), None, 40, True, "martial", "slow"),
    "pistol": ("1d10", "piercing", ("ammunition", "loading"), None, 30, True, "martial", "vex"),
}


@pytest.mark.caccia(id="CB-3613", fonte="2024 · Equipaggiamento · Tabella armi (danni, proprietà, maestria) pag. 215; Proprietà pag. 213-214; Proprietà di maestria pag. 214",
                    zona="regola:2024/equipaggiamento", voce="regola",
                    copre=["carta:2024/equipment.md#Tabella armi / Weapons (pag. 215)", "carta:2024/equipment.md#Voci generali (pag. 213)",
                           "carta:2024/equipment.md#Proprietà / Properties (pag. 213-214)",
                           "carta:2024/equipment.md#Proprietà di maestria / Mastery Properties (pag. 214)"])
@pytest.mark.parametrize("indice", sorted(_ARMI_2024))
def test_tabella_delle_armi_2024_catalogo_e_maestria(indice):
    dadi, tipo, proprieta, versatile, gittata, distanza, categoria, maestria = _ARMI_2024[indice]
    voce = _catalogo()[indice]
    lette = tuple(sorted(p.removeprefix("prop_") for p in voce["properties"] if p != "prop_special"))  # «Speciale» è solo un'etichetta
    portata = voce["thrown_range_ft"][0] if voce.get("thrown_range_ft") else voce["range_ft"] if voce["weapon_range"] == "ranged" else None
    assert (voce["damage_dice"], voce["damage_type"], lette, voce["versatile_dice"], portata, voce["weapon_range"] == "ranged",
            voce["weapon_category"]) == (dadi, tipo, proprieta, versatile, gittata, distanza, categoria)
    arma = WEAPONS[_CHIAVE_CORE.get(indice, indice.replace("-", "_"))]
    assert (arma.category, arma.mastery, arma.ranged) == (categoria, maestria, distanza)
    specchio = dict(re.findall(r"key: '(\w+)'.*?mastery: '(\w+)'", _KIND_FE.read_text(encoding="utf-8")))
    assert specchio[_CHIAVE_CORE.get(indice, indice.replace("-", "_"))].lower() == maestria


_ARMATURE_2024 = {  # indice -> (tipo, CA base, Destrezza, Forza richiesta, svantaggio a Furtività, peso in lb)
    "padded-armor": ("light", 11, True, 0, True, 8), "leather-armor": ("light", 11, True, 0, False, 10),
    "studded-leather-armor": ("light", 12, True, 0, False, 13), "hide-armor": ("medium", 12, True, 0, False, 12),
    "chain-shirt": ("medium", 13, True, 0, False, 20), "scale-mail": ("medium", 14, True, 0, True, 45),
    "breastplate": ("medium", 14, True, 0, False, 20), "half-plate-armor": ("medium", 15, True, 0, True, 40),
    "ring-mail": ("heavy", 14, False, 0, True, 40), "chain-mail": ("heavy", 16, False, 13, True, 55),
    "splint-armor": ("heavy", 17, False, 15, True, 60), "plate-armor": ("heavy", 18, False, 15, True, 65),
    "shield": ("shield", 2, False, 0, False, 6),
}


@pytest.mark.caccia(id="CB-3614", fonte="2024 · Equipaggiamento · Tabella armature (CA, Forza, Furtività, peso) · pag. 219", zona="regola:2024/equipaggiamento",
                    voce="regola", copre=["carta:2024/equipment.md#Tabella armature / Armor (pag. 219)"])
@pytest.mark.parametrize("indice", sorted(_ARMATURE_2024))
def test_tabella_delle_armature_del_catalogo_2024(indice):
    voce = _catalogo()[indice]
    assert (voce["armor_type"], voce["ac_value"], voce["dex_bonus"], voce["strength_req"], voce["stealth_disadvantage"],
            voce["weight_lb"]) == _ARMATURE_2024[indice]


@pytest.mark.caccia(id="CB-3615", fonte="2024 · Equipaggiamento · Armature: CA della tabella (leggera + Des, media + Des max 2, pesante senza Des) · pag. 219",
                    zona="regola:2024/equipaggiamento", voce="limiti",
                    copre=["carta:2024/equipment.md#Armature / Armor (pag. 219)", "carta:2024/equipment.md#Tabella armature / Armor (pag. 219)",
                           "carta:2024/equipment.md#Regole delle armature (pag. 219)", "PATCH /characters/{char_id}/items/{item_id}"])
@pytest.mark.parametrize("indice, destrezza, ca", [
    ("studded-leather-armor", 18, 16), ("studded-leather-armor", 8, 11),
    ("breastplate", 18, 16), ("breastplate", 8, 13), ("hide-armor", 14, 14),
    ("plate-armor", 18, 18), ("plate-armor", 8, 18),
])
async def test_ca_2024_con_le_armature_del_catalogo(client, indice, destrezza, ca):
    cid = (await _pg(client, "fighter", dexterity=destrezza, strength=16))["id"]
    voce = _catalogo()[indice]
    meta = {"srd_index": indice, "armor_type": voce["armor_type"], "ac_value": voce["ac_value"],
            "stealth_disadvantage": voce["stealth_disadvantage"], "strength_req": voce["strength_req"]}  # come lo aggiunge l'inventario
    armatura = await _oggetto(client, cid, voce["name"]["it"], "armor", weight=voce["weight_lb"], item_metadata=meta)
    r = await client.patch(f"/characters/{cid}/items/{armatura}", json={"is_equipped": True, "equipment_slot": "body"})
    assert r.status_code == 200, r.text
    assert r.json()["ac"] == ca


@pytest.mark.caccia(id="CB-3616", fonte="2024 · Equipaggiamento · Monete: 50 monete pesano 1 lb · pag. 213", zona="regola:2024/equipaggiamento",
                    voce="interazione", copre=["carta:2024/equipment.md#Monete / Coins (pag. 213)", "PATCH /characters/{char_id}",
                                               "PATCH /characters/{char_id}/currency", "POST /characters/{char_id}/currency/move",
                                               "GET /characters/{char_id}"])
@pytest.mark.parametrize("nello_zaino", [False, True])
async def test_cinquanta_monete_pesano_una_libbra_anche_nello_zaino(client, nello_zaino):
    cid = (await _pg(client))["id"]
    r = await client.patch(f"/characters/{cid}", json={"settings": {"coin_weight": True}})
    assert r.status_code == 200, r.text
    zaino = await _oggetto(client, cid, "Zaino", "generic", weight=0,
                           item_metadata={"container": {"capacity_lb": 30, "counts_weight": True, "quick_access": False}})
    assert (await client.patch(f"/characters/{cid}/currency", json={"gold": 100})).status_code == 200
    if nello_zaino:
        r = await client.post(f"/characters/{cid}/currency/move", json={"coin": "gold", "amount": 100, "from_container_id": None,
                                                                         "to_container_id": zaino})
        assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["encumbrance_total"] == pytest.approx(2)


@pytest.mark.caccia(id="CB-3617", fonte="2024 · Equipaggiamento · Armature: senza addestramento niente incantesimi; Scudo: senza addestramento solo niente CA · pag. 219; 2014 · Armature e Scudi · pag. 144",
                    zona="regola:2024/equipaggiamento", voce="edizioni",
                    copre=["carta:2024/equipment.md#Regole delle armature (pag. 219)", "carta:2014/equipment.md#Regole",
                           "PATCH /characters/{char_id}/items/{item_id}", "POST /characters/{char_id}/spells",
                           "GET /characters/{char_id}/spells/{spell_id}/cast-check"])
@pytest.mark.parametrize("edizione, bloccato", [("2024", False), ("2014", True)])
async def test_lo_scudo_senza_addestramento_blocca_gli_incantesimi_solo_nel_2014(client, edizione, bloccato):
    pg = await _pg(client, "wizard", edizione)
    cid, mago = pg["id"], pg["classes"][0]["id"]
    scudo = await _oggetto(client, cid, "Scudo", "shield", item_metadata={"ac_bonus": 2})
    assert (await client.patch(f"/characters/{cid}/items/{scudo}", json={"is_equipped": True, "equipment_slot": "off_hand"})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo incantato", "level": 1, "components": "V, S", "class_id": mago})
    assert r.status_code == 201, r.text
    avvisi = (await client.get(f"/characters/{cid}/spells/{r.json()['id']}/cast-check")).json()
    assert ("armor" in avvisi) is bloccato


_STRUMENTI_2024 = {  # chiave del catalogo -> caratteristica della tabella degli strumenti 2024
    "alchemists_supplies": "intelligence", "brewers_supplies": "intelligence", "calligraphers_supplies": "dexterity",
    "carpenters_tools": "strength", "cartographers_tools": "wisdom", "cobblers_tools": "dexterity", "cooks_utensils": "wisdom",
    "glassblowers_tools": "intelligence", "jewelers_tools": "intelligence", "leatherworkers_tools": "dexterity",
    "masons_tools": "strength", "painters_supplies": "wisdom", "potters_tools": "intelligence", "smiths_tools": "strength",
    "tinkers_tools": "dexterity", "weavers_tools": "dexterity", "woodcarvers_tools": "dexterity",
    "disguise_kit": "charisma", "forgery_kit": "dexterity", "dice_set": "wisdom", "dragonchess_set": "wisdom",
    "playing_card_set": "wisdom", "three_dragon_ante_set": "wisdom", "herbalism_kit": "intelligence", "bagpipes": "charisma",
    "drum": "charisma", "dulcimer": "charisma", "flute": "charisma", "horn": "charisma", "lute": "charisma", "lyre": "charisma",
    "pan_flute": "charisma", "shawm": "charisma", "viol": "charisma", "navigators_tools": "wisdom",
    "poisoners_kit": "intelligence", "thieves_tools": "dexterity",
}


@pytest.mark.caccia(id="CB-3618", fonte="2024 · Equipaggiamento · Strumenti (colonna Caratteristica) · pag. 220-221", zona="regola:2024/equipaggiamento",
                    voce="regola", copre=["carta:2024/equipment.md#Strumenti / Tools (pag. 220-221)",
                                          "carta:2024/equipment.md#Altri strumenti / Other Tools (pag. 221)"])
@pytest.mark.parametrize("chiave", sorted(_STRUMENTI_2024))
def test_caratteristica_degli_strumenti_2024(chiave):
    specchio = {t["key"]: t["ability"] for t in json.loads((_KIND_FE.parent / "tools.json").read_text(encoding="utf-8"))}
    assert (TOOLS[chiave].ability, specchio[chiave]) == (_STRUMENTI_2024[chiave], _STRUMENTI_2024[chiave])
