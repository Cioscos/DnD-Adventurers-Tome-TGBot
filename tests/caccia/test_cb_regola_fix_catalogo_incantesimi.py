"""Controlli scritti dalla correzione del gruppo catalogo-incantesimi per i dubbi «Q-…» risolti come difetti."""
import pytest

from core.db.models import Character
from tests.integration._encounter_helpers import GM_ID, as_user

HAIL = "spell:hail_of_thorns:hit"


async def _pg(client, classe, livello, edizione="2024") -> int:
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": edizione, "initial_class": {
        "class_name": classe, "level": livello, "subclass": None}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _arma(client, cid, nome, **meta) -> int:
    r = await client.post(f"/characters/{cid}/items", json={"name": nome, "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _opzioni(client, cid, arma, modo) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": arma, "attack_mode": modo})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


@pytest.mark.caccia(id="CB-4071", fonte="2024 · Incantesimi · Grandine di spine · pag. 283; 2014 · Incantesimi · Raffica di Spine · pag. 266",
                    zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Grandine di spine", "carta:2014/spells.md#Raffica di Spine", "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("edizione, dopo_il_lancio", [("2024", False), ("2014", True)])
async def test_grandine_di_spine_2024_non_vale_dopo_il_lancio_di_un_arma_da_mischia(client, edizione, dopo_il_lancio):
    cid = await _pg(client, "ranger", 2, edizione)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Grandine di Spine", "srd_index": "hail-of-thorns", "level": 1,
                                                            "is_concentration": edizione == "2014"})
    assert r.status_code == 201, r.text
    if edizione == "2014":  # la Raffica 2014 si lancia prima e resta sul lanciatore
        assert (await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_level": 1})).status_code == 200
    pugnale = await _arma(client, cid, "Pugnale", damage_dice="1d4", damage_type="piercing", weapon_type="melee",
                          properties=["finesse", "light", "thrown"])
    dardo = await _arma(client, cid, "Dardo", damage_dice="1d4", damage_type="piercing", weapon_type="ranged", properties=["finesse", "thrown"])
    # 2024: «subito dopo aver colpito con un'arma a distanza» (la categoria dell'arma): il pugnale lanciato resta un'arma da mischia.
    # 2014 p.266: «attacco con arma a distanza», il lancio conta.
    assert (HAIL in await _opzioni(client, cid, pugnale, "thrown")) is dopo_il_lancio
    assert HAIL in await _opzioni(client, cid, dardo, "thrown")
    assert HAIL not in await _opzioni(client, cid, pugnale, "melee")


@pytest.mark.caccia(id="CB-4072", fonte="2024 · Incantesimi · Eroismo · pag. 285; 2024 · Capitolo 1 · Punti Ferita Temporanei · pag. 29",
                    zona="regola:2024/incantesimi-D-F", voce="edizioni",
                    copre=["carta:2024/spells.md#Eroismo", "carta:2014/spells.md#Eroismo", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "PATCH /characters/{char_id}/concentration"])
@pytest.mark.parametrize("modo", ["manual", "concentration"])
@pytest.mark.parametrize("edizione, restano", [("2024", 3), ("2014", 0)])
async def test_eroismo_2024_i_pf_temporanei_restano_quando_l_incantesimo_finisce(client, test_session_factory, edizione, restano, modo):
    from tests.integration.rules.test_spell_effects_defenses import _cast, _sheet, _table
    from tests.integration.rules.test_spell_effects_hp import _end_spell, _new_turn
    eroe, chierico, eroismo = await _table(client, test_session_factory, "Heroism", "heroism", 1, hero_edition=edizione, caster_edition=edizione)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{chierico}/classes", json={"class_name": "bard", "level": 3, "hit_die": 8})).status_code == 201
    assert (await client.patch(f"/characters/{chierico}/ability_scores/charisma", json={"value": 16})).status_code == 200  # +3
    await _cast(client, chierico, eroismo, [eroe], level=1)
    await _new_turn(client, eroe)
    assert (await _sheet(client, eroe))["temp_hp"] == 3
    await _end_spell(client, eroe, chierico, "heroism", modo)
    # 2024: la carta non toglie i PF temporanei a fine incantesimo, durano fino a esaurimento o al Riposo Lungo (p.29).
    # 2014: «quando l'incantesimo termina, il bersaglio perde i punti ferita temporanei rimanenti».
    assert (await _sheet(client, eroe))["temp_hp"] == restano


@pytest.mark.caccia(id="CB-4073", fonte="2014 · Incantesimi · Vita Falsata · pag. 289; 2014 · Punti Ferita Temporanei · pag. 198",
                    zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Vita Falsata", "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/rounds/tick"])
async def test_vita_falsata_2014_i_pf_temporanei_finiscono_dopo_l_ora(client, test_session_factory, dadi):
    from tests.caccia.test_cb_regola_2014_incantesimi_s_z import _impara, _lancia, _pg
    cid = await _pg(client, "sorcerer", 5)
    vita = await _impara(client, cid, "false-life")
    dadi(4)
    assert (await _lancia(client, cid, vita, 1))["temp_hp"] == 8
    stati = {s["key"]: s["rounds_left"] for s in (await client.get(f"/characters/{cid}")).json()["active_states"] or []}
    assert "spell:false_life" in stati and stati.get("spell_cast:false_life") == 600  # 1 ora, sull'orologio di chi lancia
    async with test_session_factory() as s:  # l'ultimo round dell'ora, senza 599 tick
        pg = await s.get(Character, cid)
        pg.active_states = [{**x, "rounds_left": 1} if x.get("rounds_left") else x for x in pg.active_states or []]
        await s.commit()
    assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    # «ottieni 1d4 + 4 punti ferita temporanei per la durata»: finita l'ora, quelli rimasti si perdono
    assert (await client.get(f"/characters/{cid}")).json()["temp_hp"] == 0


@pytest.mark.caccia(id="CB-4074", fonte="2024 · Incantesimi · Legame di Protezione · pag. 340; 2024 · Bersagli · pag. 237",
                    zona="regola:2024/incantesimi-G-L", voce="permessi",
                    copre=["carta:2024/spells.md#Legame di Protezione", "POST /characters/{char_id}/spells/{spell_id}/use", "GET /characters/{char_id}/spells"])
@pytest.mark.parametrize("su_di_se", [True, False], ids=["bersaglio_se_stesso", "senza_bersagli"])
async def test_legame_di_protezione_2024_non_si_lancia_su_se_stessi(client, su_di_se):
    cid = await _pg(client, "cleric", 3)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Legame di Protezione", "srd_index": "warding-bond", "level": 2})
    assert r.status_code == 201, r.text
    legame = r.json()["id"]
    slot = lambda scheda: next(s["available"] for s in scheda["spell_slots"] if s["level"] == 2)  # noqa: E731
    prima = slot((await client.get(f"/characters/{cid}")).json())
    corpo = {"slot_level": 2, **({"targets": [cid]} if su_di_se else {})}
    r = await client.post(f"/characters/{cid}/spells/{legame}/use", json=corpo)
    # «Tocchi un'altra creatura consenziente» (Warding Bond 2024): chi lancia non è un bersaglio valido
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text[:300]
    scheda = (await client.get(f"/characters/{cid}")).json()
    assert slot(scheda) == prima and not [s for s in scheda["active_states"] or [] if s["key"] == "spell:warding_bond"]
    # il foglio dei bersagli non offre «te stesso»
    effetto = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == legame)["effect"]
    assert effetto["not_self"] is True
