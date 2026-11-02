"""Trade service: items, container trees and coins between two characters (pure DB)."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.services.trades import give_coins, give_item
from core.db.models import Character, Currency, EquipmentSlot, Item
from core.game.item_bonuses import item_meta

pytestmark = pytest.mark.asyncio


def _bag(**c) -> str:
    return json.dumps({"container": c})


async def _setup(factory, a_items, b_items=(), a_purse=None):
    async with factory() as s:
        a, b = Character(user_id=1, name="A"), Character(user_id=2, name="B")
        s.add_all([a, b])
        await s.flush()
        s.add(Currency(character_id=a.id, **(a_purse or {})))
        s.add(Currency(character_id=b.id))
        await s.flush()
        ids = {}
        for owner, lst in ((a, a_items), (b, b_items)):
            for spec in lst:
                spec = dict(spec)
                parent = spec.pop("parent", None)
                it = Item(character_id=owner.id, container_id=ids[parent] if parent else None, **spec)
                s.add(it)
                await s.flush()
                ids.setdefault(it.name, it.id)
        await s.commit()
        return a.id, b.id, ids


async def _load(s, cid):
    return (await s.execute(
        select(Character).where(Character.id == cid)
        .options(selectinload(Character.items), selectinload(Character.currency))
    )).scalar_one()


async def test_give_whole_item_keeps_id(test_session_factory):
    a, b, ids = await _setup(test_session_factory, [dict(name="Spada")])
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        snap, _ = await give_item(s, A, B, ids["Spada"], None)
        await s.commit()
        it = await s.get(Item, ids["Spada"])
        assert (it.character_id, it.container_id) == (b, None)
        assert snap == {"name": "Spada", "quantity": 1, "coins": None, "children": []}


async def test_give_container_moves_whole_tree(test_session_factory):
    a, b, ids = await _setup(test_session_factory, [
        dict(name="Zaino", item_metadata=_bag(coins={"gold": 35})),
        dict(name="Borsa", item_metadata=_bag(), parent="Zaino"),
        dict(name="Corda", parent="Borsa"),
    ])
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        snap, _ = await give_item(s, A, B, ids["Zaino"], None)
        await s.commit()
        rows = {n: await s.get(Item, i) for n, i in ids.items()}
        assert all(r.character_id == b for r in rows.values())
        assert rows["Zaino"].container_id is None
        assert rows["Borsa"].container_id == ids["Zaino"] and rows["Corda"].container_id == ids["Borsa"]
        assert item_meta(rows["Zaino"])["container"]["coins"]["gold"] == 35
        assert snap == {"name": "Zaino", "quantity": 1, "coins": {"gold": 35}, "children": [
            {"name": "Borsa", "quantity": 1, "coins": None, "children": [
                {"name": "Corda", "quantity": 1, "coins": None, "children": []}]}]}


async def test_give_clears_equip_and_attunement_on_tree(test_session_factory):
    a, b, ids = await _setup(test_session_factory, [
        dict(name="Zaino", item_metadata=_bag()),
        dict(name="Anello", parent="Zaino", is_equipped=True, equipment_slot=EquipmentSlot.RING1,
             item_metadata=json.dumps({"attuned": True})),
    ])
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        await give_item(s, A, B, ids["Zaino"], None)
        await s.commit()
        for n in ("Zaino", "Anello"):
            r = await s.get(Item, ids[n])
            assert not r.is_equipped and r.equipment_slot is None and not item_meta(r).get("attuned")


async def test_give_equipped_root_unequips_sender(test_session_factory):
    a, b, ids = await _setup(test_session_factory, [dict(
        name="Cotta", item_type="armor", is_equipped=True, equipment_slot=EquipmentSlot.BODY,
        item_metadata=json.dumps({"ac_value": 14}))])
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        A.base_armor_class = 14
        _, removed = await give_item(s, A, B, ids["Cotta"], None)
        assert [(i.name, slot) for i, slot in removed] == [("Cotta", EquipmentSlot.BODY)]
        assert A.base_armor_class == 10


async def test_give_partial_stack_splits(test_session_factory):
    a, b, ids = await _setup(test_session_factory, [dict(
        name="Frecce", quantity=20, is_equipped=True, equipment_slot=EquipmentSlot.AMMUNITION)])
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        snap, removed = await give_item(s, A, B, ids["Frecce"], 5)
        await s.commit()
        mine = await s.get(Item, ids["Frecce"])
        assert (mine.quantity, mine.is_equipped, mine.character_id) == (15, True, a)
        assert removed == [] and snap["quantity"] == 5
        new = (await s.execute(select(Item).where(Item.character_id == b))).scalar_one()
        assert (new.name, new.quantity, new.is_equipped, new.equipment_slot) == ("Frecce", 5, False, None)
        A, B = await _load(s, a), await _load(s, b)
        await give_item(s, A, B, ids["Frecce"], 15)
        await s.commit()
        assert (await s.get(Item, ids["Frecce"])).character_id == b


async def test_give_generic_merges_at_recipient_root(test_session_factory):
    a, b, ids = await _setup(
        test_session_factory,
        [dict(name="Torcia", quantity=3), dict(name="Sacca", item_metadata=_bag())],
        [dict(name="Torcia", quantity=2), dict(name="Sacca", item_metadata=_bag())],
    )
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        await give_item(s, A, B, ids["Torcia"], None)
        await give_item(s, A, B, ids["Sacca"], None)
        await s.commit()
        rows = (await s.execute(select(Item).where(Item.character_id == b))).scalars().all()
        assert [r.quantity for r in rows if r.name == "Torcia"] == [5]
        assert len([r for r in rows if r.name == "Sacca"]) == 2


async def test_give_invalid_quantity_422(test_session_factory):
    a, b, ids = await _setup(test_session_factory, [dict(name="Torcia", quantity=3)])
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        for q in (0, 4):
            with pytest.raises(HTTPException) as e:
                await give_item(s, A, B, ids["Torcia"], q)
            assert (e.value.status_code, e.value.detail) == (422, "invalid_quantity")


async def test_give_foreign_item_404(test_session_factory):
    a, b, ids = await _setup(test_session_factory, [], [dict(name="Spada")])
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        with pytest.raises(HTTPException) as e:
            await give_item(s, A, B, ids["Spada"], None)
        assert e.value.status_code == 404


async def test_give_coins_from_purse_then_containers(test_session_factory):
    a, b, _ = await _setup(
        test_session_factory, [dict(name="Zaino", item_metadata=_bag(coins={"gold": 5}))], a_purse={"gold": 10})
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        assert give_coins(A, B, {"gold": 12, "silver": 0}) == {"gold": 12}
        assert A.currency.gold == 0
        assert item_meta(A.items[0])["container"]["coins"]["gold"] == 3
        assert B.currency.gold == 12


async def test_give_coins_insufficient_409_no_change(test_session_factory):
    a, b, _ = await _setup(
        test_session_factory, [dict(name="Zaino", item_metadata=_bag(coins={"gold": 5}))],
        a_purse={"gold": 10, "silver": 9})
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        with pytest.raises(HTTPException) as e:
            give_coins(A, B, {"silver": 4, "gold": 50})
        assert (e.value.status_code, e.value.detail) == (409, "insufficient_funds")
        assert (A.currency.silver, A.currency.gold, B.currency.silver) == (9, 10, 0)
        assert item_meta(A.items[0])["container"]["coins"]["gold"] == 5


@pytest.mark.parametrize("coins", [{}, {"gold": 0}, {"gold": -1}, {"gold": 3, "bogus": 1}])
async def test_give_coins_nothing_to_give_422(test_session_factory, coins):
    a, b, _ = await _setup(test_session_factory, [], a_purse={"gold": 10})
    async with test_session_factory() as s:
        A, B = await _load(s, a), await _load(s, b)
        with pytest.raises(HTTPException) as e:
            give_coins(A, B, coins)
        assert (e.value.status_code, e.value.detail) == (422, "nothing_to_give")
