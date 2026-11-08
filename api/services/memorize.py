"""Memorizzare Incantesimo (Mago 2024, 5°): al termine di un riposo breve uno degli incantesimi preparati con Incantesimi si
scambia con un altro del libro. Un solo scambio per richiesta, quindi uno per riposo breve; il server convalida tutto prima di
scrivere (la risposta annulla la transazione se un controllo successivo del riposo rifiuta)."""
from __future__ import annotations

from fastapi import HTTPException, status

from core.db.models import Character
from core.rules.catalog import active_features
from core.rules.spellbook import top_slot_level, wizard_row

FEATURE = "wizard.memorize_spell"


def _refuse(name: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": name})


def memorize(char: Character, out_id: int, into_id: int) -> tuple[str, str]:
    """Scambia i due incantesimi e restituisce i loro nomi (uscito, entrato)."""
    if not any(spec.key == FEATURE for spec, _row in active_features(char)):
        raise _refuse("memorize_unavailable")
    spells = {s.id: s for s in char.spells}
    out, into = spells.get(out_id), spells.get(into_id)
    if out is None or into is None:
        raise _refuse("memorize_unknown_spell")
    row = wizard_row(char, out)
    # Solo i preparati con Incantesimi: non i sempre preparati (Maestria, Personali, sottoclasse) né i trucchetti.
    if row is None or out.level < 1 or not out.is_prepared or out.always_prepared:
        raise _refuse("memorize_out")
    if (wizard_row(char, into) is not row or into.level < 1 or not into.in_spellbook or into.is_prepared
            or into.level > top_slot_level(char, row)):
        raise _refuse("memorize_into")
    out.is_prepared, into.is_prepared = False, True
    return out.name, into.name
