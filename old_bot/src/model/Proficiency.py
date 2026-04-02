from typing import Optional, Union, List, TYPE_CHECKING

from pydantic import BaseModel, Field

from src.model.APIResource import APIResource
from src.model.ClassResource import ClassResource

if TYPE_CHECKING:
    from src.model.Race import Race, Subrace


class ProficiencyChoiceOption(BaseModel):
    choice: 'ProficiencyChoice'
    option_type: str


class ProficiencyReferenceOption(BaseModel):
    item: Optional['Proficiency'] = None
    option_type: str


class ProficiencyOptionSet(BaseModel):
    option_set_type: str
    options: Union[ProficiencyChoiceOption, ProficiencyReferenceOption]


class ProficiencyChoice(BaseModel):
    desc: str
    type: str
    choose: int
    from_: ProficiencyOptionSet = Field(..., alias='from')


class Proficiency(APIResource):
    classes: Optional[List[ClassResource]] = None
    races: Optional[List[Union['Race', 'Subrace']]] = None
    reference: Optional[APIResource] = None
    type: str
