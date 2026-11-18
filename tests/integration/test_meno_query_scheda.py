"""Tetti sul numero di query dei percorsi più chiamati: una lettura in più fa fallire il test, non rallenta il Pi in silenzio."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine


@contextmanager
def count_queries():
    seen: list[str] = []

    def on_exec(_conn, _cur, stmt, *_):
        seen.append(stmt)
    event.listen(Engine, "before_cursor_execute", on_exec)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", on_exec)


async def test_reaction_prompts_senza_richieste_non_carica_la_scheda(client):
    cid = (await client.post("/characters", json={"name": "Aldo"})).json()["id"]
    await client.get(f"/characters/{cid}/reaction-prompts")  # il primo giro fa anche la pulizia (ogni 30 s)
    with count_queries() as q:
        r = await client.get(f"/characters/{cid}/reaction-prompts")
    assert r.json() == []
    assert len(q) <= 2, q


async def test_lista_personaggi_non_fa_query_per_scheda(client):
    async def count() -> int:
        with count_queries() as q:
            assert (await client.get("/characters")).status_code == 200
        return len(q)

    await client.post("/characters", json={"name": "PG0"})
    one = await count()
    for i in range(1, 4):
        await client.post("/characters", json={"name": f"PG{i}"})
    assert await count() == one


async def test_scheda_legge_regole_e_oggetti_una_volta(client):
    cid = (await client.post("/characters", json={"name": "Aldo"})).json()["id"]
    with count_queries() as q:
        assert (await client.get(f"/characters/{cid}")).status_code == 200
    assert sum("FROM homebrew_rules" in s for s in q) <= 2, q  # la seconda è il tentativo di lettura pigra dello schema
    assert sum("FROM items" in s for s in q) == 1, q
    assert not any("sum(character_classes.level)" in s for s in q), q
