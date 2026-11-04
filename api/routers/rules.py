"""Cataloghi delle regole di classe (sola lettura)."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.schemas.session import TurnBlock
from api.routers._helpers import unarmed_attack_profile, weapon_attack_profile
from api.routers.hp import _get_owned_full
from api.services.rules_states import remove_state, use_feature
from api.services.rules_turn import clear_once_per_turn, get_turn, release, reset_turn, spend
from core.db.models import Character
from api.schemas.rules import ProficiencyGrantRead, RollOptionRead, SubclassRead
from api.services.rules_options import list_options
from core.data.damage_types import canonical_damage_type
from core.data.skills import SKILL_ABILITY_MAP
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


# ---------------------------------------------------------------------------
# Stato del turno
# ---------------------------------------------------------------------------

turn_router = APIRouter(prefix="/characters", tags=["rules"])


class TurnUse(BaseModel):
    slot: Literal["action", "bonus", "reaction", "free_interaction", "spell_slot", "bonus_spell", "attack"]
    used: bool = True  # False = annulla (correzione manuale)


async def _owned_char(db: AsyncSession, char_id: int, user_id: int) -> Character:
    char = await db.get(Character, char_id)
    if char is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return char


@turn_router.post("/{char_id}/turn/use", response_model=TurnBlock)
async def turn_use(
    char_id: int, body: TurnUse, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    char = await _owned_char(db, char_id, user_id)
    return (spend if body.used else release)(char, body.slot)


@turn_router.post("/{char_id}/turn/new", response_model=TurnBlock)
async def turn_new(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return reset_turn(await _owned_char(db, char_id, user_id))


@turn_router.post("/{char_id}/turn/other", response_model=TurnBlock)
async def turn_other(
    char_id: int, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Fuori da un incontro: è il turno di un altro, tornano gli effetti «una volta per turno»."""
    char = await _owned_char(db, char_id, user_id)
    clear_once_per_turn(char)
    return get_turn(char)


@turn_router.get("/{char_id}/roll-options", response_model=list[RollOptionRead])
async def roll_options(
    char_id: int,
    roll: Literal["attack", "spell_damage", "skill", "save", "initiative", "death_save", "damage_taken"],
    user_id: Annotated[int, Depends(get_current_user)],
    lang: Annotated[str, Depends(get_current_lang)],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: int | None = None,
    spell_id: int | None = None,
    ability: str | None = None,
    skill: str | None = None,
    damage_type: str | None = None,
    attack_mode: Literal["melee", "thrown"] = "melee",
    grip: Literal["one", "two"] = "one",
) -> list[RollOptionRead]:
    """Opzioni da chiedere al giocatore per questo tiro. Sola lettura: il server le riconvalida al tiro."""
    char = await _get_owned_full(char_id, user_id, db)
    item = next((i for i in char.items if i.id == item_id), None)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if (item_id is not None and item is None) or (spell_id is not None and spell is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if roll == "initiative":
        ability = "dexterity"
    # Stesso contesto del tiro: un'opzione legata a caratteristica o modalità non deve sparire solo dall'elenco.
    attack: dict = {}
    if roll == "attack" and spell is None:
        if item is None:
            _, _, ability = unarmed_attack_profile(char)
            attack = {"attack_mode": "melee", "grip": "one"}
        else:
            _, ability, resolved_mode = weapon_attack_profile(char, item, attack_mode)
            attack = {"attack_mode": resolved_mode, "grip": grip}
    return list_options(char, roll, lang, item=item, spell=spell, skill=skill, **attack,
                        ability=ability or SKILL_ABILITY_MAP.get(skill), damage_type=canonical_damage_type(damage_type))


# ---------------------------------------------------------------------------
# Uso dei privilegi e stati attivi
# ---------------------------------------------------------------------------

class FeatureUse(BaseModel):
    amount: int = Field(1, ge=1)
    params: dict | None = None


class FeatureUseResult(BaseModel):
    rolls: list[int] = []
    healed: int = 0
    state: dict | None = None
    notes: list[str] = []


@turn_router.post("/{char_id}/features/{feature_key}/use", response_model=FeatureUseResult)
async def feature_use(
    char_id: int, feature_key: str, body: FeatureUse, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeatureUseResult:
    char = await _get_owned_full(char_id, user_id, db)
    res = await use_feature(db, char, feature_key, body.amount, body.params)
    return FeatureUseResult(rolls=res.rolls, healed=res.healed, state=res.state, notes=res.notes)


@turn_router.delete("/{char_id}/active-states/{key}", response_model=list[dict])
async def end_active_state(
    char_id: int, key: str, user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    char = await _get_owned_full(char_id, user_id, db)
    remove_state(char, key)
    return char.active_states
