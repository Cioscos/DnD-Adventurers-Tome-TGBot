"""Controlli scritti dalla correzione del gruppo catalogo-incantesimi per i dubbi «Q-…» risolti come difetti."""
import pytest

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
