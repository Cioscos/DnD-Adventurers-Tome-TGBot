"""Controlli della zona regola:2024/ranger."""
import pytest

from core.rules.catalog import features_for
from tests.integration.rules.test_2014_bard import _ability, _full, _resolve, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _rest, _turn
from tests.integration.rules.test_2014_paladin_combat import _listed
from tests.integration.rules.test_2014_ranger import _ranger
from tests.integration.rules.test_2024_ranger import _cast_mark, _ranger24
from tests.integration.rules.test_2024_ranger_subclasses import _beast, _companions, _sub, _weapon
from tests.integration.rules.test_species_2024 import _sync

PC, FE, DREAD = "ranger.primal_companion", "ranger.favored_enemy", "ranger.dread_ambusher"


def _option(key):
    return next(o for f in features_for("2024", "ranger") for o in f.roll_options if o.key == key)


async def _incapacitate(client, cid):
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert r.status_code == 200, r.text


async def _slot_totals(client, cid) -> tuple[int, ...]:
    return tuple(s["total"] for s in sorted((await _full(client, cid))["spell_slots"], key=lambda s: s["level"]) if s["total"])


async def _spell_keys(client, cid) -> set[str]:
    return {s["srd_index"] for s in (await client.get(f"/characters/{cid}/spells")).json()}


async def _strike(client, cid, comp, **body):
    return await client.post(f"/characters/{cid}/companions/{comp['id']}/attack", json={"action_index": 0, "dice": [12], **body})


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2511", fonte="2024 · Ranger · Stalker delle Tenebre · Vista Ombrale · pag. 126; Specie · Nano · Scurovisione · pag. 188",
                    zona="regola:2024/ranger", voce="interazione",
                    copre=["carta:2024/classes/ranger.md#Vista Ombrale / Umbral Sight (Stalker delle Tenebre 3, pag. 126)",
                           "carta:2024/races.md#Nano / Dwarf (pag. 188)", "GET /characters/{char_id}"])
@pytest.mark.xfail(strict=True, reason="CB-2511: difforme dal manuale, confermato")
async def test_vista_ombrale_allunga_la_scurovisione_della_specie(client, test_session_factory):
    cid = await _sub(client, 3, "gloom_stalker")
    await _sync(test_session_factory, cid, species_key="2024_dwarf", species_options={})  # 36 m di Scurovisione dalla specie
    senses = (await _full(client, cid))["computed"]["senses"]
    assert {"type": "darkvision", "range_ft": 180} in senses, senses


@pytest.mark.caccia(id="CB-2512", fonte="2024 · Ranger · Stalker delle Tenebre · Paura di Massa (la tua CD degli incantesimi) · pag. 126",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Paura di Massa / Mass Fear (Stalker delle Tenebre 11, pag. 126)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-2512: difforme dal manuale, confermato")
async def test_paura_di_massa_usa_la_cd_degli_incantesimi_della_scheda(client):
    cid = await _sub(client, 11, "gloom_stalker", wisdom=16)
    await _item(client, cid, "Pietra della mente", item_type="generic", bonuses=[{"target": "spell_dc", "value": 1}])
    dc = (await _full(client, cid))["spellcasting"]["casters"][0]["save_dc"]
    assert dc == 8 + 4 + 3 + 1  # competenza, Saggezza e l'oggetto
    label = next(o["label"] for o in await _listed(client, cid, await _weapon(client, cid)) if o["key"] == "ranger.mass_fear")
    assert f"CD {dc}" in label, label


@pytest.mark.caccia(id="CB-2513", fonte="2024 · Ranger · Cacciatore · Preda del Cacciatore Superiore (quando danneggi la creatura marcata) · pag. 127",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Preda del Cacciatore Superiore / Superior Hunter's Prey (Cacciatore 11, pag. 127)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("way", ["unarmed", "spell"])
@pytest.mark.xfail(strict=True, reason="CB-2513: difforme dal manuale, confermato")
async def test_preda_superiore_vale_anche_senza_arma_sulla_creatura_marcata(client, way):
    cid = await _sub(client, 11, "hunter")
    await _cast_mark(client, cid)
    query = {}
    if way == "spell":
        r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "casting_time": "1 azione",
                                                                  "attack_save": "ATK", "damage_dice": "1d10", "damage_type": "fire"})
        assert r.status_code == 201, r.text
        query = {"spell_id": r.json()["id"]}
    keys = await _roll_keys(client, cid, "attack", **query)
    assert "ranger.hunters_mark_damage" in keys  # il danno del marchio vale per questo attacco
    assert "ranger.superior_hunters_prey" in keys, keys


@pytest.mark.caccia(id="CB-2514", fonte="2024 · Ranger · Cacciatore · Preda del Cacciatore e Tattiche Difensive (si cambia dopo un riposo breve o lungo) · pag. 127",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Preda del Cacciatore / Hunter's Prey (Cacciatore 3, pag. 127)",
                           "carta:2024/classes/ranger.md#Tattiche Difensive / Defensive Tactics (Cacciatore 7, pag. 127)",
                           "POST /characters/{char_id}/classes/{class_id}/options/replace"])
@pytest.mark.parametrize("level,group,first,second", [(3, "hunters_prey", "colossus_slayer", "horde_breaker"),
                                                      (7, "defensive_tactics", "escape_the_horde", "multiattack_defense")])
@pytest.mark.xfail(strict=True, reason="CB-2514: difforme dal manuale, confermato")
async def test_l_opzione_del_cacciatore_non_si_cambia_due_volte_senza_riposo(client, level, group, first, second):
    cid = await _sub(client, level, "hunter")
    assert (await _resolve(client, cid, group, [first])).status_code == 200
    klass = (await _full(client, cid))["classes"][0]["id"]
    await _rest(client, cid, "long")
    url = f"/characters/{cid}/classes/{klass}/options/replace"
    assert (await client.post(url, json={"group": group, "old_key": first, "new_key": second})).status_code == 200
    again = await client.post(url, json={"group": group, "old_key": second, "new_key": first})  # nessun riposo in mezzo
    assert again.status_code == 409, again.text


@pytest.mark.caccia(id="CB-2515", fonte="2024 · Ranger · Signore delle Bestie · Compagno Primordiale pag. 122; Glossario · Riposo Lungo: tutti i PF · pag. 370",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)",
                           "carta:2024/general.md#Long Rest (Riposo Lungo) (pag. 370-371)", "POST /characters/{char_id}/rest"])
@pytest.mark.xfail(strict=True, reason="CB-2515: difforme dal manuale, confermato")
async def test_la_bestia_primordiale_ferita_guarisce_col_riposo_lungo(client):
    cid = await _sub(client, 5, "beast_master")
    comp = await _beast(client, cid)
    r = await client.patch(f"/characters/{cid}/companions/{comp['id']}/hp", json={"op": "damage", "value": 10})
    assert r.status_code == 200, r.text
    await _rest(client, cid, "long")
    back = next(c for c in await _companions(client, cid) if c["feature_key"] == PC)
    assert (back["current_hp"], back["max_hp"]) == (30, 30)


@pytest.mark.caccia(id="CB-2516", fonte="2024 · Ranger · Signore delle Bestie · Bestia della Terra (Dadi Vita d8 pari al livello) pag. 123; Glossario · Riposo Breve · pag. 373",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Bestia della Terra / Beast of the Land (Signore delle Bestie 3, pag. 123)",
                           "carta:2024/general.md#Short Rest (Riposo Breve) (pag. 373)", "POST /characters/{char_id}/companions/{comp_id}/hit-dice"])
@pytest.mark.xfail(strict=True, reason="CB-2516: difforme dal manuale, confermato")
async def test_la_bestia_primordiale_spende_i_suoi_dadi_vita(client, dadi):
    cid = await _sub(client, 5, "beast_master")
    comp = await _beast(client, cid)
    assert comp["statblock"]["hit_dice"] == "5d8"
    r = await client.patch(f"/characters/{cid}/companions/{comp['id']}/hp", json={"op": "damage", "value": 10})
    assert r.status_code == 200, r.text
    dadi(4)
    r = await client.post(f"/characters/{cid}/companions/{comp['id']}/hit-dice", json={"count": 1})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 4 + 2  # d8 + COS +2


@pytest.mark.caccia(id="CB-2517", fonte="2024 · Ranger · Colpi Terribili pag. 124, Imboscatore Terribile pag. 125, Furia Bestiale pag. 123, Preda del Cacciatore Superiore pag. 127",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Colpi Terribili / Dreadful Strikes (Viandante Fatato 3, pag. 124)",
                           "carta:2024/classes/ranger.md#Imboscatore Terribile / Dread Ambusher (Stalker delle Tenebre 3, pag. 125)",
                           "carta:2024/classes/ranger.md#Furia Bestiale / Bestial Fury (Signore delle Bestie 11, pag. 123)",
                           "carta:2024/classes/ranger.md#Preda del Cacciatore Superiore / Superior Hunter's Prey (Cacciatore 11, pag. 127)"])
@pytest.mark.parametrize("key,kind", [("ranger.dreadful_strikes", "psychic"), ("ranger.dreadful_strike", "psychic"),
                                      ("ranger.bestial_fury_damage", "force"), ("ranger.superior_hunters_prey", "force")])
@pytest.mark.xfail(strict=True, reason="CB-2517: difforme dal manuale, confermato")
def test_i_dadi_extra_dei_privilegi_hanno_il_tipo_di_danno_della_carta(key, kind):
    assert _option(key).extra_damage_type == kind


@pytest.mark.caccia(id="CB-2518", fonte="2024 · Ranger · Instancabile, Velo della Natura pag. 121, Svolta Ammaliante pag. 125, Schivata d'Ombra pag. 126; Glossario · Incapacitato · pag. 369",
                    zona="regola:2024/ranger", voce="interazione",
                    copre=["carta:2024/classes/ranger.md#Instancabile / Tireless (Ranger 10, pag. 121)",
                           "carta:2024/classes/ranger.md#Velo della Natura / Nature's Veil (Ranger 14, pag. 121)",
                           "carta:2024/classes/ranger.md#Svolta Ammaliante / Beguiling Twist (Viandante Fatato 7, pag. 125)",
                           "carta:2024/classes/ranger.md#Schivata d'Ombra / Shadowy Dodge (Stalker delle Tenebre 15, pag. 126)",
                           "carta:2024/general.md#Incapacitated [Condition] (Incapacitato) (pag. 369)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("sub,key,params", [(None, "ranger.tireless", None), (None, "ranger.natures_veil", None),
                                            ("fey_wanderer", "ranger.beguiling_twist", {"condition": "charmed"}),
                                            ("gloom_stalker", "ranger.shadowy_dodge", None)])
async def test_un_ranger_incapacitato_non_usa_azioni_azioni_bonus_ne_reazioni(client, sub, key, params):
    cid = await (_sub(client, 15, sub, wisdom=16) if sub else _ranger24(client, 15, wisdom=16))
    await _incapacitate(client, cid)
    r = await _use(client, cid, key, **({"params": params} if params else {}))
    assert r.status_code == 409, r.text
    turn = await _turn(client, cid)
    assert not (turn["action_used"] or turn["bonus_used"] or turn["reaction_used"])


@pytest.mark.caccia(id="CB-2519", fonte="2024 · Ranger · Signore delle Bestie · Compagno Primordiale (da sola agisce e reagisce, una volta) · pag. 122",
                    zona="regola:2024/ranger", voce="limiti",
                    copre=["carta:2024/classes/ranger.md#Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)",
                           "POST /characters/{char_id}/companions/{comp_id}/attack"])
@pytest.mark.parametrize("way", ["reaction", "autonomous"])
@pytest.mark.xfail(strict=True, reason="CB-2519: difforme dal manuale, confermato")
async def test_la_bestia_primordiale_senza_ordini_non_attacca_senza_limite(client, way):
    cid = await _sub(client, 5, "beast_master")
    comp = await _beast(client, cid)
    if way == "autonomous":
        await _incapacitate(client, cid)  # il ranger non ordina: la bestia decide da sola, con la sua azione
    body = {"reaction": True} if way == "reaction" else {}
    assert (await _strike(client, cid, comp, **body)).status_code == 200
    second = await _strike(client, cid, comp, **body)
    assert second.status_code == 409, second.text


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2521", fonte="2024 · Ranger · Tabella di classe e Nemico Prescelto · pag. 119", zona="regola:2024/ranger", voce="limiti",
                    copre=["carta:2024/classes/ranger.md#Nemico Prescelto / Favored Enemy (Ranger 1, pag. 119)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("level,uses", [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)])
async def test_i_lanci_gratuiti_del_marchio_seguono_la_colonna_della_tabella(client, level, uses):
    row = await _ability(client, await _ranger24(client, level), FE)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (uses, uses, "long_rest")


@pytest.mark.caccia(id="CB-2522", fonte="2024 · Ranger · Tabella di classe e Incantesimi · pag. 119", zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Incantesimi / Spellcasting (Ranger 1, pag. 119)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("level,prepared,slots", [(1, 2, (2,)), (2, 3, (2,)), (3, 4, (3,)), (5, 6, (4, 2)), (9, 9, (4, 3, 2)),
                                                  (13, 11, (4, 3, 3, 1)), (17, 14, (4, 3, 3, 3, 1)), (19, 15, (4, 3, 3, 3, 2)),
                                                  (20, 15, (4, 3, 3, 3, 2))])
async def test_preparati_e_slot_seguono_la_tabella_2024(client, level, prepared, slots):
    cid = await _ranger24(client, level)
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"] or 0, limits["prepared_limit"]) == (0, prepared)
    assert await _slot_totals(client, cid) == slots


@pytest.mark.caccia(id="CB-2523", fonte="2024 · Ranger · Incantesimi e Nemico Prescelto dal 1° livello · pag. 119; 2014 · Ranger · Incantesimi dal 2° · pag. 104",
                    zona="regola:2024/ranger", voce="edizioni",
                    copre=["carta:2024/classes/ranger.md#Incantesimi / Spellcasting (Ranger 1, pag. 119)",
                           "carta:2014/classes/ranger.md#Incantesimi / Spellcasting (Ranger 2, pag. 104)", "PATCH /characters/{char_id}"])
async def test_il_ranger_di_primo_livello_lancia_solo_nel_2024(client):
    old = await _ranger(client, 1)
    assert await _slot_totals(client, old) == () and "hunters-mark" not in await _spell_keys(client, old)
    new = await _ranger24(client, 1)
    assert await _slot_totals(client, new) == (2,) and "hunters-mark" in await _spell_keys(client, new)


@pytest.mark.caccia(id="CB-2524", fonte="2024 · Ranger · Signore delle Bestie · Bestia della Terra e Bestia del Cielo · pag. 123-124",
                    zona="regola:2024/ranger", voce="limiti",
                    copre=["carta:2024/classes/ranger.md#Bestia della Terra / Beast of the Land (Signore delle Bestie 3, pag. 123)",
                           "carta:2024/classes/ranger.md#Bestia del Cielo / Beast of the Sky (Signore delle Bestie 3, pag. 124)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("level,kind,hp,attack", [(3, "land", 20, 2 + 3), (3, "sky", 16, 2 + 3), (20, "land", 105, 6 + 3), (20, "sky", 84, 6 + 3)])
async def test_pf_ca_e_attacco_della_bestia_primordiale_ai_livelli_estremi(client, level, kind, hp, attack):
    cid = await _sub(client, level, "beast_master", wisdom=16)
    comp = await _beast(client, cid, kind, "slashing")
    assert (comp["max_hp"], comp["armor_class"], comp["attack_bonus_extra"], comp["damage_bonus_extra"]) == (hp, 13 + 3, attack, 3)


@pytest.mark.caccia(id="CB-2525", fonte="2024 · Ranger · Stalker delle Tenebre · Imboscatore Terribile pag. 125 e Raffica dello Stalker pag. 126",
                    zona="regola:2024/ranger", voce="limiti",
                    copre=["carta:2024/classes/ranger.md#Imboscatore Terribile / Dread Ambusher (Stalker delle Tenebre 3, pag. 125)",
                           "carta:2024/classes/ranger.md#Raffica dello Stalker / Stalker's Flurry (Stalker delle Tenebre 11, pag. 126)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("level,wisdom,dice,uses", [(10, 16, "2d6", 3), (11, 8, "2d8", 1)])
async def test_colpo_terribile_dadi_e_usi_alle_soglie(client, level, wisdom, dice, uses):
    cid = await _sub(client, level, "gloom_stalker", wisdom=wisdom)
    option = next(o for o in await _listed(client, cid, await _weapon(client, cid)) if o["key"] == "ranger.dreadful_strike")
    row = await _ability(client, cid, DREAD)
    assert (option["dice"], row["max_uses"], row["restoration_type"]) == (dice, uses, "long_rest")


@pytest.mark.caccia(id="CB-2526", fonte="2024 · Ranger · Multiclasse: Ranger (esempio Ranger 4 / Stregone 3) · pag. 44", zona="regola:2024/ranger",
                    voce="interazione", copre=["carta:2024/classes/ranger.md#Multiclasse: Ranger / Multiclassing: Ranger (Creare un Personaggio, pag. 44)",
                                               "POST /characters/{char_id}/classes"])
async def test_ranger_quattro_e_stregone_tre_hanno_gli_slot_del_quinto(client):
    cid = await _ranger24(client, 4)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "sorcerer", "level": 3, "hit_die": 6})
    assert r.status_code == 201, r.text
    assert await _slot_totals(client, cid) == (4, 3, 2)


@pytest.mark.caccia(id="CB-2527", fonte="2024 · Ranger · Nemico Prescelto · pag. 119", zona="regola:2024/ranger", voce="ripetizione",
                    copre=["carta:2024/classes/ranger.md#Nemico Prescelto / Favored Enemy (Ranger 1, pag. 119)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_il_doppio_invio_del_lancio_gratuito_spende_un_solo_uso(client):
    cid = await _ranger24(client, 1)
    assert (await _use(client, cid, FE)).status_code == 200
    assert (await _use(client, cid, FE)).status_code == 409
    assert (await _ability(client, cid, FE))["uses"] == 1


@pytest.mark.caccia(id="CB-2528", fonte="2024 · Ranger · Cacciatore · Difesa del Cacciatore Superiore · pag. 127", zona="regola:2024/ranger",
                    voce="annullamento", copre=["carta:2024/classes/ranger.md#Difesa del Cacciatore Superiore / Superior Hunter's Defense (Cacciatore 15, pag. 127)",
                                                "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_rende_reazione_e_resistenza_della_difesa_superiore(client):
    cid = await _sub(client, 15, "hunter")
    for op in ("set_max", "set_current"):
        await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": 300})
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "raw_value": 20, "damage_type": "slashing",
                                                          "options": ["ranger.superior_hunters_defense"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == 290
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": (await _full(client, cid))["hp_undo_id"]})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["current_hit_points"] == 300 and not any(s["key"] == "superior_hunters_defense" for s in full["active_states"] or [])
    assert (await _turn(client, cid))["reaction_used"] is False
