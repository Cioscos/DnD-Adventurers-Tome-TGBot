"""Audit C24: Lancia Occulta 2024 (Warlock p.155) vale per trucchetti con gittata di almeno 3 m; Tocco Gelido 2024 è a Contatto (p.249).
Non si offre più alle nuove scelte, ma chi l'ha già scelta la tiene."""
from __future__ import annotations

from types import SimpleNamespace

from core.rules.catalog.y2024 import warlock_invocations as inv
from tests.integration.rules.test_2024_warlock import _cantrip, _offered, _warlock24


async def test_a_new_2024_warlock_is_not_offered_eldritch_spear_for_chill_touch(client):
    cid = await _warlock24(client, 2)
    await _cantrip(client, cid, "eldritch-blast")
    await _cantrip(client, cid, "chill-touch")
    offered = await _offered(client, cid)
    assert "eldritch_spear__eldritch_blast" in offered and "eldritch_spear__chill_touch" not in offered


def test_a_warlock_who_already_chose_it_keeps_the_row_and_the_option():
    assert "eldritch_spear__chill_touch" in inv.LEVELS
    assert "eldritch_spear__chill_touch" in {s.option_key for s in inv.INVOCATION_ROWS}
    chill = SimpleNamespace(srd_index="chill-touch", name="Tocco Gelido", level=0)

    def ctx(owned):
        row = SimpleNamespace(options={"invocations": owned})
        return SimpleNamespace(class_level=5, class_row=row, char=SimpleNamespace(spells=[chill], settings={}))
    assert "eldritch_spear__chill_touch" not in inv.available_invocations(ctx([]))
    assert "eldritch_spear__chill_touch" in inv.available_invocations(ctx(["eldritch_spear__chill_touch"]))
