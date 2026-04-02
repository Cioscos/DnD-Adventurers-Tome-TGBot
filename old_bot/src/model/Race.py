from typing import Optional, List, TYPE_CHECKING

from pydantic import BaseModel

from src.model.APIResource import APIResource
from src.model.AbilityScore import AbilityScore
from src.model.Language import Language, LanguageChoice
from src.model.Trait import Trait

if TYPE_CHECKING:
    from src.model.Proficiency import Proficiency, ProficiencyChoice


class AbilityBonus(BaseModel):
    ability_score: AbilityScore
    bonus: int


class Race(APIResource):
    age: str
    alignment: str
    language_desc: str
    language_options: LanguageChoice
    languages: Optional[List[Language]] = None
    size: str
    size_description: str
    speed: int
    starting_proficiencies: Optional[List['Proficiency']] = None  # Forward reference for Proficiency
    starting_proficiency_options: Optional['ProficiencyChoice'] = None  # Forward reference for ProficiencyChoice


class Subrace(APIResource):
    ability_bonuses: Optional[AbilityBonus]
    desc: str
    language_options: LanguageChoice
    race: Optional[Race] = None
    racial_traits: Optional[List[Trait]] = None
    starting_proficiencies: Optional[List['Proficiency']] = None
