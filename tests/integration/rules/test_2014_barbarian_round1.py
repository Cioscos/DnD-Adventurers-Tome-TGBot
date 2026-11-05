"""Giro 1 della revisione del Task 19: il Barbaro 2014 dopo i rilievi."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_barbarian import (
    BERSERKER, RAGE, TOTEM, _ability, _armor, _attack, _barbarian, _full, _hit, _hp, _keys, _pick, _rage, _states,
    _turn, _weapon,
)


async def _totem_barbarian(client, level, spirit=None, aspect=None, attunement=None, **scores) -> int:
    cid = await _barbarian(client, level, TOTEM, **scores)
    for group, animal in (("totem_spirit", spirit), ("totem_aspect", aspect), ("totem_attunement", attunement)):
        if animal:
            await _pick(client, cid, group, animal)
    return cid


# ---------------------------------------------------------------------------
# I4: i totem non chiedono l'armatura che il manuale non chiede
# ---------------------------------------------------------------------------

async def test_bear_resistance_and_the_14th_level_totems_work_in_heavy_armor(client):
    cid = await _totem_barbarian(client, 14, spirit="bear", attunement="eagle", strength=18)
    await _armor(client, cid, "heavy")
    await _rage(client, cid)
    full = await _full(client, cid)
    assert {"slashing", "fire", "cold"} <= set(full["computed"]["resistances"])  # Orso 3: solo «in ira»
    assert full["computed"]["fly_speed"] == full["computed"]["speed"]  # Aquila 14: idem
    assert "psychic" not in full["computed"]["resistances"]
    wolf = await _totem_barbarian(client, 14, spirit="wolf", attunement="wolf", strength=18)
    await _armor(client, wolf, "heavy")
    await _rage(client, wolf)
    await client.post(f"/characters/{wolf}/turn/new")  # l'ira ha speso la bonus: il Lupo 14 ne ha bisogno
    sword = await _weapon(client, wolf)
    assert "barbarian.attunement_wolf_knock" in await _keys(client, wolf, "attack", item_id=sword)  # Lupo 14


async def test_eagle_dash_and_rage_benefits_still_need_no_heavy_armor(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 10)  # svantaggio: il secondo d20 è fisso, il colpo riesce
    cid = await _totem_barbarian(client, 14, spirit="eagle", strength=18)
    await _armor(client, cid, "heavy")
    await _rage(client, cid)
    eagle = await client.post(f"/characters/{cid}/features/barbarian.totem_eagle/use", json={})
    assert eagle.status_code == 409  # Aquila 3: «e non indossa un'armatura pesante»
    sword = await _weapon(client, cid)
    assert (await _attack(client, cid, sword))["damage_bonus"] == (await _attack(client, cid, sword))["damage_bonus"]


# ---------------------------------------------------------------------------
# I5: i PF creando direttamente al 20°
# ---------------------------------------------------------------------------

async def test_hit_points_of_a_barbarian_created_at_level_20_match_climbing(client):
    low = await _barbarian(client, 19)
    top = await _barbarian(client, 20)
    assert (await _full(client, low))["hit_points"] == 12 + 18 * 7  # CON 10
    # CON 10 + 4 = 14 (+2) su ognuno dei 20 livelli: 12 + 2 al 1°, poi 19 × (7 + 2)
    assert (await _full(client, top))["hit_points"] == 12 + 2 + 19 * (7 + 2) == 185


# ---------------------------------------------------------------------------
# I9: annullare riporta anche la spossatezza di Frenesia
# ---------------------------------------------------------------------------

async def test_undoing_the_hit_that_ended_a_frenzy_rage_takes_back_the_exhaustion(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 1)
    cid = await _barbarian(client, 11, BERSERKER, constitution=10)
    await _hp(client, cid)
    await _rage(client, cid, frenzy=True)
    body = await _hit(client, cid, 45)  # TS di Ira Implacabile fallito: a terra, l'ira finisce
    assert body["conditions"]["exhaustion"] == 1 and body["active_states"] == []
    undone = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": body["hp_undo_id"]})
    assert undone.status_code == 200, undone.text
    assert not (undone.json()["conditions"] or {}).get("exhaustion")
    assert [s["key"] for s in undone.json()["active_states"]] == ["rage"]


# ---------------------------------------------------------------------------
# I10: terminare l'ira è un'azione bonus
# ---------------------------------------------------------------------------

async def test_ending_the_rage_spends_the_bonus_action_but_never_refuses(client):
    cid = await _barbarian(client, 5)
    await _rage(client, cid)
    assert (await _turn(client, cid))["bonus_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _turn(client, cid))["bonus_used"] is False
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True
    await _rage(client, cid)  # (la bonus è speso: serve un nuovo turno)
    await client.post(f"/characters/{cid}/turn/new")
    await _rage(client, cid)
    assert await _states(client, cid) != []
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200  # con la bonus già spesa


# ---------------------------------------------------------------------------
# I11: Frenesia e Ritorsione
# ---------------------------------------------------------------------------

async def test_frenzy_attack_after_the_attack_action_does_not_need_the_extra_attack_confirmation(client):
    cid = await _barbarian(client, 3, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    await _rage(client, cid, frenzy=True)
    await client.post(f"/characters/{cid}/turn/new")
    url = f"/characters/{cid}/items/{sword}/attack"
    assert (await client.post(url, json={"die": 10})).status_code == 200  # l'azione Attacco
    assert (await client.post(url, json={"die": 10})).status_code == 409  # un secondo senza Frenesia: oltre il limite
    r = await client.post(url, json={"die": 10, "options": ["barbarian.frenzy_attack"]})  # come fa il client
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_retaliation_attack_without_confirmation_once_the_attack_limit_is_spent(client):
    cid = await _barbarian(client, 14, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    url = f"/characters/{cid}/items/{sword}/attack"
    await client.post(url, json={"die": 10, "confirm_extra_attack": True})
    await client.post(url, json={"die": 10, "confirm_extra_attack": True})
    await _hit(client, cid, 3)
    r = await client.post(url, json={"die": 10, "options": ["barbarian.retaliation"]})
    assert r.status_code == 200, r.text


async def test_damage_proposes_retaliation_to_the_berserker_only(client):
    cid = await _barbarian(client, 14, BERSERKER)
    await _hp(client, cid)
    hit = await _hit(client, cid, 3)
    assert [r["key"] for r in hit["reactions"]] == ["barbarian.retaliation"]
    await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": []}})
    spent = await client.post(f"/characters/{cid}/turn/use", json={"slot": "reaction"})
    assert spent.status_code == 200
    assert (await _hit(client, cid, 1))["reactions"] == []  # la reazione è spesa
    plain = await _barbarian(client, 14, TOTEM)
    await _hp(client, plain)
    assert (await _hit(client, plain, 3))["reactions"] == []


# ---------------------------------------------------------------------------
# I12: prove di Forza pure
# ---------------------------------------------------------------------------

async def test_pure_strength_checks_get_rage_advantage_indomitable_might_and_the_bear_option(client):
    cid = await _totem_barbarian(client, 18, aspect="bear", strength=20)
    plain = (await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 1})).json()
    assert plain["total"] >= 20 and plain["mode_applied"] == "normal"  # Potenza Indomabile (18°)
    await _rage(client, cid)
    raging = (await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 8})).json()
    assert raging["mode_applied"] == "advantage" and "feature:barbarian.rage" in raging["notes"]
    dex = (await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 8})).json()
    assert dex["mode_applied"] == "normal"
    keys = [o["key"] for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "ability", "ability": "strength"})).json()]
    assert "barbarian.aspect_bear_check" in keys
    r = await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 8, "options": ["barbarian.aspect_bear_check"]})
    assert r.json()["mode_applied"] == "advantage"


# ---------------------------------------------------------------------------
# I2 / R36: il GM e il gruppo vedono gli effetti dell'ira
# ---------------------------------------------------------------------------

async def _in_encounter(client, factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, factory)
    pc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    as_user(PLAYER_ID)
    return sid, pc["character_id"]


async def _combatant_states(client, sid, viewer) -> list[dict]:
    as_user(viewer)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    as_user(PLAYER_ID)
    return next(c for c in live["encounter"]["combatants"] if c["kind"] == "pc")["active_states"]


async def test_wolf_and_bear_effects_and_reckless_attack_are_visible_to_gm_and_group(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    r = await client.post(f"/characters/{cid}/classes", json={
        "class_name": "barbarian", "level": 14, "hit_die": 12, "subclass": TOTEM})
    assert r.status_code == 201, r.text
    await _pick(client, cid, "totem_spirit", "wolf")
    await _pick(client, cid, "totem_attunement", "bear")
    await _rage(client, cid)
    sword = await _weapon(client, cid)
    await _attack(client, cid, sword, options=["barbarian.reckless_attack"])
    for viewer in (GM_ID, PLAYER_ID):
        states = {s["key"]: s for s in await _combatant_states(client, sid, viewer)}
        assert set(states) == {"rage", "reckless"}, viewer
        names = {o["key"] for o in states["rage"]["others"]}
        assert names == {"barbarian.totem_wolf", "barbarian.attunement_bear"}
        assert [o["key"] for o in states["reckless"]["others"]] == ["barbarian.reckless_attack"]
        assert all(o["text"] and o["name"] for s in states.values() for o in s["others"])


async def test_plain_rage_is_not_published_and_the_eagle_text_follows_the_armor(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 3, "hit_die": 12, "subclass": TOTEM})
    await _pick(client, cid, "totem_spirit", "eagle")
    await _rage(client, cid)
    [state] = await _combatant_states(client, sid, GM_ID)
    assert [o["key"] for o in state["others"]] == ["barbarian.totem_eagle"]
    await client.delete(f"/characters/{cid}/active-states/rage")
    await _armor(client, cid, "heavy")
    await client.post(f"/characters/{cid}/turn/new")
    await _rage(client, cid)
    assert await _combatant_states(client, sid, GM_ID) == []  # niente testo né stato: l'ira pesante non dà nulla da mostrare


# ---------------------------------------------------------------------------
# I1: Presenza Intimidatoria dalla UI
# ---------------------------------------------------------------------------

async def test_intimidating_presence_extends_without_a_new_save_and_grants_a_day_of_immunity(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    live = (await client.get(f"/characters/{cid}")).json()
    assert live["id"] == cid
    r = await client.post(f"/characters/{cid}/classes", json={
        "class_name": "barbarian", "level": 10, "hit_die": 12, "subclass": BERSERKER})
    assert r.status_code == 201, r.text
    as_user(GM_ID)
    enc = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
    g1, g2 = [c["id"] for c in enc["combatants"] if c["kind"] == "monster"]
    as_user(PLAYER_ID)
    key = "barbarian.intimidating_presence"

    async def intimidate(target):
        assert (await client.post(f"/characters/{cid}/features/{key}/use", json={})).status_code == 200
        return await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": target, "effect_key": key})

    async def resolve(target, passed):
        as_user(GM_ID)
        live = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]
        save = next(c for c in live["combatants"] if c["id"] == target)["pending_saves"][0]
        r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": passed})
        assert r.status_code == 200, r.text
        as_user(PLAYER_ID)

    assert (await intimidate(g1)).json()["pending_save_id"] is not None
    await resolve(g1, passed=False)
    await client.post(f"/characters/{cid}/turn/new")
    assert (await intimidate(g1)).json()["pending_save_id"] is None  # prolungamento
    await client.post(f"/characters/{cid}/turn/new")
    assert (await intimidate(g2)).json()["pending_save_id"] is not None
    await resolve(g2, passed=True)
    await client.post(f"/characters/{cid}/turn/new")
    again = await intimidate(g2)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "target_immune"


# ---------------------------------------------------------------------------
# I3: da sorpreso il pulsante dell'Ira deve restare raggiungibile dalla UI
# ---------------------------------------------------------------------------

async def test_surprised_barbarian_is_told_which_features_let_it_act(client, test_session_factory):
    from sqlalchemy import select
    from core.db.models import Character
    feral, early = await _barbarian(client, 7), await _barbarian(client, 6)
    for cid in (feral, early):
        async with test_session_factory() as s:
            char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
            char.turn_state = {"surprised": True}
            await s.commit()
    assert (await _full(client, feral))["computed"]["surprise_exit_features"] == ["barbarian.rage"]
    assert (await _full(client, early))["computed"]["surprise_exit_features"] == []  # senza Istinto Ferino non c'è via d'uscita
    await _rage(client, feral)
    assert (await _full(client, feral))["computed"]["surprise_exit_features"] == []  # già in ira: sorpresa tolta


# ---------------------------------------------------------------------------
# Giro 2, N5: gli attacchi con slot proprio non consumano quelli dell'azione
# ---------------------------------------------------------------------------

async def _berserker_5(client):
    cid = await _barbarian(client, 5, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    await _rage(client, cid, frenzy=True)
    await client.post(f"/characters/{cid}/turn/new")
    return cid, f"/characters/{cid}/items/{sword}/attack"


async def test_frenzy_attack_between_the_two_attacks_of_the_action_asks_no_question(client):
    cid, url = await _berserker_5(client)
    assert (await client.post(url, json={"die": 10})).status_code == 200
    assert (await client.post(url, json={"die": 10, "options": ["barbarian.frenzy_attack"]})).status_code == 200
    second = await client.post(url, json={"die": 10})  # il secondo dei due dell'azione
    assert second.status_code == 200, second.text
    turn = await _turn(client, cid)
    assert turn["attacks_made"] == 3 and turn["action_attacks"] == 2  # l'Ira vede tutti, il limite solo l'azione
    assert (await client.post(url, json={"die": 10})).status_code == 409  # il terzo dell'azione sì


async def test_frenzy_first_and_then_both_attacks_of_the_action(client):
    cid, url = await _berserker_5(client)
    assert (await client.post(url, json={"die": 10, "options": ["barbarian.frenzy_attack"]})).status_code == 200
    for _ in range(2):
        assert (await client.post(url, json={"die": 10})).status_code == 200
    assert (await client.post(url, json={"die": 10})).status_code == 409


async def test_retaliation_in_your_own_turn_leaves_the_attacks_of_the_action(client):
    cid = await _barbarian(client, 14, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    url = f"/characters/{cid}/items/{sword}/attack"
    await _hp(client, cid)
    await _hit(client, cid, 3)
    assert (await client.post(url, json={"die": 10, "options": ["barbarian.retaliation"]})).status_code == 200
    for _ in range(2):
        r = await client.post(url, json={"die": 10})
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Giro 2, M2 e M5: Ira Implacabile annullata, Ritorsione solo a chi può reagire
# ---------------------------------------------------------------------------

async def test_undoing_the_hit_takes_back_the_relentless_rage_count(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11, constitution=14)
    await _hp(client, cid)
    await _rage(client, cid)
    body = await _hit(client, cid, 45)
    assert body["zero_hp_save"]["dc"] == 10
    assert (await client.post(f"/characters/{cid}/hp/undo", json={"op_id": body["hp_undo_id"]})).status_code == 200
    again = await _hit(client, cid, 45)
    assert again["zero_hp_save"]["dc"] == 10  # il colpo annullato non conta


async def test_retaliation_is_not_offered_to_someone_who_cannot_react(client):
    cid = await _barbarian(client, 14, BERSERKER)
    await _hp(client, cid)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert (await _hit(client, cid, 3))["reactions"] == []
    healthy = await _barbarian(client, 14, BERSERKER)
    await _hp(client, healthy)
    assert [r["key"] for r in (await _hit(client, healthy, 3))["reactions"]] == ["barbarian.retaliation"]
