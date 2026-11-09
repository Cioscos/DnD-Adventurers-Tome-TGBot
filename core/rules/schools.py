"""Nomi delle scuole di magia: foglia, senza import dal catalogo."""
from __future__ import annotations

# nomi italiani delle scuole (la scuola salvata è di solito lo slug inglese del compendio)
_SCHOOL_IT = {"abiurazione": "abjuration", "ammaliamento": "enchantment", "divinazione": "divination",
              "evocazione": "conjuration", "illusione": "illusion", "invocazione": "evocation",
              "necromanzia": "necromancy", "trasmutazione": "transmutation"}


def normalize_school(value: str | None) -> str | None:
    text = (value or "").strip().lower()
    return _SCHOOL_IT.get(text, text) or None


# stati-finestra: chi li legge (``available`` di un uso) li trova finché non si lancia altro o non finisce il turno/il riposo
WINDOW_ENCHANTMENT = "window_enchantment"  # Alterare Ricordi: l'ammaliamento appena lanciato
WINDOW_ILLUSION_TURN = "window_illusion_turn"  # Realtà Illusoria: finché l'illusione dura (solo il turno, se non ha una durata)
WINDOW_ILLUSION = "window_illusion"  # Illusioni Duttili: l'illusione dura ancora
WINDOW_TRANSMUTATION = "window_transmutation"  # Pietra del Trasmutatore: si può cambiare il beneficio
