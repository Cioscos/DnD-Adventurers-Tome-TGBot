"""Controlli della revisione indipendente dei gruppi lancio-core, dati-incantesimi-fe, catalogo-incantesimi, scelte, stati-turno, oggetti e pf-personaggio."""
import json
from pathlib import Path

import pytest

from sqlalchemy import select

from core.db.models import Character, SessionParticipant, SessionRole, SpellSlot
from core.rules.catalog.granted_spells import granted_spell
from tests.caccia.test_cb_regola_2024_fighter import _guerriero, _manovre, _scheda, _usa
from tests.caccia.test_cb_regola_fix_lancio_core import _pg
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_bard import _roll_keys, _sword, _use
from tests.integration.rules.test_2014_fighter_battle_master import _damage, _hit, _key
from tests.integration.rules.test_2014_ranger_beast import _panther
from tests.integration.rules.test_2014_ranger_hunter import _superior
from tests.integration.rules.test_2014_sorcerer_origins import PRESENCE, _draconic
from tests.integration.rules.test_2014_warlock import _warlock
from tests.integration.rules.test_2014_warlock_invocations import _blade, _caster
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
                           "GET /characters/{char_id}/target-effects/{effect_key}", "GET /characters/{char_id}/companions"])
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


@pytest.mark.caccia(id="CB-4784", fonte="2024 · Talenti · Combattere con armi a due mani / Great Weapon Fighting · pag. 209",
                    zona="regola:2024/talenti", voce="interazione",
                    copre=["carta:2024/feats.md#Combattere con armi a due mani / Great Weapon Fighting (pag. 209)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
async def test_armi_a_due_mani_2024_anche_il_dado_di_superiorita_vale_almeno_3(client, dadi):
    cid = await _guerriero(client, 3, "battle_master", strength=16)
    stile = next(c for c in (await _scheda(client, cid))["pending_choices"] if c.get("group") == "fighting_style")
    r = await client.post(f"/characters/{cid}/choices/{stile['id']}/resolve", json={"kind": "class_option", "options": ["great_weapon"]})
    assert r.status_code == 200, r.text
    await _manovre(client, cid, "pushing", "trip", "menacing")
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spadone", "item_type": "weapon", "item_metadata": {
        "damage_dice": "2d6", "weapon_type": "melee", "properties": ["two_handed", "heavy"]}})
    spadone = max(i["id"] for i in r.json()["items"])
    dadi(6, 6)
    colpo = await _hit(client, cid, spadone, grip="two")
    dadi(1)
    r = await _damage(client, cid, colpo, _key("pushing"))
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["extra_rolls"] == [3]  # «ogni 1 o 2 sui dadi di danno conta come 3»


@pytest.mark.caccia(id="CB-4785", fonte="2024 · Guerriero · Azione Impetuosa · pag. 91: l'azione in più non può essere l'azione Magia; Paladino · Destriero Fedele · pag. 111; Warlock · Vigore Immondo · pag. 155; Chierico · Preservare Vita; Ranger · Compagno Primordiale · pag. 122",
                    zona="regola:2024/fighter", voce="interazione",
                    copre=["carta:2024/classes/fighter.md#Azione Impetuosa / Action Surge (Guerriero 2, pag. 91)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/preserve-life"])
@pytest.mark.parametrize("caso", ["destriero", "vigore", "preservare", "compagno"])
async def test_azione_impetuosa_non_paga_i_lanci_e_i_privilegi_ad_azione_magia(client, caso):
    classe = {"destriero": ("paladin", 5, None), "vigore": ("warlock", 2, None), "preservare": ("cleric", 3, "Dominio della Vita"),
              "compagno": ("ranger", 3, "Signore delle Bestie")}[caso]
    cid = await _crea(client, "2024", ("fighter", 2, None), classe)
    if caso == "vigore":
        scelta = next(c for c in (await _scheda(client, cid))["pending_choices"] if c.get("group") == "invocations")
        chiavi = ["fiendish_vigor", *(o["key"] for o in scelta["options"] if o["key"] not in ("fiendish_vigor", "agonizing_blast", "repelling_blast", "eldritch_spear"))]
        r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": chiavi[:scelta["count"]]})
        assert r.status_code == 200, r.text
    if caso == "compagno":  # la bestia a terra si rialza con l'azione Magia e uno slot
        r = await _usa(client, cid, "ranger.primal_companion", params={"pay": "use", "kind": "land", "damage_type": "slashing"})
        assert r.status_code == 200, r.text
        bestia = (await client.get(f"/characters/{cid}/companions")).json()[0]["id"]
        r = await client.patch(f"/characters/{cid}/companions/{bestia}/hp", json={"op": "damage", "value": 999})
        assert r.status_code == 200, r.text
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    assert (await _usa(client, cid, "fighter.action_surge")).status_code == 200
    assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})).status_code == 200
    if caso == "preservare":
        r = await client.post(f"/characters/{cid}/preserve-life", json={"allocations": [{"character_id": cid, "amount": 1}]})
    else:
        chiave, corpo = {"destriero": ("paladin.faithful_steed", {"params": {"name": "Lampo", "steed_type": "celestial"}}),
                         "vigore": ("warlock.fiendish_vigor", {}),
                         "compagno": ("ranger.primal_companion", {"params": {"pay": "slot", "kind": "land", "slot_level": "1"}})}[caso]
        r = await _usa(client, cid, chiave, **corpo)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "surge_no_magic", r.text


@pytest.mark.caccia(id="CB-4786", fonte="2014 · Equipaggiamento · Armature, Scudi · pag. 144-145", zona="regola:2014/equipaggiamento", voce="persistenza",
                    copre=["PATCH /characters/{char_id}/items/{item_id}"])
async def test_uno_scudo_imbracciato_che_diventa_un_arma_non_da_piu_ca(client):
    cid = await _crea(client, "2014", ("fighter", 1, None))
    r = await client.post(f"/characters/{cid}/items", json={"name": "Scudo", "item_type": "shield", "item_metadata": {"ac_bonus": 2}})
    iid = r.json()["items"][0]["id"]
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "off_hand"})
    assert r.json()["shield_armor_class"] == 2
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"item_type": "weapon", "item_metadata": {"damage_dice": "1d4"}})
    assert r.status_code == 200, r.text
    assert r.json()["shield_armor_class"] == 0


@pytest.mark.caccia(id="CB-4787", fonte="2014 · Ranger · Sterminatore di Nemici · pag. 105", zona="regola:2014/ranger", voce="persistenza",
                    copre=["POST /sessions/{session_id}/close", "GET /characters/{char_id}/roll-options"])
async def test_chiusa_la_serata_a_meta_scontro_non_e_piu_il_turno_di_un_altro(client, test_session_factory, monkeypatch, come_utente):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    come_utente(GM_ID)
    cid = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]["character_id"]
    come_utente(PLAYER_ID)
    assert (await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 16})).status_code == 200
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "ranger", "level": 20, "hit_die": 10})).status_code == 201
    spada = await _sword(client, cid)
    come_utente(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # turno del goblin
    assert (await client.post(f"/sessions/{sid}/close")).status_code == 204
    come_utente(PLAYER_ID)
    assert "ranger.foe_slayer_attack" in await _roll_keys(client, cid, "attack", item_id=spada)


@pytest.mark.caccia(id="CB-4791", fonte="2014 · Ranger · Sterminatore di Nemici · pag. 105 (solo nei propri turni)", zona="regola:2014/ranger", voce="interazione",
                    copre=["POST /sessions/{session_id}/encounter/sync-pcs", "GET /characters/{char_id}/roll-options"])
async def test_chi_entra_a_scontro_avviato_non_e_nel_proprio_turno(client, test_session_factory, monkeypatch, come_utente):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    come_utente(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/start", json={})).status_code == 200  # turno del primo PG
    come_utente(555)
    cid = await _crea(client, "2014", ("ranger", 20, None))
    spada = await _sword(client, cid)
    async with test_session_factory() as s:
        s.add(SessionParticipant(session_id=sid, user_id=555, character_id=cid, role=SessionRole.PLAYER, joined_at="2026-01-01T00:00:00+00:00"))
        await s.commit()
    come_utente(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/sync-pcs")
    assert r.status_code == 200, r.text
    come_utente(555)
    assert "ranger.foe_slayer_attack" not in await _roll_keys(client, cid, "attack", item_id=spada)


@pytest.mark.caccia(id="CB-4788", fonte="2014 · Talenti · Incantatore Rituale / Ritual Caster · pag. 168", zona="regola:2014/talenti", voce="interazione",
                    copre=["carta:2014/feats.md#Incantatore Rituale / Ritual Caster (pag. 168)",
                           "GET /characters/{char_id}/spells/{spell_id}/cast-check"])
async def test_un_rituale_gia_conosciuto_senza_classe_resta_lanciabile_con_lo_slot(client):
    cid = await _crea(client, "2014", ("wizard", 5, None))
    # la scheda di un mago di una sola classe salva gli incantesimi senza classe
    r = await client.post(f"/characters/{cid}/spells", json={**_spell("Allarme", 1, "alarm"), "is_ritual": True})
    assert r.status_code == 201, r.text
    riga = next(a for a in _feat_rows((await _take(client, cid, "ritual_caster")).json(), "ritual_caster"))
    r = await _complete(client, cid, riga["id"], {"list": "wizard"}, [
        {**_spell("Allarme", 1, "alarm"), "is_ritual": True}, {**_spell("Identificare", 1, "identify"), "is_ritual": True}])
    assert r.status_code == 200, r.text
    incantesimi = {s["srd_index"]: s["id"] for s in r.json()["spells"]}
    preparati = {s["srd_index"]: s["always_prepared"] for s in r.json()["spells"]}
    assert preparati == {"alarm": False, "identify": True}  # il libro dei rituali non lo prepara per il mago

    async def avvisi(chiave: str) -> list[str]:
        return (await client.get(f"/characters/{cid}/spells/{incantesimi[chiave]}/cast-check")).json()

    assert "ritual_only" not in await avvisi("alarm")  # è nel suo libro degli incantesimi
    assert "ritual_only" in await avvisi("identify")  # solo nel libro dei rituali


@pytest.mark.caccia(id="CB-4789", fonte="2024 · Warlock · Patto della Lama · pag. 156: la competenza è di chi ha legato l'arma", zona="regola:2024/warlock", voce="interazione",
                    copre=["POST /sessions/{session_id}/trade"])
async def test_un_arma_legata_ceduta_non_e_piu_l_arma_del_patto():
    from types import SimpleNamespace
    from api.services.trades import give_item
    from core.db.models import Item

    class Db:
        async def flush(self): ...
        def add(self, _row): ...
    arma = Item(id=1, character_id=1, name="Spada lunga +1", item_type="weapon", quantity=1, weight=3.0, is_equipped=False, item_metadata=json.dumps(
        {"damage_dice": "1d8", "weapon_category": "martial", "magic_bonus": 1, "pact_weapon": True, "pact_bound": True,
         "damage_type": "psychic", "pact_original_damage_type": "slashing"}))
    cede, riceve = SimpleNamespace(id=1, items=[arma]), SimpleNamespace(id=2, items=[])
    await give_item(Db(), cede, riceve, 1, None)
    meta = json.loads(arma.item_metadata)
    assert "pact_weapon" not in meta and meta["damage_type"] == "slashing"


@pytest.mark.caccia(id="CB-4790", fonte="2024 · Furfante · Usare Dispositivi Magici · pag. 131; Glossario · Addestramento nelle armature · pag. 361; 2024 · Barbaro · Ira · pag. 51",
                    zona="regola:2024/rogue", voce="interazione", copre=["POST /characters/{char_id}/items/{item_id}/scroll"])
async def test_la_pergamena_chiede_conferma_in_armatura_senza_addestramento(client):
    cid = await _crea(client, "2024", ("rogue", 13, "Furfante"))
    r = await client.post(f"/characters/{cid}/items", json={"name": "Armatura a piastre", "item_type": "armor", "item_metadata": {
        "armor_type": "heavy", "ac_value": 18}})
    piastre = max(i["id"] for i in r.json()["items"])
    assert (await client.patch(f"/characters/{cid}/items/{piastre}", json={"is_equipped": True, "equipment_slot": "body"})).status_code == 200
    r = await client.post(f"/characters/{cid}/items", json={"name": "Pergamena", "item_type": "consumable", "quantity": 1,
                                                           "item_metadata": {"subtype": "scroll"}})
    pergamena = max(i["id"] for i in r.json()["items"])
    r = await client.post(f"/characters/{cid}/items/{pergamena}/scroll", json={"spell_level": 1})
    assert r.status_code == 409 and r.json()["detail"] == {"code": "cast_confirm", "warnings": ["armor"]}, r.text
    r = await client.post(f"/characters/{cid}/items/{pergamena}/scroll", json={"spell_level": 1, "confirm": ["armor"]})
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-4792", fonte="2024 · Talenti · Maestro d'Armi / Weapon Master · pag. 209 (un'arma in cui si è competenti)", zona="regola:2024/talenti", voce="limiti",
                    copre=["PUT /characters/{char_id}/feats/{ability_id}/options"])
async def test_maestro_d_armi_dice_che_manca_la_competenza(client):
    cid = await _crea(client, "2024", ("wizard", 4, None))
    riga = _feat_rows((await _take(client, cid, "2024_weapon_master", "strength")).json(), "2024_weapon_master")[0]
    r = await _complete(client, cid, riga["id"], {"weapon_mastery": ["greatsword"]})
    assert r.status_code == 422 and r.json()["detail"] == "feat_weapon_not_proficient", r.text


@pytest.mark.caccia(id="CB-4811", fonte="2014 · Guerriero · Atleta Straordinario · pag. 72; Chierico · Conoscenze Secolari · pag. 60: con la competenza la metà non si somma", zona="regola:2014/fighter", voce="interazione",
                    copre=["carta:2014/classes/fighter.md#Atleta Straordinario / Remarkable Athlete (Campione 7, pag. 72)",
                           "POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_conoscenze_secolari_sostituisce_l_atleta_straordinario(client):
    cid = await _crea(client, "2014", ("fighter", 7, "Campione"), ("cleric", 2, "Dominio della Conoscenza"))

    async def bonus() -> int:
        return (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10})).json()["bonus"]

    assert await bonus() == 2 + 2  # Forza e metà competenza
    r = await _use(client, cid, "cleric.knowledge_of_the_ages", params={"skill": "athletics"})
    assert r.status_code == 200, r.text
    assert await bonus() == 2 + 4  # Forza e competenza


@pytest.mark.caccia(id="CB-4812", fonte="2014 · Guerriero · Implacabile · pag. 74; 2014 · Monaco · Perfezione Interiore · pag. 92; 2024 · Druido · Arcidruido · pag. 82", zona="regola:2014/fighter", voce="regola",
                    copre=["POST /characters/{char_id}/dice/initiative"])
@pytest.mark.parametrize("edizione,classe,livello,sub,riserva,dopo", [
    ("2014", "fighter", 15, "Maestro di Battaglia", "fighter.superiority_dice", 1),
    ("2014", "monk", 20, None, "monk.ki", 4),
    ("2024", "druid", 20, None, "druid.wild_shape", 1)])
async def test_i_recuperi_passivi_scattano_da_soli_al_tiro_di_iniziativa(client, edizione, classe, livello, sub, riserva, dopo):
    cid = await _crea(client, edizione, (classe, livello, sub))

    async def usi(nuovi: int | None = None) -> int:
        riga = next(a for a in (await client.get(f"/characters/{cid}")).json()["abilities"] if a["feature_key"] == riserva)
        if nuovi is not None:
            assert (await client.patch(f"/characters/{cid}/abilities/{riga['id']}", json={"uses": nuovi})).status_code == 200
        return riga["uses"]

    await usi(0)
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8})  # il giocatore non spunta nulla
    assert r.status_code == 200, r.text
    assert await usi() == dopo


@pytest.mark.caccia(id="CB-4813", fonte="2014 · Monaco · Anima Adamantina · pag. 92; 2024 · Monaco · Sopravvissuto Disciplinato · pag. 103: ogni tiro salvezza fallito", zona="regola:2014/monk", voce="regola",
                    copre=["carta:2014/classes/monk.md#Anima Adamantina / Diamond Soul (Monaco 14, pag. 92)",
                           "POST /characters/{char_id}/death_saves/roll", "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.parametrize("edizione,opzione", [("2014", "monk.diamond_soul"), ("2024", "monk.disciplined_survivor")])
async def test_il_monaco_ripete_anche_un_ts_contro_la_morte_fallito(client, edizione, opzione):
    cid = await _crea(client, edizione, ("monk", 14, None))
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})).status_code == 200
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 5})
    assert r.status_code == 200 and r.json()["outcome"] == "failure", r.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [opzione], "dice": [15]})
    assert r.status_code == 200, r.text
    assert r.json()["death"]["successes"] == 1


@pytest.mark.caccia(id="CB-4814", fonte="2014 · Warlock · Tutt'Uno con le Ombre · pag. 119: finisce con un'azione (l'azione Attacco di cui si cede un attacco)", zona="regola:2014/warlock", voce="interazione",
                    copre=["carta:2014/classes/warlock.md#Tutt'Uno con le Ombre / One with Shadows (Suppliche Occulte, livello 5, pag. 119)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_tutt_uno_con_le_ombre_finisce_anche_cedendo_un_attacco_al_famiglio(client):
    cid = await _caster(client, 5, "one_with_shadows", boon="chain")
    assert (await _use(client, cid, "warlock.one_with_shadows", params={"light": "dark"})).status_code == 200
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    r = await _use(client, cid, "warlock.pact_of_the_chain")
    assert r.status_code == 200, r.text
    assert not (await client.get(f"/characters/{cid}")).json()["conditions"].get("invisible")


@pytest.mark.caccia(id="CB-4815", fonte="2014 · Warlock · Succhiavita · pag. 119: danni necrotici", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Succhiavita / Lifedrinker (Suppliche Occulte, livello 12, Patto della Lama, pag. 119)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_succhiavita_dice_quanti_danni_sono_necrotici(client):
    cid = await _caster(client, 12, "lifedrinker", boon="blade", charisma=18, strength=10)
    r = await client.post(f"/characters/{cid}/items/{await _blade(client, cid)}/attack", json={"to_hit_die": 15})
    assert r.status_code == 200, r.text
    effetti = (r.json()["option_result"] or {}).get("effects") or []
    assert any("necrotici" in e["it"] and "4" in e["it"] and "necrotic" in e["en"] for e in effetti), r.json()


@pytest.mark.caccia(id="CB-4816", fonte="2014 · Bardo · Controfascino · pag. 54: fino alla fine del turno successivo; L5, fine dello scontro", zona="regola:2014/bard", voce="interazione",
                    copre=["carta:2014/classes/bard.md#Controfascino / Countercharm (Bardo 6, pag. 54)",
                           "POST /sessions/{session_id}/encounter/end"])
async def test_il_controfascino_non_resta_acceso_dopo_lo_scontro(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    cid = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]["character_id"]
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 6})).status_code == 201
    assert (await _use(client, cid, "bard.countercharm")).status_code == 200
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    as_user(PLAYER_ID)
    assert not _ha((await client.get(f"/characters/{cid}")).json(), "countercharm")
