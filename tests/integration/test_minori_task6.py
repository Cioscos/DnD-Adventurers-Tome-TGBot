"""Task 6 dei minori rinviati: punti 26, 27, 50, 51, 53."""
from __future__ import annotations

from api.services import catalog_migration
from tests.integration.rules.test_2014_bard_round2 import _bump
from tests.integration.rules.test_class_mechanisms import _fighter


async def test_minori_50_a_broken_character_does_not_resync_everyone_at_every_start(client, test_session_factory, monkeypatch):
    broken = await _fighter(client, 3)
    await _fighter(client, 3)
    real = catalog_migration.sync_cataloged_features
    seen: list[int] = []

    async def flaky(session, char, lang, **kw):
        seen.append(char.id)
        if char.id == broken:
            raise ValueError("dati rotti")
        return await real(session, char, lang, **kw)

    monkeypatch.setattr(catalog_migration, "sync_cataloged_features", flaky)
    await _bump(test_session_factory)
    assert await catalog_migration.migrate_catalog(test_session_factory) == 1  # l'altro personaggio passa lo stesso
    seen.clear()
    assert await catalog_migration.migrate_catalog(test_session_factory) == 0
    assert seen == []  # al secondo avvio nessuno viene risincronizzato


# --- 51: i GET non scrivono nel database -------------------------------------------------------------------------

import json  # noqa: E402

from sqlalchemy import event, select, text  # noqa: E402

from core.db.models import Character, Companion, Item  # noqa: E402


class _Writes:
    """Conta le istruzioni di scrittura (INSERT/UPDATE/DELETE) eseguite sul database."""

    def __init__(self, factory):
        self.engine = factory.kw["bind"].sync_engine
        self.statements: list[str] = []

    def _on(self, conn, cursor, statement, *a):
        if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            self.statements.append(statement)

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._on)


async def _armored(client, factory) -> int:
    """Un PG con Destrezza 16 e un'armatura leggera indossata, con la base salvata volutamente sbagliata e già migrata."""
    cid = (await client.post("/characters", json={"name": "Prova"})).json()["id"]
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 16})
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Cuoio", "item_type": "armor", "quantity": 1,
        "item_metadata": {"armor_type": "light", "ac_value": 11}})
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "body"})
    assert r.status_code == 200, r.text
    await client.get(f"/characters/{cid}")  # migra una volta
    return cid


async def test_minori_51_a_get_does_not_write_even_when_the_stored_ac_is_stale(client, test_session_factory):
    cid = await _armored(client, test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).base_armor_class = 1  # valore salvato in ritardo (es. una via che non ricalcola)
        await s.commit()
    with _Writes(test_session_factory) as w:
        r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200
    assert r.json()["ac"] == 14  # 11 + Des 3: il GET restituisce il valore calcolato
    assert w.statements == []
    async with test_session_factory() as s:
        assert (await s.get(Character, cid)).base_armor_class == 1  # e non lo salva


async def test_minori_51_a_get_does_not_write_the_migration_flag(client, test_session_factory):
    cid = (await client.post("/characters", json={"name": "Vecchio"})).json()["id"]
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.settings = {}  # scheda di prima della migrazione della CA
        await s.commit()
    with _Writes(test_session_factory) as w:
        assert (await client.get(f"/characters/{cid}")).status_code == 200
    assert w.statements == []


async def test_minori_51_writes_that_change_the_ac_save_it(client, test_session_factory):
    cid = await _armored(client, test_session_factory)
    async with test_session_factory() as s:
        assert (await s.get(Character, cid)).base_armor_class == 14
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 12})
    async with test_session_factory() as s:
        assert (await s.get(Character, cid)).base_armor_class == 12  # 11 + Des 1


async def test_minori_51_a_get_does_not_close_a_stale_wild_shape(client, test_session_factory):
    cid = (await client.post("/characters", json={"name": "Druido"})).json()["id"]
    async with test_session_factory() as s:
        s.add(Companion(character_id=cid, kind="wild_shape", name="Lupo", is_active=True, max_hp=10, current_hp=10, created_at="2026-01-01T00:00:00"))
        await s.commit()  # forma attiva senza lo stato: dato rimasto indietro
    with _Writes(test_session_factory) as w:
        r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200
    assert r.json().get("active_form") is None
    assert w.statements == []


async def test_minori_51_the_character_gets_write_nothing(client, test_session_factory):
    cid = await _armored(client, test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).settings = {}
        await s.commit()
    urls = ["/characters", f"/characters/{cid}", f"/characters/{cid}/turn-state", f"/characters/{cid}/companions",
            f"/characters/{cid}/export", f"/characters/{cid}/history", f"/characters/{cid}/items", f"/characters/{cid}/spells"]
    with _Writes(test_session_factory) as w:
        for url in urls:
            r = await client.get(url)
            assert r.status_code in (200, 404), (url, r.status_code)
    assert w.statements == []


def test_minori_51_closing_the_wild_shape_state_closes_the_form_row():
    from types import SimpleNamespace as NS

    from core.rules.states import close_wild_shape_rows

    form, familiar = NS(kind="wild_shape", is_active=True), NS(kind="familiar", is_active=True)
    char = NS(companions=[form, familiar])
    close_wild_shape_rows(char, [{"key": "rage"}])
    assert form.is_active is True
    close_wild_shape_rows(char, [{"key": "wild_shape"}])
    assert form.is_active is False and familiar.is_active is True
    close_wild_shape_rows(NS(), [{"key": "wild_shape"}])  # compagni non caricati: niente da fare


def test_expiry_count_zero_is_refused_by_the_public_schema():
    import pytest
    from pydantic import ValidationError

    from api.schemas.encounter import ExpiryIn

    with pytest.raises(ValidationError):
        ExpiryIn(anchor="owner", edge="start", count=0)
    assert ExpiryIn(anchor="owner", edge="start", count=1).count == 1
