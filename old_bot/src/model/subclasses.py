from typing import List, Dict, Any, Optional, Union

from pydantic import BaseModel, Field, root_validator, model_validator

from src.model.APIResource import APIResource


class OptionItem(APIResource):
    pass


class EquipmentCategory(APIResource):
    pass


class Option(BaseModel):
    option_type: str
    item: Optional[OptionItem] = None
    of: Optional[OptionItem] = None
    count: Optional[int] = None
    choice: Optional['Choice'] = None  # Use string-based forward reference


class OptionSet(BaseModel):
    option_set_type: str
    options: Optional[List[Option]] = None
    equipment_category: Optional[EquipmentCategory] = None


class Choice(BaseModel):
    desc: str
    choose: int
    type: str
    from_: Union['OptionSet', EquipmentCategory] = Field(..., alias='from')


class ProficiencyChoice(BaseModel):
    desc: str
    choose: int
    type: str
    from_: OptionSet = Field(..., alias='from')


class StartingEquipment(BaseModel):
    equipment: APIResource
    quantity: int


class StartingEquipmentOption(BaseModel):
    desc: str
    choose: int
    type: str
    from_: OptionSet = Field(..., alias='from')


class Prerequisite(BaseModel):
    minimum_score: int
    ability_score: APIResource

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return (f"Minimum score: {self.minimum_score} - "
                f"Ability score: {self.ability_score.name}")


class MultiClassing(BaseModel):
    prerequisites: Optional[List[Prerequisite]] = None
    proficiencies: Optional[List[APIResource]] = None


class SpellcastingInfo(BaseModel):
    name: str
    desc: List[str]


class Spellcasting(BaseModel):
    level: int
    spellcasting_ability: APIResource
    info: List[SpellcastingInfo]


class DamageType(APIResource):
    level: Optional[int] = None
    desc: Optional[List[str]] = None
