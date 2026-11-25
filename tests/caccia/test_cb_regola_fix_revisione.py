"""Controlli della revisione indipendente dei gruppi lancio-core, dati-incantesimi-fe e catalogo-incantesimi."""
import json
from pathlib import Path

import pytest

from sqlalchemy import select

from core.db.models import Character, SpellSlot
from core.rules.catalog.granted_spells import granted_spell
from tests.caccia.test_cb_regola_fix_lancio_core import _pg
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_spell_effects_defenses import _cast, _sheet, _table

SRD = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd"


def _voce(edizione: str, indice: str) -> dict:
    file = "spells.json" if edizione == "2014" else "spells-2024.json"
    return next(s for s in json.loads((SRD / file).read_text(encoding="utf-8"))["items"] if s["index"] == indice)


def _ha(scheda: dict, chiave: str) -> bool:
    return any(s["key"] == chiave for s in scheda["active_states"] or [])


@pytest.mark.caccia(id="CB-4761", fonte="2014 · Incantesimi · Previsione · pag. 264; 2024 · Incantesimi · Preveggenza · pag. 276",
                    zona="regola:2014/incantesimi-M-R", voce="ripetizione",
                    copre=["carta:2014/spells.md#Previsione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_previsione_rilanciata_su_un_png_finisce_sul_bersaglio_di_prima(client, test_session_factory, edizione):
    eroe, mago, previsione = await _table(client, test_session_factory, "Previsione", "foresight", 9, hero_edition=edizione, caster_edition=edizione)
    await _cast(client, mago, previsione, [eroe], level=9)
    assert _ha(await _sheet(client, eroe), "spell:foresight")
    async with test_session_factory() as s:  # un altro slot di 9° senza le 8 ore di un riposo, che la farebbero finire da sé
        for slot in (await s.execute(select(SpellSlot).where(SpellSlot.character_id == mago))).scalars():
            slot.used = 0
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/characters/{mago}/spells/{previsione}/use", json={"slot_level": 9, "targets": [], "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    # «Termina se lanciato di nuovo»: anche se il nuovo bersaglio non ha una scheda
    assert not _ha(await _sheet(client, eroe), "spell:foresight")
    assert not _ha(await _sheet(client, mago, GM_ID), "spell_cast:foresight")


@pytest.mark.caccia(id="CB-4762", fonte="2014 · Incantesimi · Santuario · pag. 272", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Santuario", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_santuario_2014_finisce_quando_il_protetto_attacca(client, test_session_factory):
    eroe, chierico, santuario = await _table(client, test_session_factory, "Santuario", "sanctuary", 1, hero_edition="2014", caster_edition="2014")
    await _cast(client, chierico, santuario, [eroe], level=1)
    assert _ha(await _sheet(client, eroe), "spell:sanctuary")
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{eroe}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "damage_type": "slashing", "weapon_type": "melee"}})
    arma = max(i["id"] for i in r.json()["items"])
    r = await client.post(f"/characters/{eroe}/items/{arma}/attack", json={})
    assert r.status_code == 200, r.text
    # «Termina se la creatura protetta attacca o lancia un incantesimo su un nemico»
    assert not _ha(await _sheet(client, eroe), "spell:sanctuary")
