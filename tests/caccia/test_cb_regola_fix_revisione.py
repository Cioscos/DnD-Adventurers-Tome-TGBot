"""Controlli della revisione indipendente dei gruppi lancio-core, dati-incantesimi-fe, catalogo-incantesimi, scelte, stati-turno, oggetti e pf-personaggio."""
import json
from pathlib import Path

import pytest

from sqlalchemy import select

from core.db.models import Character, SpellSlot
from core.rules.catalog.granted_spells import granted_spell
from tests.caccia.test_cb_regola_2024_fighter import _guerriero, _manovre, _scheda, _usa
from tests.caccia.test_cb_regola_fix_lancio_core import _pg
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_bard import _roll_keys, _sword
from tests.integration.rules.test_2014_fighter_battle_master import _damage, _hit, _key
from tests.integration.rules.test_2014_sorcerer_origins import PRESENCE, _draconic
from tests.integration.rules.test_2014_warlock import _warlock
from tests.integration.rules.test_2014_warlock_patrons import FEY
from tests.integration.rules.test_2014_wizard_enchantment import GAZE, _effect, _wizard
from tests.integration.rules.test_2024_warlock_review2 import _chain
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _spell, _take
from tests.integration.rules.test_spell_effects_defenses import _cast, _sheet, _table

SRD = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd"
NANO = Path(__file__).resolve().parents[1] / "fixtures" / "ddb" / "cleric19.json"  # chierico 19, nano delle colline 2014, 212 PF
SCORES = {"strength": 14, "dexterity": 14, "constitution": 12, "intelligence": 14, "wisdom": 14, "charisma": 16}


def _voce(edizione: str, indice: str) -> dict:
    file = "spells.json" if edizione == "2014" else "spells-2024.json"
    return next(s for s in json.loads((SRD / file).read_text(encoding="utf-8"))["items"] if s["index"] == indice)


def _ha(scheda: dict, chiave: str) -> bool:
    return any(s["key"] == chiave for s in scheda["active_states"] or [])


async def _amuleto(client, cid) -> None:
    """+1 alla CD e all'attacco degli incantesimi."""
    r = await client.post(f"/characters/{cid}/items", json={"name": "Amuleto", "item_type": "accessory", "item_metadata": {
        "bonuses": [{"target": "spell_dc", "value": 1}, {"target": "spell_attack", "value": 1}]}})
    assert r.status_code == 201, r.text
    iid = max(i["id"] for i in r.json()["items"])
    assert (await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "neck"})).status_code == 200


async def _crea(client, edizione: str, *classi: tuple[str, int, str | None]) -> int:
    (nome, livello, sub), *altre = classi
    r = await client.post("/characters", json={"name": "PG", "rules_edition": edizione, "ability_scores": SCORES,
                                               "initial_class": {"class_name": nome, "level": livello, "subclass": sub}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome, livello, sub in altre:
        r = await client.post(f"/characters/{cid}/classes", json={"class_name": nome, "level": livello, "subclass": sub})
        assert r.status_code == 201, r.text
    return cid


async def _importa(client, monkeypatch, edizione: str, talento: str | None = None, forzati: int | None = None) -> dict:
    import api.routers.transfer as transfer
    dati = json.loads(NANO.read_text(encoding="utf-8"))
    if talento:
        dati["data"]["feats"] = [*(dati["data"].get("feats") or []), {"definition": {"name": talento, "description": ""}}]
        dati["data"]["modifiers"]["feat"].append({"type": "bonus", "subType": "hit-points-per-level", "value": 2})
    if forzati:
        dati["data"]["overrideHitPoints"] = forzati
    dati["data"]["removedHitPoints"] = 10

    async def finto(_id: int) -> dict:
        return dati
    monkeypatch.setattr(transfer, "fetch_ddb", finto)
    r = await client.post("/characters/import/ddb", json={"url": "https://www.dndbeyond.com/characters/1", "rules_edition": edizione})
    assert r.status_code == 201, r.text
    return r.json()["character"]


@pytest.mark.caccia(id="CB-4761", fonte="2014 · Incantesimi · Previsione · pag. 264; 2024 · Incantesimi · Preveggenza · pag. 276",
                    zona="regola:2014/incantesimi-M-R", voce="ripetizione",
                    copre=["carta:2014/spells.md#Previsione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_previsione_rilanciata_su_un_png_finisce_sul_bersaglio_di_prima(client, test_session_factory, edizione):
    eroe, mago, previsione = await _table(client, test_session_factory, "Previsione", "foresight", 9, hero_edition=edizione, caster_edition=edizione)
    await _cast(client, mago, previsione, [eroe], level=9)
    assert _ha(await _sheet(client, eroe), "spell:foresight")
    async with test_session_factory() as s:  # un altro slot di 9° senza le 8 ore di un riposo, che la farebbero finire da sé
        for slot in (await s.execute(select(SpellSlot).where(SpellSlot.character_id == mago))).scalars():
            slot.used = 0
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/characters/{mago}/spells/{previsione}/use", json={"slot_level": 9, "targets": [], "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    # «Termina se lanciato di nuovo»: anche se il nuovo bersaglio non ha una scheda
    assert not _ha(await _sheet(client, eroe), "spell:foresight")
    assert not _ha(await _sheet(client, mago, GM_ID), "spell_cast:foresight")


@pytest.mark.caccia(id="CB-4762", fonte="2014 · Incantesimi · Santuario · pag. 272", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Santuario", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_santuario_2014_finisce_quando_il_protetto_attacca(client, test_session_factory):
    eroe, chierico, santuario = await _table(client, test_session_factory, "Santuario", "sanctuary", 1, hero_edition="2014", caster_edition="2014")
    await _cast(client, chierico, santuario, [eroe], level=1)
    assert _ha(await _sheet(client, eroe), "spell:sanctuary")
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{eroe}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "damage_type": "slashing", "weapon_type": "melee"}})
    arma = max(i["id"] for i in r.json()["items"])
    r = await client.post(f"/characters/{eroe}/items/{arma}/attack", json={})
    assert r.status_code == 200, r.text
    # «Termina se la creatura protetta attacca o lancia un incantesimo su un nemico»
    assert not _ha(await _sheet(client, eroe), "spell:sanctuary")


@pytest.mark.caccia(id="CB-4763", fonte="2014 · Incantesimi · Rigenerazione · pag. 270", zona="regola:2014/incantesimi-M-R", voce="regola",
                    copre=["carta:2014/spells.md#Rigenerazione", "POST /characters/{char_id}/items/{item_id}/cast",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("come", ["oggetto", "riga_senza_indice", "riga_del_catalogo"])
async def test_rigenerazione_senza_tiro_di_cura_da_comunque_i_4d8_piu_15(client, dadi, come):
    cid, classe = await _pg(client, "cleric", 13)
    for op, valore in (("set_max", 100), ("set_current", 10)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": valore})).status_code == 200
    if come != "riga_del_catalogo":
        dadi(5, 5, 5, 5)
    if come == "oggetto":
        r = await client.post(f"/characters/{cid}/items", json={"name": "Verga", "item_type": "generic", "item_metadata": {
            "charges": {"max": 5, "current": 5}, "granted_spells": [{"name": "Rigenerazione", "srd_index": "regenerate", "level": 7, "charges_cost": 1}]}})
        assert r.status_code == 201, r.text
        r = await client.post(f"/characters/{cid}/items/{r.json()['items'][-1]['id']}/cast", json={"spell_index": 0})
    else:
        r = await client.post(f"/characters/{cid}/spells", json={"name": "Rigenerazione", "level": 7, "class_id": classe,
                                                                **({"srd_index": "regenerate"} if come == "riga_del_catalogo" else {})})
        assert r.status_code == 201, r.text
        r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_level": 7})
    assert r.status_code == 200, r.text
    # 4d8 + 15 subito; la riga del catalogo li tira dalla «Cura» dell'incantesimo, non anche dal lancio (CB-3363)
    attesi = 10 if come == "riga_del_catalogo" else 45
    assert (await client.get(f"/characters/{cid}")).json()["current_hit_points"] == attesi


@pytest.mark.caccia(id="CB-4764", fonte="2024 · Incantesimi · Ristorare Inferiore · pag. 291; Fame di Hadar · pag. 286; Presenza Regale di Yolande · pag. 343; "
                                        "Evoca Elementale · pag. 254; Muro di Pietra · pag. 339; Fonte di luce lunare · pag. 277; Parola del Potere · pag. 306; "
                                        "2014 · Muro di Pietra · pag. 254; Rampicante Afferrante · pag. 267",
                    zona="regola:2024/incantesimi-G-L", voce="edizioni",
                    copre=["carta:2024/spells.md#Ristorare Inferiore", "carta:2024/spells.md#Fame di Hadar", "carta:2014/spells.md#Muro di Pietra",
                           "GET /characters/{char_id}/spells"])
@pytest.mark.parametrize("edizione, chiave, campo, valore", [
    ("2024", "lesser-restoration", "casting_time", "1 azione bonus"), ("2014", "lesser-restoration", "casting_time", "1 azione"),
    ("2024", "hunger-of-hadar", "damage_dice", "2d6"), ("2024", "hunger-of-hadar", "higher_levels_dice", "1d6"),
    ("2024", "hunger-of-hadar", "damage_type", "cold"), ("2024", "hunger-of-hadar", "attack_save", "SAVE"),
    ("2024", "yolandes-regal-presence", "damage_dice", "4d6"), ("2024", "yolandes-regal-presence", "damage_type", "psychic"),
    ("2024", "conjure-elemental", "attack_save", "SAVE"), ("2024", "fount-of-moonlight", "attack_save", "SAVE"),
    ("2014", "wall-of-stone", "attack_save", "SAVE"), ("2024", "wall-of-stone", "attack_save", "SAVE"),
    ("2014", "grasping-vine", "attack_save", "SAVE"),
    ("2024", "power-word-heal", "components", "V"), ("2024", "power-word-kill", "components", "V"),
    ("2024", "power-word-kill", "damage_dice", "12d12"), ("2024", "power-word-kill", "damage_type", "psychic"),
])
def test_gli_incantesimi_concessi_hanno_i_dati_della_carta(edizione, chiave, campo, valore):
    assert getattr(granted_spell(chiave, edizione), campo) == valore


@pytest.mark.caccia(id="CB-4765", fonte="2014 · Incantesimi · Guarigione di Massa · pag. 240; Antipatia/Simpatia · pag. 214; Simbolo · pag. 277; "
                                        "Aura Sacra · pag. 216; Danza Irresistibile di Otto · pag. 228; Gabbia di Forza · pag. 238",
                    zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Guarigione di Massa", "carta:2014/spells.md#Antipatia/Simpatia"])
@pytest.mark.parametrize("indice, campi", [
    ("mass-heal", {"school": "evocation"}),  # «Invocazione»: è evocation in inglese (come Cura Ferite di Massa, CB-4035)
    ("antipathy-sympathy", {"attack_type": "SAVE", "save_ability": "wis"}), ("symbol", {"attack_type": "SAVE", "save_ability": "con"}),
    ("holy-aura", {"attack_type": "SAVE", "save_ability": "con"}), ("irresistible-dance", {"attack_type": "SAVE", "save_ability": "wis"}),
    ("forcecage", {"attack_type": "SAVE", "save_ability": "cha"}),
])
def test_le_voci_2014_del_catalogo_hanno_scuola_e_ts_della_carta(indice, campi):
    voce = _voce("2014", indice)
    assert {k: voce[k] for k in campi} == campi


@pytest.mark.caccia(id="CB-4766", fonte="2024 · Incantesimi · Evoca Elementale · pag. 254; 2014 · Incantesimi · Fatale · pag. 235", zona="regola:2024/incantesimi-D-F",
                    voce="regola", copre=["carta:2024/spells.md#Evoca Elementale", "carta:2014/spells.md#Fatale"])
def test_evoca_elementale_2024_e_fatale_2014_hanno_i_dadi_della_carta():
    for voce in (_voce("2024", "conjure-elemental"), vars(granted_spell("conjure-elemental", "2024"))):  # 8d8 del tipo scelto, +2d8 per slot oltre il 5°
        assert (voce["damage_dice"], voce["damage_type"], voce["higher_levels_dice"]) == ("8d8", None, "2d8")
    assert granted_spell("conjure-elemental", "2014").damage_dice is None  # nel 2014 evoca una creatura, nessun danno
    fatale = _voce("2014", "weird")
    assert (fatale["damage_dice"], fatale["damage_type"], fatale["higher_levels_dice"]) == ("4d10", "psychic", None)


@pytest.mark.caccia(id="CB-4767", fonte="2014 · Chierico · Incantesimi · pag. 58; Paladino · Incantesimi · pag. 97 (dal 2° livello); Multiclasse · pag. 164",
                    zona="regola:2014/cleric", voce="interazione",
                    copre=["carta:2014/spells.md#Cura Ferite", "POST /characters/{char_id}/spells"])
async def test_un_paladino_2014_di_primo_livello_non_toglie_al_chierico_il_livello_massimo_dei_preparati(client):
    cid, _ = await _pg(client, "cleric", 3, wisdom=16, charisma=16)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "paladin", "level": 1, "hit_die": 10})
    assert r.status_code == 201, r.text
    # l'unica classe che incanta è il chierico (slot fino al 2°): un incantesimo non assegnato è suo
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Rianimare Morti", "level": 5, "is_prepared": True})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "spell_above_slots", r.text
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Aiuto", "level": 2, "is_prepared": True})
    assert r.status_code == 201, r.text


@pytest.mark.caccia(id="CB-4769", fonte="2014 · Incantesimi · Vita Falsata · pag. 289; 2014 · Punti Ferita Temporanei · pag. 198",
                    zona="regola:2014/incantesimi-S-Z", voce="ripetizione",
                    copre=["carta:2014/spells.md#Vita Falsata", "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/rounds/tick"])
async def test_vita_falsata_2014_rilanciata_con_un_tiro_piu_basso_svanisce_lo_stesso(client, dadi, test_session_factory):
    cid, classe = await _pg(client, "sorcerer", 5)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Vita Falsata", "srd_index": "false-life", "level": 1, "class_id": classe})
    for dado in (4, 1):  # 8 PF temporanei, poi 5: restano gli 8
        dadi(dado)
        corpo = {"slot_level": 1, "confirm": ["one_slot_per_turn"]}
        assert (await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json=corpo)).status_code == 200
    assert (await client.get(f"/characters/{cid}")).json()["temp_hp"] == 8
    async with test_session_factory() as s:  # l'ultimo round dell'ora, senza 599 tick
        pg = await s.get(Character, cid)
        pg.active_states = [{**x, "rounds_left": 1} if x.get("rounds_left") else x for x in pg.active_states or []]
        await s.commit()
    assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    assert (await client.get(f"/characters/{cid}")).json()["temp_hp"] == 0


@pytest.mark.caccia(id="CB-4781", fonte="2014 · Razze · Nano delle Colline, Robustezza Nanica · pag. 28; Talenti · Robusto · pag. 170",
                    zona="regola:2014/razze", voce="persistenza",
                    copre=["carta:2014/races.md#Nano delle Colline / Hill Dwarf (pag. 28)", "POST /characters/import/ddb"])
@pytest.mark.parametrize("edizione, talento, forzati, massimo", [
    ("2014", None, None, 212), ("2014", "Tough", None, 212 + 38), ("2014", None, 200, 200),
    ("2024", None, None, 212), ("2024", "Tough", None, 212 + 38)])
async def test_l_import_da_beyond_non_conta_due_volte_i_pf_per_livello(client, monkeypatch, edizione, talento, forzati, massimo):
    scheda = await _importa(client, monkeypatch, edizione, talento, forzati)
    assert scheda["computed"]["hp_max_effective"] == massimo
    assert scheda["current_hit_points"] == massimo - 10  # i danni segnati su Beyond restano


@pytest.mark.caccia(id="CB-4782", fonte="2014 · Warlock · Presenza Fatata · pag. 117; Stregone · Presenza Draconica · pag. 102; Mago · Sguardo Ipnotico · pag. 115: TS contro la CD incantesimi; 2024 · Warlock · Investitura del Padrone delle Catene · pag. 156",
                    zona="regola:2014/warlock", voce="regola",
                    copre=["POST /characters/{char_id}/features/{feature_key}/use",
                           "GET /characters/{char_id}/target-effects/{feature_key}", "GET /characters/{char_id}/companions"])
@pytest.mark.parametrize("caso", ["warlock", "stregone", "mago", "famiglio"])
async def test_i_privilegi_contro_la_cd_incantesimi_contano_i_bonus_degli_oggetti(client, caso):
    if caso == "famiglio":
        cid, _ = await _chain(client)
        await _amuleto(client, cid)
        assert (await client.get(f"/characters/{cid}/companions")).json()[0]["save_dc"] == 14 + 1
        return
    if caso == "warlock":
        cid, chiave, corpo = await _warlock(client, 5, "archfey", charisma=16), FEY, {"params": {"mode": "charmed"}}
    elif caso == "stregone":
        cid, chiave, corpo = await _draconic(client, 18, charisma=16), PRESENCE, {"params": {"mode": "awe"}}
    else:
        cid, chiave, corpo = await _wizard(client, 5, "enchantment", intelligence=16), GAZE, {}
    await _amuleto(client, cid)
    (cd,) = [c["save_dc"] for c in (await _scheda(client, cid))["spellcasting"]["casters"]]
    r = await _usa(client, cid, chiave, **corpo)
    assert r.status_code == 200, r.text
    assert (await _effect(client, cid, chiave))["save_dc"] == cd


@pytest.mark.caccia(id="CB-4783", fonte="2024 · Talenti · Iniziato alla Magia · pag. 201; 2014 · Iniziato alla Magia · pag. 168: gli incantesimi del talento hanno CD e attacco degli incantesimi",
                    zona="regola:2024/talenti", voce="interazione",
                    copre=["PUT /characters/{char_id}/feats/{ability_id}/options", "GET /characters/{char_id}"])
async def test_gli_incantesimi_di_un_talento_contano_i_bonus_degli_oggetti(client):
    cid = await _crea(client, "2024", ("fighter", 4, None))
    riga = _feat_rows((await _take(client, cid, "2024_magic_initiate")).json(), "2024_magic_initiate")[0]
    r = await _complete(client, cid, riga["id"], {"list": "wizard", "ability": "intelligence"},
                        [_spell("Luce", 0, "light"), _spell("Dardo di Fuoco", 0, "fire-bolt"), _spell("Charme", 1, "charm-person")])
    assert r.status_code == 200, r.text
    await _amuleto(client, cid)
    charme = next(s for s in (await _scheda(client, cid))["spells"] if s["srd_index"] == "charm-person")
    assert (charme["save_dc"], charme["attack_bonus"]) == (8 + 2 + 2 + 1, 2 + 2 + 1)
