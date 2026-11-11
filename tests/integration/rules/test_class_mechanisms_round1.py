"""Giro 1 della revisione del Task 19: meccanismi comuni (R32-R37), provati con privilegi di prova e non con il Barbaro."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Ability, AppMeta, Character
from core.rules.feature_sync import ABILITY_BONUS_KEY
from core.rules.types import FeatureSpec, Modifier, OnUse, RollOptionSpec, StateSpec, TargetEffect, Uses
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_class_mechanisms import KEY, _fighter, _full, _spec, _use
from tests.integration.test_condition_time import _advance, _start

BARBARIAN_BODY = {"name": "Barbaro", "initial_class": {"class_name": "barbarian", "level": 5}}


async def _scores(client, cid) -> dict:
    return {a["name"]: a["value"] for a in (await _full(client, cid))["ability_scores"]}


# ---------------------------------------------------------------------------
# R33: passaggio al catalogo dei personaggi esistenti
# ---------------------------------------------------------------------------

async def _age(factory, cid, name="Furia") -> None:
    """Riporta il Barbaro allo stato di prima del catalogo: riga col vecchio nome, 2 usi spesi e testo proprio."""
    async with factory() as s:
        rows = (await s.execute(select(Ability).where(Ability.character_id == cid))).scalars().all()
        for a in rows:
            if a.feature_key == "barbarian.rage":
                a.name, a.uses, a.description = name, 1, "Il mio testo"
            elif a.feature_key == "barbarian.reckless_attack":
                await s.delete(a)
        await s.commit()


async def _rage_row(client, cid) -> dict:
    return next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "barbarian.rage")


async def test_migration_brings_existing_characters_to_the_catalog_once(client, test_session_factory):
    from api.services.catalog_migration import migrate_catalog
    from core.rules.catalog import CATALOG_VERSION
    cid = (await client.post("/characters", json=BARBARIAN_BODY)).json()["id"]
    await _age(test_session_factory, cid)
    assert (await _rage_row(client, cid))["name"] == "Furia"
    assert await migrate_catalog(test_session_factory) == 1
    rage = await _rage_row(client, cid)
    assert (rage["name"], rage["uses"], rage["max_uses"], rage["description"]) == ("Ira", 1, 3, "Il mio testo")  # usi spesi e testo propri restano
    keys = {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
    assert "barbarian.reckless_attack" in keys
    async with test_session_factory() as s:
        assert (await s.get(AppMeta, "catalog_version")).value == str(CATALOG_VERSION)
    await _age(test_session_factory, cid)
    assert await migrate_catalog(test_session_factory) == 0  # stessa versione: nessun lavoro
    assert (await _rage_row(client, cid))["name"] == "Furia"


async def test_migration_runs_again_when_the_catalog_version_changes(client, test_session_factory):
    from api.services.catalog_migration import migrate_catalog
    cid = (await client.post("/characters", json=BARBARIAN_BODY)).json()["id"]
    async with test_session_factory() as s:
        s.add(AppMeta(key="catalog_version", value="0"))
        await s.commit()
    await _age(test_session_factory, cid)
    assert await migrate_catalog(test_session_factory) == 1
    assert (await _rage_row(client, cid))["name"] == "Ira"


async def test_migration_never_deletes_spell_slot_rows(client, test_session_factory):
    from api.services.catalog_migration import migrate_catalog
    from core.db.models import SpellSlot
    cid = (await client.post("/characters", json=BARBARIAN_BODY)).json()["id"]
    async with test_session_factory() as s:  # dati vecchi: slot messi direttamente su un non incantatore
        s.add(SpellSlot(character_id=cid, level=1, total=2, used=1))
        await s.commit()
    await _age(test_session_factory, cid)
    assert await migrate_catalog(test_session_factory) == 1
    async with test_session_factory() as s:
        rows = (await s.execute(select(SpellSlot).where(SpellSlot.character_id == cid))).scalars().all()
    assert [(r.level, r.total, r.used) for r in rows] == [(1, 2, 1)]  # R33 non prevede di toccare gli slot


async def test_migration_failure_of_one_character_does_not_block_the_others(client, test_session_factory, monkeypatch):
    from api.services.catalog_migration import migrate_catalog
    first = (await client.post("/characters", json=BARBARIAN_BODY)).json()["id"]
    second = (await client.post("/characters", json=BARBARIAN_BODY)).json()["id"]
    for cid in (first, second):
        await _age(test_session_factory, cid)
    from api.services import catalog_migration
    real = catalog_migration.sync_cataloged_features

    async def flaky(session, char, lang="it", **kw):
        if char.id == first:
            raise RuntimeError("scheda rotta")
        return await real(session, char, lang, **kw)
    monkeypatch.setattr(catalog_migration, "sync_cataloged_features", flaky)
    assert await migrate_catalog(test_session_factory) == 1
    assert (await _rage_row(client, second))["name"] == "Ira"
    assert (await _rage_row(client, first))["name"] == "Furia"
    async with test_session_factory() as s:  # minori 50: la versione si segna lo stesso, un personaggio rotto non fa ripetere il sync a tutti
        assert await s.get(AppMeta, "catalog_version") is not None


# ---------------------------------------------------------------------------
# R34: i bonus ai punteggi dei privilegi
# ---------------------------------------------------------------------------

BONUS = dict(level=5, ability_bonus={"strength": 4}, ability_cap=24)


async def test_migration_marks_the_bonus_as_applied_without_touching_the_scores(client, rules_catalog, test_session_factory):
    from api.services.catalog_migration import migrate_catalog
    rules_catalog(_spec(**BONUS))
    cid = await _fighter(client, 5, strength=16)  # il giocatore aveva già scritto il +4: 16 è il punteggio finale
    async with test_session_factory() as s:  # lo stato di prima: nessuna traccia del bonus
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.settings = {k: v for k, v in (char.settings or {}).items() if k not in (ABILITY_BONUS_KEY, "retrofit_done")}
        await s.commit()
    assert await migrate_catalog(test_session_factory) == 1
    assert (await _scores(client, cid))["strength"] == 16
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 12})  # un altro sync
    assert (await _scores(client, cid))["strength"] == 16
    assert KEY in (await _full(client, cid))["settings"][ABILITY_BONUS_KEY]  # segnato: salendo di livello non lo si ridà


async def test_leveling_up_still_grants_the_bonus_and_creation_at_level_too(client, rules_catalog):
    rules_catalog(_spec(**BONUS))
    cid = await _fighter(client, 4, strength=10)
    cls = (await _full(client, cid))["classes"][0]["id"]
    assert (await _scores(client, cid))["strength"] == 10
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 5})
    assert (await _scores(client, cid))["strength"] == 14
    direct = await _fighter(client, 5)
    assert (await _scores(client, direct))["strength"] == 14


async def test_imported_character_counts_the_bonus_as_applied(client, rules_catalog):
    rules_catalog(_spec(**BONUS))
    cid = await _fighter(client, 5, strength=16)
    exported = (await client.get(f"/characters/{cid}/export")).json()
    exported["character"]["settings"].pop(ABILITY_BONUS_KEY, None)  # file di prima dei bonus
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    assert {a["name"]: a["value"] for a in r.json()["ability_scores"]}["strength"] == 16


# ---------------------------------------------------------------------------
# I7: chiavi del server
# ---------------------------------------------------------------------------

async def test_patching_settings_cannot_drop_the_bonus_or_zero_hp_keys(client, rules_catalog, test_session_factory):
    rules_catalog(_spec(**BONUS))
    cid = await _fighter(client, 5)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.settings = {**(char.settings or {}), "zero_hp_save_uses": {KEY: 2}}
        await s.commit()
    assert (await _scores(client, cid))["strength"] == 14
    r = await client.patch(f"/characters/{cid}", json={"settings": {"hp_auto_calc": True}})
    assert r.json()["settings"][ABILITY_BONUS_KEY] and r.json()["settings"]["zero_hp_save_uses"] == {KEY: 2}
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 12})
    assert (await _scores(client, cid))["strength"] == 14  # non si rida il +4


async def test_import_cleans_the_new_server_keys(client, rules_catalog):
    rules_catalog(_spec(**BONUS))
    cid = await _fighter(client, 5, strength=10)
    for bonus, zero in ((["x"], "tre"), ({KEY: "tre"}, {KEY: -4}), ({KEY: {"strength": "molto"}}, [1])):
        exported = (await client.get(f"/characters/{cid}/export")).json()
        exported["character"]["settings"].update({ABILITY_BONUS_KEY: bonus, "zero_hp_save_uses": zero})
        r = await client.post("/characters/import", json=exported)
        assert r.status_code == 201, r.text
        assert r.json()["settings"].get("zero_hp_save_uses", {}) == {}
        assert all(isinstance(v, dict) and all(type(p) is int for p in v.values())
                   for v in r.json()["settings"].get(ABILITY_BONUS_KEY, {}).values())


# ---------------------------------------------------------------------------
# I9: gli annullamenti riportano anche la spossatezza
# ---------------------------------------------------------------------------

TIRED = StateSpec("prova", rounds=1, ends_on=("unconscious",), exhaustion_on_end=1)


async def test_hp_undo_takes_back_the_exhaustion_charged_by_the_operation(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(state=TIRED)))
    cid = await _fighter(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 30})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 20})
    await _use(client, cid)
    hit = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 25})).json()
    assert hit["conditions"]["exhaustion"] == 1 and hit["active_states"] == []
    undone = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": hit["hp_undo_id"]})
    assert undone.status_code == 200, undone.text
    assert not (undone.json()["conditions"] or {}).get("exhaustion")
    assert [s["key"] for s in undone.json()["active_states"]] == ["prova"]


async def test_hp_undo_keeps_the_exhaustion_that_was_there_before(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(state=TIRED)))
    cid = await _fighter(client)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 2}})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 30})
    await _use(client, cid)
    hit = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 40})).json()
    assert hit["conditions"]["exhaustion"] == 3
    undone = (await client.post(f"/characters/{cid}/hp/undo", json={"op_id": hit["hp_undo_id"]})).json()
    assert undone["conditions"]["exhaustion"] == 2


async def test_previous_turn_takes_back_the_exhaustion_of_an_expired_state(client, test_session_factory, rules_catalog, monkeypatch):
    rules_catalog(_spec(on_use=OnUse(state=StateSpec("prova", rounds=1, exhaustion_on_end=1))))
    _, sid, _enc, cid, _pc, _g1, _g2 = await _start(client, test_session_factory, monkeypatch)
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})).status_code == 201
    assert (await _use(client, cid)).status_code == 200
    await _advance(client, sid, 3)  # di nuovo il turno del PG: lo stato scade e lascia la spossatezza
    as_user(PLAYER_ID)
    assert (await _full(client, cid))["conditions"]["exhaustion"] == 1
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200
    as_user(PLAYER_ID)
    full = await _full(client, cid)
    assert not (full["conditions"] or {}).get("exhaustion")
    assert [s["key"] for s in full["active_states"]] == ["prova"]


# ---------------------------------------------------------------------------
# I10: terminare uno stato può costare uno slot del turno
# ---------------------------------------------------------------------------

async def test_ending_a_state_spends_its_end_slot_and_still_ends_without_it(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(state=StateSpec("prova", end_slot="bonus"))))
    cid = await _fighter(client)

    async def turn():
        return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    await _use(client, cid)
    assert (await client.delete(f"/characters/{cid}/active-states/prova")).status_code == 200
    assert (await turn())["bonus_used"] is True
    await _use(client, cid)  # con la bonus già spesa lo stato finisce lo stesso, senza errori: un tocco sbagliato si corregge
    assert (await client.delete(f"/characters/{cid}/active-states/prova")).status_code == 200
    assert (await _full(client, cid))["active_states"] == []
    assert (await turn())["bonus_used"] is True


async def test_state_without_end_slot_costs_nothing_to_end(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(state=StateSpec("prova"))))
    cid = await _fighter(client)
    await _use(client, cid)
    await client.delete(f"/characters/{cid}/active-states/prova")
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["bonus_used"] is False


# ---------------------------------------------------------------------------
# I11: gli attacchi con slot proprio non pesano sul limite dell'azione Attacco
# ---------------------------------------------------------------------------

BONUS_ATTACK = RollOptionSpec(key="fighter.prova_bonus", phase="before", rolls=("attack",), slot="bonus",
                              label={"it": "Bonus", "en": "Bonus"})


async def test_attack_with_an_own_slot_option_skips_the_attack_limit(client, rules_catalog):
    rules_catalog(_spec(roll_options=(BONUS_ATTACK,)))
    cid = await _fighter(client, 1)
    sword = (await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": []}})).json()["items"][0]["id"]
    url = f"/characters/{cid}/items/{sword}/attack"
    assert (await client.post(url, json={"die": 10})).status_code == 200
    again = await client.post(url, json={"die": 10})  # un secondo attacco normale: oltre il limite
    assert again.status_code == 409 and again.json()["detail"]["code"] == "attack_limit"
    extra = await client.post(url, json={"die": 10, "options": ["fighter.prova_bonus"]})
    assert extra.status_code == 200, extra.text
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["bonus_used"] is True
    unarmed = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})
    assert unarmed.status_code == 409  # il limite vale ancora per chi non sceglie l'opzione


# ---------------------------------------------------------------------------
# I12 / R35: prove di caratteristica pure
# ---------------------------------------------------------------------------

STR_ADV = Modifier("advantage", 1, when=lambda c: c.roll in ("skill", "ability") and c.ability == "strength", source="feature:x")
STR_MIN = Modifier("min_total", 25, when=lambda c: c.roll in ("skill", "ability") and c.ability == "strength")
CHECK_OPTION = RollOptionSpec(key="fighter.prova_check", phase="before", rolls=("ability",), mode="advantage",
                              label={"it": "Prova", "en": "Test"}, available=lambda c: c.ability == "strength")


async def test_ability_check_rolls_with_the_ability_modifier_and_the_catalog_branches(client, rules_catalog):
    rules_catalog(_spec(modifiers=(STR_ADV, STR_MIN), roll_options=(CHECK_OPTION,)))
    cid = await _fighter(client, 5, strength=16, dexterity=14)
    r = await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 4, "mode": "normal"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode_applied"] == "advantage" and "feature:x" in body["notes"]  # ramo c.roll == "ability" del catalogo
    assert body["total"] == 25 and body["description"] == "strength"  # totale minimo
    dex = (await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 4})).json()
    assert dex["total"] == 4 + 2 and dex["mode_applied"] == "normal"  # nessuna competenza: solo il modificatore


async def test_ability_check_offers_options_and_applies_them(client, rules_catalog):
    rules_catalog(_spec(roll_options=(CHECK_OPTION,)))
    cid = await _fighter(client, 5, strength=16)
    keys = [o["key"] for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "ability", "ability": "strength"})).json()]
    assert "fighter.prova_check" in keys
    other = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "ability", "ability": "dexterity"})).json()
    assert "fighter.prova_check" not in [o["key"] for o in other]
    r = await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 4, "options": ["fighter.prova_check"]})
    assert r.json()["mode_applied"] == "advantage"
    bad = await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 4, "options": ["fighter.prova_check"]})
    assert bad.status_code == 409


async def test_ability_check_is_recorded_and_can_be_retouched(client, rules_catalog):
    cid = await _fighter(client, 5, strength=16)
    await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 7})
    history = (await client.get(f"/characters/{cid}/history")).json()
    assert any("Forza" in h["description"] and h["event_type"] == "skill_roll" for h in history)
    stats = (await client.get(f"/characters/{cid}/dice/stats")).json()
    assert stats["total_rolls"] >= 1 if "total_rolls" in stats else stats
    last = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["last_roll"]
    assert last["roll"] == "ability" and last["ability"] == "strength" and last["skill"] is None


async def test_ability_check_refuses_an_unknown_ability(client):
    cid = await _fighter(client)
    assert (await client.post(f"/characters/{cid}/ability_checks/luck/roll", json={"die": 4})).status_code == 400


# ---------------------------------------------------------------------------
# I1: prolungamento e immunità di un effetto su altri
# ---------------------------------------------------------------------------

def _scare() -> TargetEffect:
    return TargetEffect(condition="frightened", save_ability="wisdom", save_dc=12,
                        ends_at={"anchor": "source", "edge": "end", "count": 1}, extends=True, immune_on_success=True)


async def _scare_ready(client, factory, rules_catalog, monkeypatch):
    install_fake_telegram(monkeypatch)
    rules_catalog(_spec(on_use=OnUse(slot="action", target_effect=lambda _c, _p: _scare())))
    sid, _ = await setup_full_encounter(client, factory)
    pc, g1, g2 = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})).status_code == 201
    return sid, cid, g1["id"], g2["id"]


async def _scare_use(client, cid, target):
    assert (await _use(client, cid)).status_code == 200
    return await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": target, "effect_key": KEY})


async def _goblin(client, sid, gid) -> dict:
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    as_user(PLAYER_ID)
    return next(c for c in live["encounter"]["combatants"] if c["id"] == gid)


async def _resolve(client, sid, gid, passed: bool) -> None:
    goblin = await _goblin(client, sid, gid)
    save = goblin["pending_saves"][0]
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": passed})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)


async def test_extending_an_effect_on_the_same_target_asks_for_no_new_save(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, g1, _ = await _scare_ready(client, test_session_factory, rules_catalog, monkeypatch)
    assert (await _scare_use(client, cid, g1)).json()["pending_save_id"] is not None
    await _resolve(client, sid, g1, passed=False)
    assert (await _goblin(client, sid, g1))["conditions"] == {"frightened": True}
    await client.post(f"/characters/{cid}/turn/new")
    again = (await _scare_use(client, cid, g1)).json()
    assert again["applied"] is True and again["pending_save_id"] is None  # prolungamento: nessun nuovo TS
    goblin = await _goblin(client, sid, g1)
    assert goblin["pending_saves"] == [] and [e["slug"] for e in goblin["condition_effects"]] == ["frightened"]


async def test_a_passed_save_makes_the_target_immune_until_a_long_rest(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, g1, g2 = await _scare_ready(client, test_session_factory, rules_catalog, monkeypatch)
    await _scare_use(client, cid, g1)
    await _resolve(client, sid, g1, passed=True)
    await client.post(f"/characters/{cid}/turn/new")
    again = await _scare_use(client, cid, g1)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "target_immune"
    other = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": g2, "effect_key": KEY})
    assert other.status_code == 200  # un altro bersaglio non è immune
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _scare_use(client, cid, g1)).status_code == 200


async def test_preview_marks_immune_candidates(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, g1, g2 = await _scare_ready(client, test_session_factory, rules_catalog, monkeypatch)
    await _scare_use(client, cid, g1)
    await _resolve(client, sid, g1, passed=True)
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid)).status_code == 200
    preview = (await client.get(f"/characters/{cid}/target-effects/{KEY}")).json()
    assert {c["id"]: c["immune"] for c in preview["combatants"]}[g1] is True
    assert {c["id"]: c["immune"] for c in preview["combatants"]}[g2] is False


# ---------------------------------------------------------------------------
# I2 / R36: gli stati con effetto su altri sono nel combattente
# ---------------------------------------------------------------------------

async def test_live_combatant_exposes_states_with_effects_on_others_and_nothing_private(client, test_session_factory, rules_catalog, monkeypatch):
    install_fake_telegram(monkeypatch)
    rules_catalog(
        _spec(on_use=OnUse(state=StateSpec("prova", rounds=3, data={"others": [KEY]}))),
        FeatureSpec(key="fighter.privato", class_key="fighter", edition="2014", level=1, source_title="P",
                    name={"it": "Privato", "en": "Private"}, summary={"it": "x", "en": "x"}, action_type=None,
                    on_use=OnUse(state=StateSpec("privato", rounds=3))))
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    await _use(client, cid)
    await client.post(f"/characters/{cid}/features/fighter.privato/use", json={})
    for viewer in (GM_ID, PLAYER_ID):
        as_user(viewer)
        live = (await client.get(f"/sessions/{sid}/live")).json()
        mine = next(c for c in live["encounter"]["combatants"] if c["kind"] == "pc")
        assert [s["key"] for s in mine["active_states"]] == ["prova"], viewer
        state = mine["active_states"][0]
        assert state["rounds_left"] == 3 and state["others"] == [{"key": KEY, "name": "Prova", "text": "x"}]
        monster = next(c for c in live["encounter"]["combatants"] if c["kind"] == "monster")
        assert monster["active_states"] == []


# ---------------------------------------------------------------------------
# I11: le reazioni disponibili dopo un danno
# ---------------------------------------------------------------------------

REACTION = RollOptionSpec(key="fighter.prova_reaction", phase="before", rolls=("attack",), slot="reaction",
                          label={"it": "Reagisci", "en": "React"}, available=lambda c: bool((c.turn or {}).get("damaged")))


async def test_damage_response_offers_the_reactions_it_has_opened(client, rules_catalog):
    rules_catalog(_spec(roll_options=(REACTION,)))
    cid = await _fighter(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 30})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 30})
    hit = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3})).json()
    assert [r["key"] for r in hit["reactions"]] == ["fighter.prova_reaction"]
    assert hit["reactions"][0]["label"] == "Reagisci"
    heal = (await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 2})).json()
    assert heal["reactions"] == []  # solo il danno le apre


# ---------------------------------------------------------------------------
# Giro 2, N1 / N2: il segno «già applicato» non si perde mai
# ---------------------------------------------------------------------------

async def _marked_fighter(client, factory) -> tuple[int, int]:
    """Un 5° che aveva già scritto il +4 a mano (16), segnato dal passaggio al catalogo: marcatore `{}`."""
    from api.services.catalog_migration import migrate_catalog
    cid = await _fighter(client, 5, strength=16)
    async with factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.settings = {k: v for k, v in (char.settings or {}).items() if k not in (ABILITY_BONUS_KEY, "retrofit_done")}
        await s.commit()
    await migrate_catalog(factory)
    assert (await _full(client, cid))["settings"][ABILITY_BONUS_KEY][KEY] == {}
    return cid, (await _full(client, cid))["classes"][0]["id"]


async def test_marked_character_keeps_its_scores_across_an_edition_round_trip(client, rules_catalog, test_session_factory):
    rules_catalog(_spec(**BONUS))
    cid, _ = await _marked_fighter(client, test_session_factory)
    for edition in ("2024", "2014"):
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edition})).status_code == 200
    assert (await _scores(client, cid))["strength"] == 16


async def test_marked_character_keeps_its_scores_when_the_level_goes_down_and_up(client, rules_catalog, test_session_factory):
    rules_catalog(_spec(**BONUS))
    cid, cls = await _marked_fighter(client, test_session_factory)
    for level in (4, 5):
        await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": level})
    assert (await _scores(client, cid))["strength"] == 16


async def test_old_file_without_edition_counts_the_bonus_as_applied(client, rules_catalog):
    rules_catalog(_spec(**BONUS))
    cid = await _fighter(client, 5, strength=16)
    exported = (await client.get(f"/characters/{cid}/export")).json()
    exported["character"]["settings"].pop(ABILITY_BONUS_KEY, None)
    exported["character"].pop("rules_edition", None)  # un file di prima delle edizioni
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    new = r.json()["id"]
    assert (await _scores(client, new))["strength"] == 16
    await client.patch(f"/characters/{new}/ability_scores/dexterity", json={"value": 12})  # un altro sync
    assert (await _scores(client, new))["strength"] == 16
    assert KEY in (await _full(client, new))["settings"][ABILITY_BONUS_KEY]


# ---------------------------------------------------------------------------
# Giro 2, N3: il combattente mostra il testo del catalogo, mai le note del giocatore
# ---------------------------------------------------------------------------

async def test_live_never_shows_the_players_notes_and_speaks_the_viewers_language(client, test_session_factory, rules_catalog, monkeypatch):
    from api.auth import get_current_lang
    from api.main import app
    install_fake_telegram(monkeypatch)
    from dataclasses import replace
    rules_catalog(replace(_spec(on_use=OnUse(state=StateSpec("prova", rounds=3, data={"others": [KEY]}))),
                          summary={"it": "Testo italiano", "en": "English text"}))
    previous = app.dependency_overrides[get_current_lang]
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    await _use(client, cid)
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == KEY)
    secret = "NOTA PRIVATA: odio il GM"
    r = await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"description": secret})
    assert r.status_code == 200, r.text
    try:
        for lang, text in (("it", "Testo italiano"), ("en", "English text")):
            app.dependency_overrides[get_current_lang] = lambda lang=lang: lang
            for viewer in (GM_ID, PLAYER_ID):
                as_user(viewer)
                raw = (await client.get(f"/sessions/{sid}/live")).text
                assert secret not in raw, (viewer, lang)
                live = (await client.get(f"/sessions/{sid}/live")).json()
                mine = next(c for c in live["encounter"]["combatants"] if c["kind"] == "pc")
                assert mine["active_states"][0]["others"][0]["text"] == text, (viewer, lang)
                snap = next(c for c in live["live_characters"] if c["id"] == cid)
                assert snap["active_states"][0]["others"][0]["text"] == text, (viewer, lang)
    finally:
        app.dependency_overrides[get_current_lang] = previous


# ---------------------------------------------------------------------------
# Giro 2, N4: la prova pura usa la stessa formula del bonus delle abilità
# ---------------------------------------------------------------------------

async def test_pure_ability_check_adds_jack_of_all_trades_like_the_skills_do(client):
    cid = (await client.post("/characters", json={"name": "Bardo"})).json()["id"]
    await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 5, "hit_die": 8})
    await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 10})
    full = await _full(client, cid)
    assert full["skill_bonuses"]["athletics"] == 1  # Factotum: 3 // 2, senza competenza
    pure = (await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 7})).json()
    assert pure["bonus"] == full["skill_bonuses"]["athletics"] and pure["total"] == 8
    proficient = await _fighter(client, 5, strength=10)  # senza Factotum: solo il modificatore
    assert (await client.post(f"/characters/{proficient}/ability_checks/strength/roll", json={"die": 7})).json()["bonus"] == 0


async def test_pure_ability_check_of_someone_elses_character_is_refused(client):
    cid = await _fighter(client)
    as_user(987654)
    r = await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 7})
    assert r.status_code in (403, 404)


async def test_an_effect_with_two_conditions_puts_both_on_the_target_after_one_failed_save(client, test_session_factory, rules_catalog, monkeypatch):
    install_fake_telegram(monkeypatch)
    rules_catalog(_spec(on_use=OnUse(slot="action", target_effect=lambda _c, _p: TargetEffect(
        condition="charmed", also=("incapacitated",), save_ability="wisdom", save_dc=12,
        ends_at={"anchor": "source", "edge": "end", "count": 1}))))
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pc, g1, g2 = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})).status_code == 201
    for target, passed in ((g1["id"], False), (g2["id"], True)):
        await client.post(f"/characters/{cid}/turn/new")
        assert (await _use(client, cid)).status_code == 200
        r = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": target, "effect_key": KEY})
        assert r.json()["pending_save_id"] is not None
        assert (await _goblin(client, sid, target))["conditions"] == {}  # finché il TS non è tirato non c'è nulla
        await _resolve(client, sid, target, passed=passed)
    hit, saved = await _goblin(client, sid, g1["id"]), await _goblin(client, sid, g2["id"])
    assert hit["conditions"] == {"charmed": True, "incapacitated": True}
    assert sorted(e["slug"] for e in hit["condition_effects"]) == ["charmed", "incapacitated"]
    assert saved["conditions"] == {} and saved["condition_effects"] == []
