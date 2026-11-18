"""LA8: la riga di Cronologia di un'opzione pagata non mostra le chiavi interne dei gettoni."""
from __future__ import annotations

import json
from types import SimpleNamespace

from core.rules.roll_options import spent_description


def test_tokens_become_words():
    char = SimpleNamespace(abilities=[SimpleNamespace(feature_key="monk.ki", name="Ki")], classes=[], rules_edition="2014")
    state = json.dumps({"key": "spell:bless", "name": "Benedizione"})
    out = spent_description(char, "Danni extra", [
        "turn:reaction", "once:rogue.sneak_attack", "feature:monk.ki:2", "slot:3", f"state:spell:bless:{state}"])
    assert out == "Danni extra (reazione, una volta per turno, Ki -2, slot di 3° livello, Benedizione speso)"
    assert ":" not in out.partition("(")[2]
    assert spent_description(char, "Attacco Furtivo (una volta per turno)", ["once:rogue.sneak_attack"]) == \
        "Attacco Furtivo (una volta per turno)"
