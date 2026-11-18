"""/live legge effetti e TS di tutte le schede insieme: stesso risultato della lettura scheda per scheda."""
from __future__ import annotations

from sqlalchemy import event

from api.services.condition_effects import SaveSpec, character_effect_payload, upsert_effect
from core.db.models import PendingSave


def _ps(eff_id, cid, status, **kw):
    return PendingSave(effect_id=eff_id, character_id=cid, ability="constitution", dc=12,
                       status=status, created_at="2026-11-18T10:00:00", **kw)


async def _payload(s, ids):
    try:
        from api.services.condition_effects import characters_effect_payload
    except ImportError:  # codice di prima della modifica: stessa attesa, una scheda alla volta
        return {i: await character_effect_payload(s, i) for i in ids}
    return await characters_effect_payload(s, ids)


async def test_effetti_e_ts_divisi_per_scheda(client, test_session_factory):
    a = (await client.post("/characters", json={"name": "Aldo"})).json()["id"]
    b = (await client.post("/characters", json={"name": "Bea"})).json()["id"]
    c = (await client.post("/characters", json={"name": "Ciro"})).json()["id"]
    async with test_session_factory() as s:
        pois = await upsert_effect(s, ("character", a), "poisoned", save=SaveSpec("constitution", 12, "end"))
        fear = await upsert_effect(s, ("character", a), "frightened")
        fear.pending = True  # in attesa del TS: non è sulla scheda, ma il suo TS sì
        prone = await upsert_effect(s, ("character", b), "prone", source_character_id=a)
        s.add_all([
            _ps(pois.id, a, "failed"),                  # superato da quello dopo: nascosto
            _ps(pois.id, a, "failed"),                  # il più recente dell'effetto: visibile
            _ps(fear.id, a, "pending"),
            _ps(prone.id, b, "failed", dismissed=True),  # scartato: nascosto
            _ps(pois.id, b, "pending"),                 # effetto di un'altra scheda: slug vuoto
        ])
        await s.commit()
        out = await _payload(s, [a, b, c])
        for cid in (a, b, c):  # la lettura singola dà lo stesso risultato
            assert await character_effect_payload(s, cid) == out[cid]

    eff_a, ps_a = out[a]
    assert [e.slug for e in eff_a] == ["poisoned"]
    assert [(p.slug, p.status) for p in ps_a] == [("poisoned", "failed"), ("frightened", "pending")]
    eff_b, ps_b = out[b]
    assert [(e.slug, e.source_name) for e in eff_b] == [("prone", "Aldo")]
    assert [(p.slug, p.status) for p in ps_b] == [("", "pending")]
    assert out[c] == ([], [])


async def test_live_non_fa_query_per_personaggio(client, test_session_factory):
    """Il numero di query di _load_live_characters non cresce con le schede."""
    from api.routers.sessions import _load_live_characters

    ids = [(await client.post("/characters", json={"name": f"PG{i}"})).json()["id"] for i in range(4)]

    async def count(char_ids):
        async with test_session_factory() as s:
            n = 0

            def on_exec(*_):
                nonlocal n
                n += 1
            engine = s.bind.sync_engine
            event.listen(engine, "before_cursor_execute", on_exec)
            try:
                out = await _load_live_characters(char_ids, s)
            finally:
                event.remove(engine, "before_cursor_execute", on_exec)
            assert set(out) == set(char_ids)
            return n

    assert await count(ids[:1]) == await count(ids)
