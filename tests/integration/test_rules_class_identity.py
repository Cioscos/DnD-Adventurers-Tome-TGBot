from types import SimpleNamespace

from sqlalchemy import select

from core.db.models import Ability, Character, CharacterClass
from core.rules.edition import CLASS_KEYS, class_key
from core.rules.sample_characters import SAMPLE_SPECS, seed_rules_characters


def test_class_key_is_case_and_language_insensitive():
    for n in ("Mago", "wizard", "Wizard", "MAGO"):
        assert class_key(SimpleNamespace(class_name=n)) == "wizard"


def test_custom_class_key_is_none():
    assert class_key(SimpleNamespace(class_name="Cacciatore di Taglie")) is None


def test_class_keys_are_the_twelve_english_keys():
    assert len(CLASS_KEYS) == 12 and "wizard" in CLASS_KEYS


def test_specs_cover_every_class_in_both_editions():
    for ed in ("2014", "2024"):
        keys = {s["classes"][0][0] for s in SAMPLE_SPECS if s["edition"] == ed and len(s["classes"]) == 1 and s["name"].startswith("[prova] ") and s.get("kind") == "class"}
        assert keys == set(CLASS_KEYS)
    assert all(s["name"].startswith("[prova]") for s in SAMPLE_SPECS)


async def test_seed_is_idempotent_and_builds_edge_cases(test_session_factory):
    async with test_session_factory() as s:
        first = await seed_rules_characters(s, 99)
        await s.commit()
        second = await seed_rules_characters(s, 99)
        await s.commit()
        assert first == len(SAMPLE_SPECS) and second == 0
        chars = {c.name: c for c in (await s.execute(select(Character))).scalars()}
        assert len(chars) == len(SAMPLE_SPECS)
        multi = chars["[prova] Multiclasse Mago/Warlock"]
        rows = (await s.execute(select(CharacterClass).where(CharacterClass.character_id == multi.id))).scalars().all()
        assert sorted((class_key(r), r.level) for r in rows) == [("warlock", 3), ("wizard", 17)]
        fighter = chars["[prova] Guerriero CA manuale"]
        assert fighter.base_armor_class == 18 and fighter.base_armor_class_override is True
        assert chars["[prova] Proficienze vuote"].general_proficiencies == []
        assert chars["[prova] Classe custom"].rules_edition == "2014"
        custom = (await s.execute(select(CharacterClass).where(CharacterClass.character_id == chars["[prova] Classe custom"].id))).scalar_one()
        assert custom.hit_die is None
        spent = (await s.execute(select(Ability).where(Ability.character_id == chars["[prova] Usi spesi"].id))).scalars().all()
        assert any(a.uses < a.max_uses for a in spent)
