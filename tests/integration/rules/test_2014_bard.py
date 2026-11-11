"""Bardo 2014 (Task 20): progressione, Ispirazione Bardica, Factotum, Canto di Riposo, Controfascino, Maestria,
Segreti Magici e i due Collegi."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Character, SessionParticipant
from core.rules.catalog import features_for
from core.rules.spellcasting import known_limits, slots_for
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session

LORE = "Collegio della Sapienza"
VALOR = "Collegio del Valore"
BI = "bard.bardic_inspiration"
SONG = "bard.song_of_rest"
SKILLS = ("acrobatics", "arcana", "deception", "history", "insight")


async def _bard(client, level=5, subclass=None, **scores) -> int:
    body = {"name": "Bardo", "initial_class": {"class_name": "bard", "level": level, "subclass": subclass}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _ability(client, cid, key) -> dict | None:
    return next((a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == key), None)


async def _keys_of(client, cid) -> set[str]:
    return {a["feature_key"] for a in (await _full(client, cid))["abilities"]}


async def _use(client, cid, key, **body):
    return await client.post(f"/characters/{cid}/features/{key}/use", json=body)


async def _states(client, cid) -> list[dict]:
    return (await _full(client, cid))["active_states"] or []


async def _skills(client, cid, **levels) -> None:
    r = await client.patch(f"/characters/{cid}/skills", json={"skills": levels})
    assert r.status_code == 200, r.text


async def _roll_keys(client, cid, roll, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": roll, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _spells(client, cid) -> dict[str, dict]:
    return {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}


# ---------------------------------------------------------------------------
# Progressione e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,cantrips,known", [
    (1, 2, 4), (3, 2, 6), (4, 3, 7), (9, 3, 12), (10, 4, 14), (14, 4, 18), (17, 4, 20), (18, 4, 22), (20, 4, 22)])
def test_cantrips_and_known_spells_follow_the_class_table(level, cantrips, known):
    limits = known_limits("2014", "bard", level)
    assert (limits.cantrips, limits.spells) == (cantrips, known)


async def test_spell_slots_follow_the_full_caster_table(client):
    cid = await _bard(client, 5)
    slots = {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}
    assert slots == {1: 4, 2: 3, 3: 2}


async def test_hit_points_use_the_d8_and_follow_constitution(client):
    cid = await _bard(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 8
    assert full["hit_points"] == 8 + 5 + 5  # 8 + COS al 1°, poi la media 5 (COS 10)
    await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 14})
    assert (await _full(client, cid))["hit_points"] == 8 + 5 + 5 + 2 * 3


def test_multiclass_and_class_proficiencies_from_the_class_table():
    from core.rules.proficiencies import class_proficiencies

    first = class_proficiencies("2014", "bard", False)
    assert first.armor == ("light",) and set(first.weapons) == {
        "simple", "hand_crossbow", "longsword", "rapier", "shortsword"}
    assert set(first.saves) == {"dexterity", "charisma"} and first.skills_count == 3
    multi = class_proficiencies("2014", "bard", True)
    assert multi.armor == ("light",) and not multi.weapons and not multi.saves and multi.skills_count == 1


@pytest.mark.parametrize("level", [4, 8, 12, 16, 19])
async def test_asi_choice_is_pending_at_each_asi_level(client, level):
    cid = await _bard(client, level)
    levels = sorted(c["level"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi")
    assert levels == [lv for lv in (4, 8, 12, 16, 19) if lv <= level]


@pytest.mark.parametrize("level,present", [
    (1, {"bardic_inspiration"}), (2, {"jack_of_all_trades", "song_of_rest"}), (3, {"expertise"}),
    (5, {"font_of_inspiration"}), (6, {"countercharm"}), (10, {"magical_secrets"}), (20, {"superior_inspiration"}),
])
async def test_features_appear_at_their_level(client, level, present):
    cid = await _bard(client, level)
    assert {f"bard.{k}" for k in present} <= await _keys_of(client, cid)
    if level > 1:
        low = await _bard(client, level - 1)
        assert not {f"bard.{k}" for k in present} & await _keys_of(client, low)


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    cid = await _bard(client, 20, LORE)
    keys = await _keys_of(client, cid)
    assert not keys & {f"bard.{k}" for k in (
        "hit_points", "proficiencies", "equipment", "spellcasting", "bard_college", "ability_score_improvement",
        "multiclassing")}
    titles = {s.source_title for s in features_for("2014", "bard")}
    assert "Punti Ferita / Hit Points (Bardo 1, pag. 52)" in titles


async def test_college_features_need_the_recognised_subclass(client):
    lore, valor, none = await _bard(client, 14, LORE), await _bard(client, 14, VALOR), await _bard(client, 14, "Collegio Inventato")
    lore_keys, valor_keys = {"bard.cutting_words", "bard.peerless_skill"}, {"bard.combat_inspiration", "bard.battle_magic"}
    assert lore_keys <= await _keys_of(client, lore) and not valor_keys & await _keys_of(client, lore)
    assert valor_keys <= await _keys_of(client, valor) and not lore_keys & await _keys_of(client, valor)
    assert not (lore_keys | valor_keys) & await _keys_of(client, none)


# ---------------------------------------------------------------------------
# Ispirazione Bardica e Fonte di Ispirazione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,cha,uses,rest", [
    (1, 16, 3, "long_rest"), (1, 8, 1, "long_rest"), (4, 10, 1, "long_rest"), (4, 18, 4, "long_rest"),
    (5, 14, 2, "short_rest"), (5, 8, 1, "short_rest"), (15, 20, 5, "short_rest")])
async def test_inspiration_uses_follow_charisma_and_recharge_by_level(client, level, cha, uses, rest):
    cid = await _bard(client, level, charisma=cha)
    bi = await _ability(client, cid, BI)
    assert (bi["name"], bi["max_uses"], bi["uses"], bi["restoration_type"]) == ("Ispirazione Bardica", uses, uses, rest)


async def test_inspiration_max_follows_charisma_live(client):
    cid = await _bard(client, 3, charisma=10)
    assert (await _ability(client, cid, BI))["max_uses"] == 1
    await client.patch(f"/characters/{cid}/ability_scores/charisma", json={"value": 18})
    assert (await _ability(client, cid, BI))["max_uses"] == 4


@pytest.mark.parametrize("level,die", [(1, 6), (4, 6), (5, 8), (9, 8), (10, 10), (14, 10), (15, 12), (20, 12)])
async def test_inspiration_die_follows_the_level(client, level, die):
    cid = await _bard(client, level, charisma=16)
    r = await _use(client, cid, BI)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert (state["key"], state["data"]["die"], state["rounds_left"]) == ("bardic_inspiration", die, 100)


async def test_inspiration_spends_a_use_and_the_bonus_action_and_lasts_ten_minutes(client):
    cid = await _bard(client, 5, charisma=16)
    assert (await _use(client, cid, BI)).status_code == 200
    assert (await _ability(client, cid, BI))["uses"] == 2
    again = await _use(client, cid, BI)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    assert (await _ability(client, cid, BI))["uses"] == 2
    state = (await _states(client, cid))[0]
    assert state["data"]["others"] == [BI] and set(state["ends_on"]) == {"rest_short", "rest_long", "manual"}
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, BI)).status_code == 200
    assert len(await _states(client, cid)) == 1  # un solo dado alla volta: il nuovo rinnova lo stato


async def test_inspiration_at_zero_uses_is_refused_without_spending_the_bonus_action(client):
    cid = await _bard(client, 3, charisma=10)
    assert (await _use(client, cid, BI)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, BI)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"


async def test_inspiration_recharges_on_a_short_rest_only_from_level_5(client):
    low, high = await _bard(client, 4, charisma=16), await _bard(client, 5, charisma=16)
    for cid in (low, high):
        assert (await _use(client, cid, BI)).status_code == 200
        r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
        assert r.status_code == 200, r.text
    assert (await _ability(client, low, BI))["uses"] == 2
    assert (await _ability(client, high, BI))["uses"] == 3
    assert await _states(client, high) == []  # il riposo breve chiude il dado dato


async def test_valor_inspiration_lists_combat_inspiration_for_the_group(client):
    valor, lore = await _bard(client, 3, VALOR, charisma=16), await _bard(client, 3, LORE, charisma=16)
    await _use(client, valor, BI)
    await _use(client, lore, BI)
    assert (await _states(client, valor))[0]["data"]["others"] == [BI, "bard.combat_inspiration"]
    assert (await _states(client, lore))[0]["data"]["others"] == [BI]


# ---------------------------------------------------------------------------
# Factotum
# ---------------------------------------------------------------------------

async def test_jack_of_all_trades_adds_half_proficiency_once_to_every_check_without_it(client):
    cid = await _bard(client, 5, dexterity=10)  # competenza +3: metà = 1
    await _skills(client, cid, stealth=True, acrobatics="expert")
    stealth = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()
    expert = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10})).json()
    other = (await client.post(f"/characters/{cid}/skills/sleight_of_hand/roll", json={"die": 10})).json()
    assert (stealth["bonus"], expert["bonus"], other["bonus"]) == (3, 6, 1)
    pure = (await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 10})).json()
    assert pure["bonus"] == 1


async def test_jack_of_all_trades_starts_at_level_2(client):
    cid = await _bard(client, 1, dexterity=10)
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()["bonus"] == 0
    assert (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()["bonus"] == 0


@pytest.mark.parametrize("level,half", [(2, 1), (5, 1), (9, 2), (13, 2), (17, 3)])
async def test_jack_of_all_trades_counts_on_initiative_once(client, level, half):
    cid = await _bard(client, level, dexterity=14)  # +2
    roll = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    assert roll["bonus"] == 2 + half and "feature:bard.jack_of_all_trades" in roll["notes"]
    assert (await _full(client, cid))["initiative_bonus"] == 2 + half


async def test_jack_of_all_trades_counts_on_the_encounter_initiative(client, test_session_factory):
    sid, cid = await _bard_in_session(client, test_session_factory, 5)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    comb = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb['id']}/initiative", json={"die": 10})
    assert r.status_code == 200, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    assert pc["initiative"] == 10 + 3 + 1  # DES 16 + metà competenza


async def _bard_in_session(client, test_session_factory, level, owner=None):
    """Il PG di `seed_session` (DES 16, del giocatore) diventa un bardo."""
    sid, cid = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": level, "hit_die": 8})
    assert r.status_code == 201, r.text
    return sid, cid


# ---------------------------------------------------------------------------
# Canto di Riposo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,die", [(2, 6), (8, 6), (9, 8), (12, 8), (13, 10), (16, 10), (17, 12)])
async def test_song_of_rest_die_follows_the_level(client, level, die):
    cid = await _bard(client, level)
    r = await _use(client, cid, SONG)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["die"] == die
    ends = set((await _states(client, cid))[0]["ends_on"])
    assert ends == {"rest_long", "new_turn", "manual"}  # il riposo breve del bardo non lo chiude (I6)


async def _hurt(test_session_factory, cid, hp=5, maximum=40):
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.hit_points, char.current_hit_points = maximum, hp
        await s.commit()


async def _spend(client, cid, roll=4):
    cls = (await _full(client, cid))["classes"][0]
    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": cls["id"], "count": 1, "rolls": [roll]})
    assert r.status_code == 200, r.text
    return r.json()


async def test_song_of_rest_adds_one_die_to_a_friend_who_spends_hit_dice(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{hero}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    await _hurt(test_session_factory, hero)
    plain = await _spend(client, hero)
    assert plain["healed"] == 4 and plain["song_rolls"] == []

    as_user(GM_ID)
    bard = await _bard(client, 2)
    async with test_session_factory() as s:  # il bardo siede al tavolo
        gm = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        gm.character_id = bard
        await s.commit()
    assert (await _use(client, bard, SONG)).status_code == 200

    as_user(PLAYER_ID)
    first = await _spend(client, hero)
    assert len(first["song_rolls"]) == 1 and 1 <= first["song_rolls"][0] <= 6 and first["song_die"] == 6
    assert first["healed"] == 4 + first["song_rolls"][0]
    second = await _spend(client, hero)  # il dado extra è uno a testa per riposo
    assert second["song_rolls"] == [] and second["healed"] == 4
    await client.post(f"/characters/{hero}/rest", json={"rest_type": "short"})
    await _hurt(test_session_factory, hero)
    assert len((await _spend(client, hero))["song_rolls"]) == 1  # un nuovo riposo, un nuovo dado


async def test_song_of_rest_does_not_reach_a_character_outside_the_session(client, test_session_factory):
    as_user(GM_ID)
    bard = await _bard(client, 2)
    assert (await _use(client, bard, SONG)).status_code == 200
    stranger = await _bard(client, 3)
    await _hurt(test_session_factory, stranger)
    assert (await _spend(client, stranger))["song_rolls"] == []


async def test_song_of_rest_also_heals_the_bard_who_performs(client, test_session_factory):
    cid = await _bard(client, 9)
    await _hurt(test_session_factory, cid)
    await _use(client, cid, SONG)
    result = await _spend(client, cid)
    assert result["song_die"] == 8 and len(result["song_rolls"]) == 1 and 1 <= result["song_rolls"][0] <= 8


# ---------------------------------------------------------------------------
# Controfascino
# ---------------------------------------------------------------------------

async def test_countercharm_is_an_action_that_lasts_until_the_end_of_the_next_turn(client):
    cid = await _bard(client, 6)
    r = await _use(client, cid, "bard.countercharm")
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert (state["key"], state["rounds_left"]) == ("countercharm", 2)
    assert set(state["ends_on"]) == {"incapacitated", "rest_short", "rest_long", "manual"}  # M3: un riposo lo chiude
    assert state["data"]["others"] == ["bard.countercharm"]
    again = await _use(client, cid, "bard.countercharm")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_countercharm_option_on_saves_only_while_it_lasts_and_gives_advantage(client):
    cid = await _bard(client, 6)
    assert "bard.countercharm" not in await _roll_keys(client, cid, "save", ability="wisdom")
    await _use(client, cid, "bard.countercharm")
    assert "bard.countercharm" in await _roll_keys(client, cid, "save", ability="wisdom")
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll",
                          json={"die": 8, "options": ["bard.countercharm"]})
    assert r.json()["mode_applied"] == "advantage"


async def test_countercharm_ends_when_the_bard_is_incapacitated(client):
    cid = await _bard(client, 6)
    await _use(client, cid, "bard.countercharm")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert await _states(client, cid) == []


# ---------------------------------------------------------------------------
# Maestria e Segreti Magici
# ---------------------------------------------------------------------------

def _choice(full, group):
    return next((c for c in full["pending_choices"] if c.get("group") == group), None)


async def _resolve(client, cid, group, options):
    choice = _choice(await _full(client, cid), group)
    return await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                             json={"kind": "class_option", "options": options})


async def test_expertise_offers_proficient_skills_and_sets_them_to_expert(client):
    cid = await _bard(client, 3)
    await _skills(client, cid, **{s: True for s in SKILLS[:4]})
    choice = _choice(await _full(client, cid), "expertise")
    assert choice["count"] == 2 and {o["key"] for o in choice["options"]} == set(SKILLS[:4])
    assert choice["options"][0]["name"]["it"] and choice["options"][0]["name"]["en"]
    r = await _resolve(client, cid, "expertise", ["arcana", "history"])
    assert r.status_code == 200, r.text
    skills = r.json()["skills"]
    assert skills["arcana"] == "expert" and skills["history"] == "expert" and skills["acrobatics"] is True
    assert _choice(r.json(), "expertise") is None


async def test_expertise_refuses_a_skill_without_proficiency_or_already_expert(client):
    cid = await _bard(client, 3)
    await _skills(client, cid, acrobatics=True, arcana="expert", history=True)
    assert (await _resolve(client, cid, "expertise", ["acrobatics", "insight"])).status_code == 422
    assert (await _resolve(client, cid, "expertise", ["arcana", "acrobatics"])).status_code == 422
    assert (await _resolve(client, cid, "expertise", ["acrobatics", "history"])).status_code == 200


@pytest.mark.parametrize("level,count", [(3, 2), (9, 2), (10, 4)])
async def test_expertise_count_follows_the_levels(client, level, count):
    cid = await _bard(client, level)
    assert _choice(await _full(client, cid), "expertise")["count"] == count


async def test_second_expertise_excludes_the_skills_already_expert(client):
    cid = await _bard(client, 3)
    await _skills(client, cid, **{s: True for s in SKILLS})
    await _resolve(client, cid, "expertise", ["arcana", "history"])
    await client.patch(f"/characters/{cid}/classes/{(await _full(client, cid))['classes'][0]['id']}", json={"level": 10})
    choice = _choice(await _full(client, cid), "expertise")
    assert choice["count"] == 2 and {o["key"] for o in choice["options"]} == {"acrobatics", "deception", "insight"}


async def _add_spell(client, cid, name, level, **extra):
    return await client.post(f"/characters/{cid}/spells", json={"name": name, "level": level, **extra})


async def test_magical_secrets_pick_any_spell_up_to_the_castable_level(client):
    cid = await _bard(client, 10)
    choice = _choice(await _full(client, cid), "magical_secrets")
    assert choice["count"] == 2 and choice["spell_pick"] == {"free": False, "max_level": 5, "list": None}
    too_high = await _add_spell(client, cid, "Disintegrazione", 6, pick_id=choice["id"])
    assert too_high.status_code == 422 and too_high.json()["detail"]["code"] == "spell_pick_level"
    one = await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])
    assert one.status_code == 201, one.text
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    assert one.json()["class_id"] == bard_class
    left = _choice(await _full(client, cid), "magical_secrets")
    assert left["count"] == 1
    two = await _add_spell(client, cid, "Trucchetto altrui", 0, pick_id=left["id"])  # un trucchetto è ammesso
    assert two.status_code == 201, two.text
    full = await _full(client, cid)
    assert _choice(full, "magical_secrets") is None
    limits = full["spellcasting"]["limits"][0]
    assert (limits["known_count"], limits["cantrips_count"]) == (1, 1)  # contano nei conosciuti


async def test_magical_secrets_pick_refuses_a_wrong_choice_and_a_second_use(client):
    cid = await _bard(client, 10)
    assert (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id="inesistente")).status_code == 404
    choice = _choice(await _full(client, cid), "magical_secrets")
    assert (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])).status_code == 201
    assert (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])).status_code == 409  # già conosciuto
    assert (await _add_spell(client, cid, "Volare", 3, pick_id=choice["id"])).status_code == 201
    assert (await _add_spell(client, cid, "Fulmine", 3, pick_id=choice["id"])).status_code == 404  # scelta esaurita


@pytest.mark.parametrize("level,count", [(10, 2), (14, 4), (18, 6)])
async def test_magical_secrets_count_follows_the_levels(client, level, count):
    cid = await _bard(client, level)
    assert _choice(await _full(client, cid), "magical_secrets")["count"] == count


async def test_magical_secrets_is_absent_below_level_10(client):
    cid = await _bard(client, 9)
    assert _choice(await _full(client, cid), "magical_secrets") is None


# ---------------------------------------------------------------------------
# Superiore Ispirazione
# ---------------------------------------------------------------------------

async def test_superior_inspiration_is_offered_at_initiative_only_with_no_uses_left(client):
    cid = await _bard(client, 20, charisma=16)
    assert "bard.superior_inspiration" not in await _roll_keys(client, cid, "initiative")
    bi = await _ability(client, cid, BI)
    await client.patch(f"/characters/{cid}/abilities/{bi['id']}", json={"uses": 0})
    assert "bard.superior_inspiration" in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": ["bard.superior_inspiration"]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, BI))["uses"] == 1
    assert "bard.superior_inspiration" not in await _roll_keys(client, cid, "initiative")


async def test_superior_inspiration_in_the_encounter_initiative(client, test_session_factory):
    sid, cid = await _bard_in_session(client, test_session_factory, 20)
    bi = await _ability(client, cid, BI)
    await client.patch(f"/characters/{cid}/abilities/{bi['id']}", json={"uses": 0})
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    comb = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb['id']}/initiative",
                          json={"die": 8, "options": ["bard.superior_inspiration"]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, BI))["uses"] == 1


# ---------------------------------------------------------------------------
# Collegio della Sapienza
# ---------------------------------------------------------------------------

async def test_lore_bonus_proficiencies_pick_three_skills_not_yet_proficient(client):
    cid = await _bard(client, 3, LORE)
    await _skills(client, cid, acrobatics=True)
    choice = _choice(await _full(client, cid), "lore_skills")
    assert choice["count"] == 3 and "acrobatics" not in {o["key"] for o in choice["options"]}
    assert (await _resolve(client, cid, "lore_skills", ["acrobatics", "arcana", "history"])).status_code == 422
    r = await _resolve(client, cid, "lore_skills", ["arcana", "history", "insight"])
    assert r.status_code == 200, r.text
    assert all(r.json()["skills"][s] is True for s in ("arcana", "history", "insight"))
    assert _choice(r.json(), "lore_skills") is None


async def test_valor_has_no_bonus_skills_choice(client):
    cid = await _bard(client, 3, VALOR)
    assert _choice(await _full(client, cid), "lore_skills") is None


@pytest.mark.parametrize("level,die", [(3, 6), (5, 8), (10, 10), (15, 12)])
async def test_cutting_words_rolls_the_inspiration_die_and_spends_a_use_and_the_reaction(client, level, die):
    cid = await _bard(client, level, LORE, charisma=16)
    r = await _use(client, cid, "bard.cutting_words")
    assert r.status_code == 200, r.text
    rolls = r.json()["rolls"]
    assert len(rolls) == 1 and 1 <= rolls[0] <= die
    assert (await _ability(client, cid, BI))["uses"] == (await _ability(client, cid, BI))["max_uses"] - 1
    turn = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turn["reaction_used"] is True and turn["bonus_used"] is False
    again = await _use(client, cid, "bard.cutting_words")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_cutting_words_without_inspiration_uses_is_refused_and_keeps_the_reaction(client):
    cid = await _bard(client, 3, LORE, charisma=10)
    await _use(client, cid, BI)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, "bard.cutting_words")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["reaction_used"] is False


async def test_cutting_words_is_not_a_valor_feature(client):
    cid = await _bard(client, 3, VALOR, charisma=16)
    assert (await _use(client, cid, "bard.cutting_words")).status_code == 404


async def test_peerless_skill_adds_the_die_after_the_roll_and_spends_a_use(client):
    cid = await _bard(client, 14, LORE, charisma=16)
    assert "bard.peerless_skill" not in await _roll_keys(client, cid, "attack")
    assert "bard.peerless_skill" not in await _roll_keys(client, cid, "save", ability="wisdom")
    first = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5})).json()
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "athletics"})).json()
    peerless = next(o for o in options if o["key"] == "bard.peerless_skill")
    assert peerless["phase"] == "after_roll"
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["bard.peerless_skill"]})
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 10  # d10 al 14°
    assert r.json()["total"] == first["total"] + extra["extra_total"]
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"] - 1


async def test_peerless_skill_on_the_initiative_and_without_uses(client):
    cid = await _bard(client, 14, LORE, charisma=16)
    assert "bard.peerless_skill" in await _roll_keys(client, cid, "initiative")
    bi = await _ability(client, cid, BI)
    await client.patch(f"/characters/{cid}/abilities/{bi['id']}", json={"uses": 0})
    assert "bard.peerless_skill" not in await _roll_keys(client, cid, "initiative")
    assert "bard.peerless_skill" not in await _roll_keys(client, cid, "skill", skill="athletics")


async def test_additional_magical_secrets_do_not_count_among_the_known_spells(client):
    cid = await _bard(client, 6, LORE)
    choice = _choice(await _full(client, cid), "additional_secrets")
    assert choice["count"] == 2 and choice["spell_pick"] == {"free": True, "max_level": 3, "list": None}
    await _add_spell(client, cid, "Incantesimo base", 1)
    assert (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])).status_code == 201
    left = _choice(await _full(client, cid), "additional_secrets")
    assert (await _add_spell(client, cid, "Trucchetto altrui", 0, pick_id=left["id"])).status_code == 201
    full = await _full(client, cid)
    limits = full["spellcasting"]["limits"][0]
    assert (limits["known_count"], limits["cantrips_count"]) == (1, 0)  # solo quello scelto a mano
    assert _choice(full, "additional_secrets") is None
    names = await _spells(client, cid)
    assert names["Palla di fuoco"]["class_id"] == full["classes"][0]["id"]


async def test_additional_magical_secrets_come_with_the_lore_college_at_level_6(client):
    assert _choice(await _full(client, await _bard(client, 5, LORE)), "additional_secrets") is None
    assert _choice(await _full(client, await _bard(client, 6, VALOR)), "additional_secrets") is None


# ---------------------------------------------------------------------------
# Collegio del Valore
# ---------------------------------------------------------------------------

async def test_valor_bonus_proficiencies_grant_medium_armor_shields_and_martial_weapons(client):
    valor, lore = await _bard(client, 3, VALOR), await _bard(client, 3, LORE)
    got = (await _full(client, valor))["general_proficiencies"]
    assert {"Armature medie", "Scudi"} <= set(got["armor"]) and "Armi da guerra" in got["weapons"]
    plain = (await _full(client, lore))["general_proficiencies"]
    assert "Armature medie" not in plain["armor"] and "Armi da guerra" not in plain["weapons"]


async def test_valor_extra_attack_is_two_from_level_6_and_does_not_stack(client):
    five, six, lore = await _bard(client, 5, VALOR), await _bard(client, 6, VALOR), await _bard(client, 6, LORE)
    attacks = {c: (await client.get(f"/characters/{c}/turn-state")).json()["attacks_allowed"] for c in (five, six, lore)}
    assert attacks == {five: 1, six: 2, lore: 1}
    r = await client.post(f"/characters/{six}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201
    assert (await client.get(f"/characters/{six}/turn-state")).json()["attacks_allowed"] == 2


async def _sword(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == "Spada")
    r = await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    return wid


async def test_battle_magic_after_a_bard_spell_cast_with_the_action(client):
    cid = await _bard(client, 14, VALOR)
    sword = await _sword(client, cid)
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    spell = (await _add_spell(client, cid, "Dardo", 0, casting_time="1 azione", class_id=bard_class)).json()
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})
    assert r.status_code == 200, r.text
    assert "bard.battle_magic" in await _roll_keys(client, cid, "attack", item_id=sword)
    r = await client.post(f"/characters/{cid}/items/{sword}/attack",
                          json={"die": 10, "options": ["bard.battle_magic"]})
    assert r.status_code == 200, r.text
    turn = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turn["bonus_used"] is True and turn["attacks_made"] == 1 and turn["action_attacks"] == 0
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)  # l'azione bonus è spesa


async def test_battle_magic_needs_a_bard_spell_cast_with_the_action(client):
    cid = await _bard(client, 14, VALOR)
    sword = await _sword(client, cid)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    bonus = (await _add_spell(client, cid, "Parola", 0, casting_time="1 azione bonus", class_id=bard_class)).json()
    await client.post(f"/characters/{cid}/spells/{bonus['id']}/use", json={})
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.post(f"/characters/{cid}/turn/new")
    other = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    assert other.status_code == 201, other.text
    wizard_class = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"] == "wizard")
    foreign = (await _add_spell(client, cid, "Dardo magico", 0, casting_time="1 azione", class_id=wizard_class)).json()
    await client.post(f"/characters/{cid}/spells/{foreign['id']}/use", json={})
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)  # non è un incantesimo da bardo


async def test_battle_magic_marker_clears_with_a_new_turn(client):
    cid = await _bard(client, 14, VALOR)
    sword = await _sword(client, cid)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    spell = (await _add_spell(client, cid, "Dardo", 0, casting_time="1 azione", class_id=bard_class)).json()
    await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})
    await client.post(f"/characters/{cid}/turn/new")
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)


# ---------------------------------------------------------------------------
# Export, import e Beyond
# ---------------------------------------------------------------------------

async def test_free_known_spells_survive_export_and_import(client):
    cid = await _bard(client, 6, LORE)
    choice = _choice(await _full(client, cid), "additional_secrets")
    await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])
    await _add_spell(client, cid, "Volare", 3, class_id=(await _full(client, cid))["classes"][0]["id"])
    exported = (await client.get(f"/characters/{cid}/export")).json()
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    copy = await _full(client, r.json()["id"])
    assert (copy["spellcasting"]["limits"][0]["known_count"]) == 1


async def test_beyond_skill_names_do_not_break_the_class_option_import(test_session_factory):
    from api.services.ddb_import import apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2014", "classes": [("Bardo", 6, LORE, 8)]}
        char = await build_rules_character(s, spec, 1)
        report = ImportReport()
        apply_class_options(char, [{"class_index": 0, "name": n} for n in ("Stealth", "Mystery")], report, "it")
        assert [e.name for e in report.approximated] == ["Mystery"]  # il nome dell'abilità non rompe nulla, l'altro si segnala
