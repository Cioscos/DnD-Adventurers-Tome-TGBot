"""Cataloghi delle regole di classe (sola lettura)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.auth import get_current_lang, get_current_user
from api.schemas.rules import ProficiencyGrantRead, SubclassRead
from core.data.spell_slots import normalize_class_name
from core.rules.proficiencies import class_proficiencies, grant_to_dict
from core.rules.subclasses import subclasses_for
from core.rules.types import Edition

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/subclasses", response_model=list[SubclassRead])
async def list_subclasses(
    edition: Edition, class_key: str, _user: Annotated[int, Depends(get_current_user)],
) -> list[SubclassRead]:
    class_key = normalize_class_name(class_key) or class_key  # accetta anche i nomi italiani (`Mago`)
    return [SubclassRead(key=s.key, name=s.name, choice_level=s.choice_level) for s in subclasses_for(edition, class_key)]


@router.get("/proficiencies", response_model=ProficiencyGrantRead)
async def class_proficiency_grant(
    edition: Edition, class_key: str, as_multiclass: bool,
    _user: Annotated[int, Depends(get_current_user)], lang: Annotated[str, Depends(get_current_lang)],
) -> ProficiencyGrantRead:
    """Competenze che dà la classe (con elenco e numero delle abilità da scegliere)."""
    class_key = normalize_class_name(class_key) or class_key
    return ProficiencyGrantRead(**grant_to_dict(class_proficiencies(edition, class_key, as_multiclass), lang))
