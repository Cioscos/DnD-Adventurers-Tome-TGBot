"""Incantesimi per classe ed edizione attraverso l'API: pool, classe, limiti, conferme, fasi `cast` e `after_damage`."""
from __future__ import annotations

from core.rules.catalog import granted_spells
from core.rules.catalog.granted_spells import GrantedSpell
from core.rules.types import Cost, FeatureSpec, RollOptionSpec, Uses

_LABEL = {"it": "Applica?", "en": "Apply?"}
TWIN = RollOptionSpec(key="twin", phase="before", rolls=("cast",), label=_LABEL, cost=Cost(feature_key="wizard.prova"),
                      effect=lambda _c, _i: {"it": "Secondo bersaglio", "en": "Second target"})
EMPOWERED = RollOptionSpec(key="empowered", phase="after_damage", rolls=("spell_damage",), label=_LABEL,
                           cost=Cost(feature_key="wizard.prova"), reroll_dice=lambda _c, _i: 2)
BOMBARD = RollOptionSpec(key="bombard", phase="after_damage", rolls=("spell_damage",), label=_LABEL,
                         reroll_dice=lambda _c, _i: 1, keep_rolled=True, once_per_turn=True)


def _feature(*options, **kw) -> FeatureSpec:
    return FeatureSpec(key="wizard.prova", class_key="wizard", edition="2014", level=1, source_title="Prova",
                       name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None,
                       uses=Uses(table={1: 3}), restoration="long_rest", roll_options=options, **kw)


async def _char(client, *classes, edition="2014", **scores) -> int:
    r = await client.post("/characters", json={"name": "Prova"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for name, level in classes:
        r = await client.post(f"/characters/{cid}/classes", json={"class_name": name, "level": level, "hit_die": 8})
        assert r.status_code == 201, r.text
    if edition != "2014":
        r = await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
        assert r.status_code == 200, r.text
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _spell(client, cid, **kw) -> dict:
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Prova", "level": 1, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def _full(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


def _code(r) -> str | None:
    return r.json()["detail"]["code"] if r.status_code in (400, 409, 422) and isinstance(r.json()["detail"], dict) else None


def _slot(full, level, pact=False) -> dict:
    return next(s for s in full["spell_slots"] if s["level"] == level and bool(s["is_pact"]) == pact)


# --- Pool ---------------------------------------------------------------------------------------------------------

async def test_pact_and_regular_slot_chosen_by_id(client):
    cid = await _char(client, ("warlock", 1), ("wizard", 1))
    spell = await _spell(client, cid)
    full = await _full(client, cid)
    pact, regular = _slot(full, 1, pact=True), _slot(full, 1)

    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_id": pact["id"]})
    assert r.status_code == 200, r.text
    assert (_slot(r.json(), 1, pact=True)["used"], _slot(r.json(), 1)["used"]) == (1, 0)

    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_id": regular["id"]})
    assert r.status_code == 200, r.text
    assert (_slot(r.json(), 1, pact=True)["used"], _slot(r.json(), 1)["used"]) == (1, 1)


async def test_slot_level_alone_falls_to_the_pool_with_room(client):
    """§19 n. 8: la prima riga esaurita non deve dare 400 se l'altra ha disponibilità."""
    cid = await _char(client, ("warlock", 1), ("wizard", 1))
    spell = await _spell(client, cid)
    for _ in range(3):  # Mago 1: due slot; Warlock 1: uno
        r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1})
        assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1})
    assert r.status_code == 400


async def test_slot_of_someone_else_refused(client):
    cid = await _char(client, ("wizard", 1))
    other = await _char(client, ("wizard", 1))
    spell = await _spell(client, cid)
    foreign = _slot(await _full(client, other), 1)
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_id": foreign["id"]})
    assert r.status_code == 400
    assert _slot(await _full(client, other), 1)["used"] == 0


async def test_slot_below_spell_level_refused(client):
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, level=3, damage_dice="8d6", attack_save="ATK")
    full = await _full(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1})
    assert r.status_code == 400
    assert _code(r) == "slot_too_low"
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_id": _slot(full, 2)["id"]})
    assert _code(r) == "slot_too_low"
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/attack", json={"slot_level": 2, "die": 10})
    assert _code(r) == "slot_too_low"
    assert all(s["used"] == 0 for s in (await _full(client, cid))["spell_slots"])
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 3})
    assert r.status_code == 200, r.text


async def test_cantrip_use_spends_nothing_and_starts_concentration(client):
    cid = await _char(client, ("wizard", 1))
    spell = await _spell(client, cid, level=0, is_concentration=True, duration="Concentrazione, fino a 1 minuto")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == spell["id"]
    assert all(s["used"] == 0 for s in r.json()["spell_slots"])


# --- Classe dell'incantesimo --------------------------------------------------------------------------------------

async def test_dc_uses_spell_class(client):
    cid = await _char(client, ("wizard", 5), ("cleric", 5), intelligence=18, wisdom=12)
    full = await _full(client, cid)
    cleric = next(c for c in full["classes"] if c["class_name"] == "cleric")
    pb = full["proficiency_bonus"]
    mine = await _spell(client, cid, class_id=cleric["id"], level=0, attack_save="ATK")
    legacy = await _spell(client, cid, name="Senza classe", level=0, attack_save="ATK")

    r = await client.post(f"/characters/{cid}/spells/{mine['id']}/attack", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_bonus"] == pb + 1
    assert r.json()["caster_class"] == "cleric"

    r = await client.post(f"/characters/{cid}/spells/{legacy['id']}/attack", json={"die": 10})
    assert r.json()["to_hit_bonus"] == pb + 4
    assert r.json()["caster_class"] == "wizard"

    spells = {s["id"]: s for s in (await _full(client, cid))["spells"]}
    assert spells[mine["id"]]["save_dc"] == 8 + pb + 1
    assert spells[legacy["id"]]["save_dc"] == 8 + pb + 4
    listed = (await client.get(f"/characters/{cid}/spells")).json()
    assert next(s for s in listed if s["id"] == mine["id"])["attack_bonus"] == pb + 1


async def test_class_of_another_character_refused(client):
    cid = await _char(client, ("wizard", 1))
    other = await _char(client, ("cleric", 1))
    foreign = (await _full(client, other))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "X", "level": 1, "class_id": foreign})
    assert r.status_code == 400
    spell = await _spell(client, cid)
    r = await client.patch(f"/characters/{cid}/spells/{spell['id']}", json={"class_id": foreign})
    assert r.status_code == 400


async def test_removing_the_class_keeps_the_spell(client):
    cid = await _char(client, ("wizard", 3), ("cleric", 3))
    cleric = next(c for c in (await _full(client, cid))["classes"] if c["class_name"] == "cleric")
    spell = await _spell(client, cid, class_id=cleric["id"])
    r = await client.delete(f"/characters/{cid}/classes/{cleric['id']}")
    assert r.status_code in (200, 204), r.text
    survived = next(s for s in (await _full(client, cid))["spells"] if s["id"] == spell["id"])
    assert survived["class_id"] is None


async def test_export_keeps_class_and_always_prepared(client):
    cid = await _char(client, ("wizard", 3), ("cleric", 3))
    cleric = next(c for c in (await _full(client, cid))["classes"] if c["class_name"] == "cleric")
    await _spell(client, cid, class_id=cleric["id"], always_prepared=True)
    exported = await client.get(f"/characters/{cid}/export")
    assert exported.status_code == 200, exported.text
    r = await client.post("/characters/import", json=exported.json())
    assert r.status_code == 201, r.text
    copy = r.json()
    spell = copy["spells"][0]
    assert spell["always_prepared"] is True
    assert next(c for c in copy["classes"] if c["id"] == spell["class_id"])["class_name"] == "cleric"


# --- Personaggi esistenti e cambio di edizione ----------------------------------------------------------------------

async def test_existing_character_keeps_slots_and_spells_on_recalc(client, test_session_factory):
    """`class_id` nullo: stessi slot e stessa CD di prima, senza scelta dell'utente."""
    cid = await _char(client, ("paladin", 3), ("wizard", 1), intelligence=16)
    spell = await _spell(client, cid, is_prepared=True)
    await client.patch(f"/characters/{cid}", json={"name": "Altro nome"})
    full = await _full(client, cid)
    assert {s["level"]: s["total"] for s in full["spell_slots"]} == {1: 3}
    got = next(s for s in full["spells"] if s["id"] == spell["id"])
    assert (got["class_id"], got["always_prepared"]) == (None, False)


async def test_edition_switch_keeps_spent_slots_and_spells(client):
    cid = await _char(client, ("paladin", 5), ("wizard", 1))
    spell = await _spell(client, cid)
    full = await _full(client, cid)
    assert {s["level"]: s["total"] for s in full["spell_slots"]} == {1: 4, 2: 2}  # combinato 2014: 2 + 1 = 3
    for level, used in ((1, 3), (2, 2)):
        r = await client.patch(f"/characters/{cid}/spell_slots/{_slot(full, level)['id']}", json={"used": used})
        assert r.status_code == 200, r.text

    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    assert r.status_code == 200, r.text
    assert {s["level"]: (s["total"], s["used"]) for s in r.json()["spell_slots"]} == {1: (4, 3), 2: (3, 2)}
    assert [s["id"] for s in r.json()["spells"]] == [spell["id"]]

    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})
    assert {s["level"]: (s["total"], s["used"]) for s in r.json()["spell_slots"]} == {1: (4, 3), 2: (2, 2)}
    assert [s["id"] for s in r.json()["spells"]] == [spell["id"]]


async def test_manual_slots_untouched_by_edition_switch(client):
    cid = await _char(client, ("paladin", 1))
    await client.patch(f"/characters/{cid}", json={"settings": {"spell_slots_mode": "manual"}})
    r = await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 5})
    assert r.status_code == 201, r.text
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    assert {s["level"]: s["total"] for s in r.json()["spell_slots"]} == {3: 5}


# --- Preparati ------------------------------------------------------------------------------------------------------

async def test_always_prepared_not_counted_and_not_removable(client):
    cid = await _char(client, ("cleric", 1), wisdom=10)  # tetto 1
    always = await _spell(client, cid, name="Dominio", always_prepared=True)
    assert always["is_prepared"] is True
    info = (await _full(client, cid))["spellcasting"]
    assert (info["prepared_count"], info["prepared_cap"]) == (0, 1)

    normal = await _spell(client, cid, name="Normale")
    r = await client.patch(f"/characters/{cid}/spells/{normal['id']}", json={"is_prepared": True})
    assert r.status_code == 200, r.text  # il sempre preparato non occupa il posto

    r = await client.patch(f"/characters/{cid}/spells/{always['id']}", json={"is_prepared": False})
    assert r.status_code == 400
    assert _code(r) == "always_prepared"
    r = await client.patch(f"/characters/{cid}/spells/{always['id']}", json={"always_prepared": False, "is_prepared": False})
    assert r.status_code == 200, r.text  # togliere il segno resta una scelta dell'utente


async def test_prepared_cap_per_class_when_assigned(client):
    cid = await _char(client, ("wizard", 1), ("cleric", 1), intelligence=18, wisdom=10, edition="2024")
    full = await _full(client, cid)
    cleric = next(c for c in full["classes"] if c["class_name"] == "cleric")
    assert full["spellcasting"]["prepared_cap"] == 8  # 4 + 4 dalle tabelle 2024
    limits = {x["class_id"]: x for x in full["spellcasting"]["limits"]}
    assert limits[cleric["id"]]["prepared_limit"] == 4
    for i in range(4):
        s = await _spell(client, cid, name=f"C{i}", class_id=cleric["id"])
        r = await client.patch(f"/characters/{cid}/spells/{s['id']}", json={"is_prepared": True})
        assert r.status_code == 200, r.text
    s = await _spell(client, cid, name="C4", class_id=cleric["id"])
    r = await client.patch(f"/characters/{cid}/spells/{s['id']}", json={"is_prepared": True})
    assert r.status_code == 400  # il tetto di quella classe, anche se il totale ha posto
    limits = {x["class_id"]: x for x in (await _full(client, cid))["spellcasting"]["limits"]}
    assert limits[cleric["id"]]["prepared_count"] == 4


async def test_limits_2014_known_caster_and_cantrips(client):
    cid = await _char(client, ("bard", 4))
    await _spell(client, cid, name="T", level=0)
    await _spell(client, cid, name="L")
    full = await _full(client, cid)
    assert full["spellcasting"]["has_preparing_class"] is False
    row = full["spellcasting"]["limits"][0]
    assert (row["cantrips_count"], row["cantrips_limit"], row["known_count"], row["known_limit"]) == (1, 3, 1, 7)
    assert row["prepared_limit"] is None


async def test_limits_ignore_custom_classes(client):
    cid = await _char(client, ("Classe inventata", 5))
    assert (await _full(client, cid))["spellcasting"]["limits"] == []


async def test_all_casters_prepare_in_2024(client):
    cid = await _char(client, ("bard", 5), edition="2024")
    info = (await _full(client, cid))["spellcasting"]
    assert (info["has_preparing_class"], info["prepared_cap"]) == (True, 9)
    assert info["limits"][0]["known_limit"] is None


async def test_manual_cap_hides_per_class_limit(client):
    cid = await _char(client, ("cleric", 3))
    await client.patch(f"/characters/{cid}", json={"settings": {"prepared_cap_mode": "manual", "prepared_cap_value": 9}})
    info = (await _full(client, cid))["spellcasting"]
    assert info["prepared_cap"] == 9
    assert info["limits"][0]["prepared_limit"] is None


# --- Rituali --------------------------------------------------------------------------------------------------------

async def test_ritual_2014_classes_2024_any_prepared(client):
    paladin14 = await _char(client, ("paladin", 5))
    spell = await _spell(client, paladin14, is_ritual=True, is_prepared=True)
    r = await client.post(f"/characters/{paladin14}/spells/{spell['id']}/use", json={"as_ritual": True})
    assert r.status_code == 400

    paladin24 = await _char(client, ("paladin", 5), edition="2024", charisma=16)
    spell = await _spell(client, paladin24, is_ritual=True, is_prepared=True)
    r = await client.post(f"/characters/{paladin24}/spells/{spell['id']}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text
    assert (await _full(client, paladin24))["spellcasting"]["has_ritual_caster"] is True

    other = await _spell(client, paladin24, name="Non preparato", is_ritual=True)
    r = await client.post(f"/characters/{paladin24}/spells/{other['id']}/use", json={"as_ritual": True})
    assert r.status_code == 409
    assert _code(r) == "cast_confirm"
    assert r.json()["detail"]["warnings"] == ["ritual_unprepared"]
    r = await client.post(f"/characters/{paladin24}/spells/{other['id']}/use",
                          json={"as_ritual": True, "confirm": ["ritual_unprepared"]})
    assert r.status_code == 200, r.text

    wizard24 = await _char(client, ("wizard", 3), edition="2024")
    book = await _spell(client, wizard24, is_ritual=True)
    r = await client.post(f"/characters/{wizard24}/spells/{book['id']}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text

    cleric14 = await _char(client, ("cleric", 3), wisdom=14)
    spell = await _spell(client, cleric14, is_ritual=True)
    r = await client.post(f"/characters/{cleric14}/spells/{spell['id']}/use", json={"as_ritual": True})
    assert r.status_code == 409


async def test_ritual_caster_feat_2014_allows_rituals(client, test_session_factory):
    from core.db.models import Ability
    cid = await _char(client, ("paladin", 5))
    spell = await _spell(client, cid, is_ritual=True, is_prepared=True)
    async with test_session_factory() as s:
        s.add(Ability(character_id=cid, name="Incantatore Rituale", feature_key="feat.ritual_caster", is_active=True))
        await s.commit()
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text


# --- Danno e concentrazione -----------------------------------------------------------------------------------------

async def test_half_damage_rounds_down(client):
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, damage_dice="1d6", attack_save="SAVE")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={"main_rolls": [5]})
    assert r.status_code == 200, r.text
    assert (r.json()["total"], r.json()["half_damage"]) == (5, 2)


async def test_concentration_rounds_kept_after_cast(client):
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, is_concentration=True, duration="Concentrazione, fino a 1 minuto")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["concentration_rounds_left"] == 10
    # Un client che richiama il PATCH senza `rounds` sullo stesso incantesimo non azzera il contatore.
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["concentration_rounds_left"] == 10


async def test_concentration_started_by_hand_reads_the_duration(client):
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, is_concentration=True, duration="Concentrazione, fino a 1 minuto")
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell["id"]})
    assert r.json()["settings"]["concentration_rounds_left"] == 10


async def _concentrating(client, cid) -> None:
    spell = await _spell(client, cid, name="Conc", level=0, is_concentration=True)
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})
    assert r.status_code == 200, r.text


async def test_concentration_dc_capped_30_only_2024(client):
    new = await _char(client, ("wizard", 5), edition="2024")
    await _concentrating(client, new)
    r = await client.post(f"/characters/{new}/concentration/save", json={"damage": 100})
    assert r.status_code == 200, r.text
    assert r.json()["dc"] == 30
    old = await _char(client, ("wizard", 5))
    await _concentrating(client, old)
    r = await client.post(f"/characters/{old}/concentration/save", json={"damage": 100})
    assert r.json()["dc"] == 50


# --- Conferme al lancio ---------------------------------------------------------------------------------------------

async def test_one_slot_spell_per_turn_2024_confirm(client):
    cid = await _char(client, ("wizard", 5), edition="2024")
    spell = await _spell(client, cid)
    url = f"/characters/{cid}/spells/{spell['id']}/use"
    r = await client.post(url, json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "spell_slot", "used": True})).status_code == 409

    r = await client.post(url, json={"slot_level": 1})
    assert r.status_code == 409
    assert r.json()["detail"]["warnings"] == ["one_slot_per_turn"]
    assert _slot(await _full(client, cid), 1)["used"] == 1

    check = await client.get(f"/characters/{cid}/spells/{spell['id']}/cast-check")
    assert check.json() == ["one_slot_per_turn"]

    r = await client.post(url, json={"slot_level": 1, "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    assert _slot(r.json(), 1)["used"] == 2

    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.post(url, json={"slot_level": 1})).status_code == 200


async def test_spell_attack_marks_slot_and_reroll_does_not_recast(client):
    cid = await _char(client, ("wizard", 5), edition="2024")
    spell = await _spell(client, cid, attack_save="ATK")
    url = f"/characters/{cid}/spells/{spell['id']}/attack"
    r = await client.post(url, json={"slot_level": 1, "die": 10})
    assert r.status_code == 200, r.text
    r = await client.post(url, json={"slot_level": 1, "die": 10})
    assert r.status_code == 409
    assert r.json()["detail"]["warnings"] == ["one_slot_per_turn"]


async def test_two_action_spells_allowed_2014_bonus_rule_confirmed(client):
    cid = await _char(client, ("wizard", 5))
    action = await _spell(client, cid, casting_time="1 azione")
    bonus = await _spell(client, cid, name="Bonus", casting_time="1 azione bonus")
    cantrip = await _spell(client, cid, name="Trucco", level=0, casting_time="1 azione")
    assert (await client.post(f"/characters/{cid}/spells/{action['id']}/use", json={"slot_level": 1})).status_code == 200
    assert (await client.post(f"/characters/{cid}/spells/{action['id']}/use", json={"slot_level": 1})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{bonus['id']}/use", json={"slot_level": 1})
    assert r.status_code == 409
    assert r.json()["detail"]["warnings"] == ["bonus_spell"]
    r = await client.post(f"/characters/{cid}/spells/{bonus['id']}/use", json={"slot_level": 1, "confirm": ["bonus_spell"]})
    assert r.status_code == 200, r.text
    assert (await client.post(f"/characters/{cid}/spells/{cantrip['id']}/use", json={})).status_code == 200


async def test_armor_without_training_blocks_cast_with_confirm(client):
    cid = await _char(client, ("wizard", 5))
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Piastre", "item_type": "armor", "is_equipped": True,
        "item_metadata": {"armor_type": "heavy", "ac_value": 18}})
    assert r.status_code == 201, r.text
    item = next(i for i in r.json()["items"] if i["name"] == "Piastre")
    if not item["is_equipped"]:
        r = await client.patch(f"/characters/{cid}/items/{item['id']}", json={"is_equipped": True, "equipment_slot": "body"})
        assert r.status_code == 200, r.text
    spell = await _spell(client, cid, attack_save="ATK")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1})
    assert r.status_code == 409
    assert r.json()["detail"]["warnings"] == ["armor"]
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/attack", json={"slot_level": 1, "die": 10})
    assert r.status_code == 409
    assert _slot(await _full(client, cid), 1)["used"] == 0
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1, "confirm": ["armor"]})
    assert r.status_code == 200, r.text
    assert _slot(r.json(), 1)["used"] == 1


# --- Fase `cast` ----------------------------------------------------------------------------------------------------

async def test_cast_options_listed_paid_and_reported(client, rules_catalog):
    rules_catalog(_feature(TWIN))
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid)
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "cast", "spell_id": spell["id"]})
    assert [o["key"] for o in listed.json()] == ["twin"]

    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1, "options": ["twin"]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["keys"] == ["twin"]
    assert r.json()["option_result"]["effects"] == [{"it": "Secondo bersaglio", "en": "Second target"}]
    assert next(a for a in r.json()["abilities"] if a["feature_key"] == "wizard.prova")["uses"] == 2


async def test_cast_option_on_spell_attack_uses_its_own_field(client, rules_catalog):
    rules_catalog(_feature(TWIN))
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, attack_save="ATK")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/attack",
                          json={"slot_level": 1, "die": 10, "cast_options": ["twin"]})
    assert r.status_code == 200, r.text
    assert r.json()["cast_option_result"]["keys"] == ["twin"]
    assert next(a for a in r.json()["character"]["abilities"] if a["feature_key"] == "wizard.prova")["uses"] == 2


async def test_unknown_cast_option_rolls_back_the_slot(client, rules_catalog):
    rules_catalog(_feature(TWIN))
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 1, "options": ["nope"]})
    assert r.status_code == 409
    assert _code(r) == "option_unavailable"
    assert _slot(await _full(client, cid), 1)["used"] == 0


# --- Fase `after_damage` --------------------------------------------------------------------------------------------

async def _damage(client, cid, spell, rolls) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={"main_rolls": rolls})
    assert r.status_code == 200, r.text
    return r.json()


async def test_after_damage_replaces_chosen_dice_on_server_state(client, rules_catalog, monkeypatch):
    rules_catalog(_feature(EMPOWERED))
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, damage_dice="3d6+2", attack_save="SAVE")
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "spell_damage", "spell_id": spell["id"]})
    option = next(o for o in listed.json() if o["key"] == "empowered")
    assert (option["phase"], option["reroll_limit"]) == ("after_damage", 2)

    first = await _damage(client, cid, spell, [1, 2, 6])
    assert first["total"] == 11
    monkeypatch.setattr("api.routers.spells.random.randint", lambda _a, _b: 5)
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["empowered"], "reroll": [0, 1]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["main_rolls"] == [5, 5, 6]
    assert (body["total"], body["half_damage"]) == (18, 9)
    assert body["option_result"]["keys"] == ["empowered"]
    assert next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "wizard.prova")["uses"] == 2


async def test_after_damage_limits_and_stale_state(client, rules_catalog):
    rules_catalog(_feature(EMPOWERED))
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, damage_dice="3d6", attack_save="SAVE")
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["empowered"], "reroll": [0]})
    assert r.status_code == 409
    assert _code(r) == "no_last_damage"

    await _damage(client, cid, spell, [1, 2, 3])
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["empowered"], "reroll": [0, 1, 2]})
    assert _code(r) == "bad_reroll"  # oltre il limite
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["empowered"], "reroll": [9]})
    assert _code(r) == "bad_reroll"
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["empowered"], "reroll": []})
    assert _code(r) == "bad_reroll"
    assert next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "wizard.prova")["uses"] == 3

    await client.post(f"/characters/{cid}/turn/new")
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["empowered"], "reroll": [0]})
    assert _code(r) == "no_last_damage"


async def test_after_damage_keep_rolled_needs_a_max_die_and_adds(client, rules_catalog, monkeypatch):
    rules_catalog(_feature(BOMBARD))
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, damage_dice="2d8", attack_save="SAVE")
    await _damage(client, cid, spell, [3, 8])
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["bombard"], "reroll": [0]})
    assert _code(r) == "bad_reroll"  # il dado non mostra il massimo
    monkeypatch.setattr("api.routers.spells.random.randint", lambda _a, _b: 4)
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["bombard"], "reroll": [1]})
    assert r.status_code == 200, r.text
    assert (r.json()["total"], r.json()["rolls"]) == (15, [3, 8, 4])
    assert r.json()["main_rolls"] == [3, 8]
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["bombard"], "reroll": [1]})
    assert _code(r) == "option_unavailable"  # una volta per turno


async def test_after_damage_reports_multiplier_and_extra_dice(client, rules_catalog, monkeypatch):
    rules_catalog(_feature(EMPOWERED))
    cid = await _char(client, ("wizard", 5))
    spell = await _spell(client, cid, damage_dice="1d6", attack_save="SAVE")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage",
                          json={"main_rolls": [1], "extra_dice": "1d4", "extra_rolls": [2]})
    assert r.status_code == 200, r.text
    monkeypatch.setattr("api.routers.spells.random.randint", lambda _a, _b: 3)
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["empowered"], "reroll": [1]})
    assert r.status_code == 200, r.text
    assert (r.json()["main_rolls"], r.json()["extra_rolls"], r.json()["total"]) == ([1], [3], 4)


# --- Incantesimi concessi dai privilegi (D4, D6) ---------------------------------------------------------------------

async def test_granted_spell_appears_always_prepared_and_survives_edition_switch(client, rules_catalog, monkeypatch):
    monkeypatch.setitem(granted_spells.GRANTED_SPELLS, "prova-concesso", GrantedSpell(
        key="prova-concesso", name={"it": "Concesso", "en": "Granted"}, level=1))
    rules_catalog(_feature(granted_spells=("prova-concesso",)))
    cid = await _char(client, ("wizard", 3), intelligence=10)
    full = await _full(client, cid)
    wizard = full["classes"][0]["id"]
    spell = next(s for s in full["spells"] if s["srd_index"] == "prova-concesso")
    assert (spell["always_prepared"], spell["is_prepared"], spell["class_id"]) == (True, True, wizard)
    assert full["spellcasting"]["prepared_count"] == 0

    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    assert r.status_code == 200, r.text
    moved = next(s for s in r.json()["spells"] if s["srd_index"] == "prova-concesso")
    assert moved["always_prepared"] is False  # il privilegio non c'è più: resta, ma conta come gli altri

    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})
    back = [s for s in r.json()["spells"] if s["srd_index"] == "prova-concesso"]
    assert len(back) == 1
    assert back[0]["always_prepared"] is True


async def test_granted_spell_reuses_the_one_the_player_already_has(client, rules_catalog, monkeypatch):
    monkeypatch.setitem(granted_spells.GRANTED_SPELLS, "prova-concesso", GrantedSpell(
        key="prova-concesso", name={"it": "Concesso", "en": "Granted"}, level=1))
    cid = await _char(client, ("wizard", 3))
    mine = await _spell(client, cid, name="Il mio testo", srd_index="prova-concesso", description="Mie note")
    rules_catalog(_feature(granted_spells=("prova-concesso",)))
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})
    assert r.status_code == 200, r.text
    found = [s for s in r.json()["spells"] if s["srd_index"] == "prova-concesso"]
    assert [s["id"] for s in found] == [mine["id"]]
    assert (found[0]["description"], found[0]["always_prepared"]) == ("Mie note", True)


# --- Migrazione -----------------------------------------------------------------------------------------------------

def test_migrations_declare_the_new_columns():
    from core.db.engine import _MIGRATIONS
    columns = {(t, c): d for t, c, _, d in _MIGRATIONS}
    assert ("spells", "class_id") in columns
    assert columns[("spells", "always_prepared")] == "0"
