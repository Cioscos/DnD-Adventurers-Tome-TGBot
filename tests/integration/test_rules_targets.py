"""Effetti dei privilegi su un altro combattente (D1): TS del mostro segnato dal GM, PG che tira da solo."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import CharacterClass, ConditionEffect, PendingSave
from core.rules.types import FeatureSpec, OnUse, RollOptionSpec, TargetEffect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.test_rules_attacks import _mastery_feature

_HEX = RollOptionSpec(
    key="test_hex", phase="after_hit", rolls=("attack",), label={"it": "Malia", "en": "Hex"},
    target_effect=lambda _ctx, _inputs: TargetEffect(condition="frightened", save_ability="wisdom", save_dc=12, rounds=2),
)


def _hex_feature() -> FeatureSpec:
    return FeatureSpec(
        key="fighter.prova", class_key="fighter", edition="2024", level=1, source_title="Prova",
        name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None, roll_options=(_HEX,),
        on_use=OnUse(target_effect=lambda _ctx, _inputs: TargetEffect(condition="poisoned", ends_at={"anchor": "source", "edge": "end", "count": 1})))


async def _master(factory, cid, *weapons: str) -> None:
    async with factory() as s:
        row = (await s.execute(select(CharacterClass).where(CharacterClass.character_id == cid))).scalars().first()
        row.options = {"weapon_mastery": list(weapons)}
        await s.commit()


async def _fighter(client, cid) -> None:
    for call in (
        client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 3, "hit_die": 10}),
        client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 16}),
        client.patch(f"/characters/{cid}", json={"rules_edition": "2024"}),
    ):
        assert (await call).status_code in (200, 201)


async def _ready(client, factory, rules_catalog, monkeypatch, *weapons: str):
    """Incontro attivo con il PG (2024, Maestria su ``weapons``, FOR 16): (sid, char_id, pc_id, g1_id, g2_id)."""
    install_fake_telegram(monkeypatch)
    rules_catalog(_mastery_feature(), _hex_feature())
    sid, _ = await setup_full_encounter(client, factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    pc, g1, g2 = r.json()["combatants"]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    await _fighter(client, cid)
    await _master(factory, cid, *weapons)
    return sid, cid, pc["id"], g1["id"], g2["id"]


async def _confirm(client, cid, weapon_name, damage_dice, *options: str) -> dict:
    r = await client.post(f"/characters/{cid}/items", json={"name": weapon_name, "item_type": "weapon", "item_metadata": {
        "damage_dice": damage_dice, "weapon_type": "melee", "properties": []}})
    assert r.status_code == 201, r.text
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == weapon_name)
    first = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "defer_damage": True})).json()
    r = await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={"options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


def _target(client, cid, combatant_id, key):
    return client.post(f"/characters/{cid}/target-effects", json={"combatant_id": combatant_id, "effect_key": key})


async def _gm_view(client, sid) -> dict:
    """I combattenti come li vede il GM; lascia l'utente in modalità GM."""
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    return {c["id"]: c for c in live["encounter"]["combatants"]}


async def test_player_effect_creates_pending_save_for_monster(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    done = await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    assert done["option_result"]["targets"] == ["mastery_topple"]
    r = await _target(client, cid, g1, "mastery_topple")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True and body["result"]["save_dc"] == 13  # 8 + FOR 3 + competenza 2
    assert body["result"]["save_ability"] == "constitution" and body["target_name"] == "Goblin 1"
    goblin = (await _gm_view(client, sid))[g1]
    [save] = goblin["pending_saves"]
    assert (save["ability"], save["dc"], save["status"], save["slug"]) == ("constitution", 13, "pending", "prone")
    assert not goblin["conditions"].get("prone") and goblin["condition_effects"] == []  # prima del TS non c'è nulla


async def test_gm_resolve_failed_applies_condition_and_duration(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch)
    await _confirm(client, cid, "Spada", "1d8", "test_hex")
    assert (await _target(client, cid, g1, "test_hex")).status_code == 200
    goblin = (await _gm_view(client, sid))[g1]
    [save] = goblin["pending_saves"]
    assert goblin["conditions"] == {}
    for _ in range(3):  # il GM tarda un giro intero: la durata non è decorsa
        await client.post(f"/sessions/{sid}/encounter/next-turn")
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": False})
    assert r.status_code == 200, r.text
    goblin = (await _gm_view(client, sid))[g1]
    assert goblin["conditions"] == {"frightened": True} and goblin["pending_saves"] == []
    [eff] = goblin["condition_effects"]
    assert (eff["slug"], eff["expiry_count"], eff["expiry_anchor"], eff["save_ability"]) == ("frightened", 2, "owner", None)


async def test_gm_resolve_success_applies_nothing(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    await _target(client, cid, g1, "mastery_topple")
    [save] = (await _gm_view(client, sid))[g1]["pending_saves"]
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": True})
    assert r.status_code == 200, r.text
    goblin = (await _gm_view(client, sid))[g1]
    assert not goblin["conditions"].get("prone") and goblin["condition_effects"] == []


async def test_stranger_cannot_target(client, test_session_factory, rules_catalog, monkeypatch):
    _, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    as_user(GM_ID)  # il GM non è il proprietario del personaggio
    assert (await _target(client, cid, g1, "mastery_topple")).status_code == 403
    as_user(PLAYER_ID)
    assert (await _target(client, cid, 99999, "mastery_topple")).status_code == 404  # fuori dall'incontro
    assert (await _target(client, cid, g1, "mastery_sap")).status_code == 409  # mai confermato
    async with test_session_factory() as s:
        assert (await s.execute(select(ConditionEffect))).first() is None


async def test_effect_is_consumed_once(client, test_session_factory, rules_catalog, monkeypatch):
    _, cid, _, g1, g2 = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    assert (await _target(client, cid, g1, "mastery_topple")).status_code == 200
    r = await _target(client, cid, g2, "mastery_topple")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "no_target_effect")


async def test_without_encounter_only_returns_result(client, test_session_factory, rules_catalog):
    rules_catalog(_mastery_feature())
    cid = (await client.post("/characters", json={"name": "Solo"})).json()["id"]
    await _fighter(client, cid)
    await _master(test_session_factory, cid, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    r = await client.post(f"/characters/{cid}/target-effects", json={"effect_key": "mastery_topple"})
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is False and r.json()["result"]["save_dc"] == 13
    assert r.json()["result"]["condition"] == "prone"
    preview = await client.get(f"/characters/{cid}/target-effects/mastery_topple")
    assert preview.json()["combatants"] == [] and preview.json()["result"]["save_dc"] == 13


async def test_condition_expires_with_duration(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "mace")
    await _confirm(client, cid, "Mazza", "1d6", "mastery_sap")
    r = await _target(client, cid, g1, "mastery_sap")
    assert r.status_code == 200 and r.json()["pending_save_id"] is None
    assert (await _gm_view(client, sid))[g1]["conditions"] == {"custom:sap": True}
    for _ in range(2):  # turni di g1 e g2: fino all'inizio del turno del PG la condizione c'è ancora
        await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert (await _gm_view(client, sid))[g1]["conditions"] == {"custom:sap": True}
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    goblin = (await _gm_view(client, sid))[g1]
    assert not goblin["conditions"].get("custom:sap") and goblin["condition_effects"] == []


async def test_pc_target_rolls_save_alone(client, test_session_factory, rules_catalog, monkeypatch):
    _, cid, pc, _, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    r = await _target(client, cid, pc, "mastery_topple")  # il PG è bersaglio valido come un alleato: stesso percorso
    assert r.status_code == 200, r.text
    sheet = (await client.get(f"/characters/{cid}")).json()
    [save] = sheet["pending_saves"]
    assert (save["ability"], save["dc"], save["slug"]) == ("constitution", 13, "prone")
    assert not sheet["conditions"].get("prone") and sheet["condition_effects"] == []  # prima del TS non c'è nulla
    r = await client.post(f"/characters/{cid}/pending-saves/{save['id']}/roll", json={"die": 1})
    assert r.status_code == 200 and r.json()["passed"] is False, r.text
    sheet = (await client.get(f"/characters/{cid}")).json()
    assert sheet["conditions"].get("prone") and [e["slug"] for e in sheet["condition_effects"]] == ["prone"]


async def test_pc_target_passed_save_leaves_nothing(client, test_session_factory, rules_catalog, monkeypatch):
    _, cid, pc, _, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    await _target(client, cid, pc, "mastery_topple")
    [save] = (await client.get(f"/characters/{cid}")).json()["pending_saves"]
    r = await client.post(f"/characters/{cid}/pending-saves/{save['id']}/roll", json={"die": 20})
    assert r.status_code == 200 and r.json()["passed"] is True, r.text
    sheet = (await client.get(f"/characters/{cid}")).json()
    assert not sheet["conditions"].get("prone") and sheet["condition_effects"] == [] and sheet["pending_saves"] == []


async def test_passed_save_keeps_a_condition_the_target_already_had(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{g1}/conditions", json={"slug": "prone"})
    as_user(PLAYER_ID)
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    await _target(client, cid, g1, "mastery_topple")
    [save] = (await _gm_view(client, sid))[g1]["pending_saves"]
    await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": True})
    goblin = (await _gm_view(client, sid))[g1]
    assert goblin["conditions"] == {"prone": True} and [e["slug"] for e in goblin["condition_effects"]] == ["prone"]


async def test_second_pending_effect_on_same_target_is_refused(client, test_session_factory, rules_catalog, monkeypatch):
    _, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    assert (await _target(client, cid, g1, "mastery_topple")).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")  # un solo attacco per azione
    await _confirm(client, cid, "Maglio 2", "2d6", "mastery_topple")
    r = await _target(client, cid, g1, "mastery_topple")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "target_effect_pending")
    assert (await _target(client, cid, g1, "mastery_topple")).status_code == 409  # l'effetto non è stato consumato


async def test_ending_the_encounter_drops_pending_effects(client, test_session_factory, rules_catalog, monkeypatch):
    sid, cid, _, g1, _ = await _ready(client, test_session_factory, rules_catalog, monkeypatch, "maul")
    await _confirm(client, cid, "Maglio", "2d6", "mastery_topple")
    await _target(client, cid, g1, "mastery_topple")
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    async with test_session_factory() as s:
        assert (await s.execute(select(ConditionEffect))).first() is None
        assert (await s.execute(select(PendingSave))).first() is None
