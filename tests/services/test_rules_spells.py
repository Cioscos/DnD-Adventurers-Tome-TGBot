import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import rules_spells as rs  # noqa: E402

RULES = ROOT / "docs" / "superpowers" / "rules"
SRD = {x["index"] for x in json.loads((ROOT / "webapp/src/data/srd/spells.json").read_text(encoding="utf-8"))["items"]}

HEADER = ("| titolo IT | titolo EN | livello | scuola | classi | tempo di lancio | gittata | componenti | durata "
          "| concentrazione | rituale | effetto meccanico | pagina |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")


@pytest.mark.skipif(not (RULES / "2014" / "spells.md").exists(), reason="tabelle dei manuali solo in locale")
def test_parse_real_tables():
    y14, y24 = rs.parse_table(RULES / "2014" / "spells.md"), rs.parse_table(RULES / "2024" / "spells.md")
    assert len(y14) >= 355 and len(y24) >= 385
    for rows in (y14, y24):
        names = [r.name_en for r in rows]
        assert len(names) == len(set(names))
    acid = next(r for r in y14 if r.name_en == "Acid Splash")
    assert (acid.name_it, acid.level, acid.school) == ("Fiotto Acido", 0, "conjuration")  # PHB 2014: Evocazione = Conjuration
    assert acid.classes == ["sorcerer", "wizard"] and acid.range_ft == 60
    assert next(r for r in y24 if r.name_en == "Acid Splash").school == "evocation"


def test_range_ft():
    assert [rs.range_ft(s) for s in ("18 m", "27 metri", "1,5 m", "18 m (60 ft)", "60 feet", "120 piedi", "Contatto",
                                     "Self", "Incantatore (raggio 9 m)", "1 mile")] == \
        [60, 90, 5, 60, 60, 120, None, None, None, 5280]


def test_srd_index_for():
    assert rs.srd_index_for("Melf's Acid Arrow", SRD) == "acid-arrow"
    assert rs.srd_index_for("Tasha's Hideous Laughter", SRD) == "hideous-laughter"
    assert rs.srd_index_for("Acid Splash", SRD) == "acid-splash"
    assert rs.srd_index_for("Hex", SRD) is None


def test_phb_index():
    assert rs.phb_index("Armor of Agathys") == "armor-of-agathys"
    assert rs.phb_index("Crusader's Mantle") == "crusaders-mantle"


def test_bad_row_raises(tmp_path):
    f = tmp_path / "s.md"
    f.write_text(HEADER + "| Libro | Book | 1 | Evocazione | Bibliotecario | 1 azione | 9 m | V | Istantanea | no | no "
                 "| x | 1 |\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Book"):
        rs.parse_table(f)


def test_mechanics_save_damage_upcast():
    assert rs.mechanics("Emanazione 10 ft: ogni creatura fa TS For o subisce 2d6 necrotico. Slot superiore: "
                        "+1d6 per livello oltre il 1.") == {
        "attack_type": "SAVE", "save_ability": "str", "damage_dice": "2d6", "damage_type": "necrotic",
        "higher_levels_dice": "1d6"}


def test_mechanics_spell_attack():
    m = rs.mechanics("Attacco a distanza con incantesimo: 1d12 fulmine; scalata +1d12 per slot oltre il 1°")
    assert (m["attack_type"], m["damage_dice"], m["damage_type"], m["higher_levels_dice"]) == ("ATK", "1d12", "lightning", "1d12")


def test_mechanics_extra_damage_and_nothing():
    m = rs.mechanics("Arma non magica: +1 a colpire e +1d4 danni extra di acido, freddo o fuoco")
    assert (m["damage_dice"], m["damage_type"], m["attack_type"]) == ("1d4", "acid", None)
    assert rs.mechanics("Legame telepatico con una creatura consenziente.") == {
        "attack_type": None, "save_ability": None, "damage_dice": None, "damage_type": None, "higher_levels_dice": None}
