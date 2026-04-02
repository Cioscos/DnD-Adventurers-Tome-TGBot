from typing import Optional, List, Union

from pydantic import BaseModel, Field

from src.model.APIResource import APIResource
from src.model.Equipment import Equipment
from src.model.Proficiency import Proficiency
from src.model.SpellResource import SpellResource


class ActionOption(BaseModel):
    action_name: str
    count: Union[int, str]
    option_type: str
    type: str


class MultipleActionOption(BaseModel):
    items: List[ActionOption]
    option_type: str


class MonsterActionOptionSet(BaseModel):
    option_set_type: str
    options: Union[ActionOption, MultipleActionOption]


class MonsterActionChoice(BaseModel):
    choose: int
    type: str
    from_: Optional[MonsterActionOptionSet] = Field(..., alias='from')


class Action(BaseModel):
    action_name: str
    type: str
    count: Union[int, str]


class DamageType(BaseModel):
    index: str
    name: str
    desc: List[str]


class Skill(BaseModel):
    ability_score: Optional['AbilityScore'] = None
    desc: List[str]
    index: str
    name: str


class AbilityScore(BaseModel):
    desc: List[str]
    full_name: str
    index: str
    name: str
    skills: Optional[Skill] = None


class ActionDc(BaseModel):
    success: str
    type: Optional[AbilityScore] = None
    value: int


class DamageOption(BaseModel):
    damage_dice: str
    damage_type: DamageType
    notes: str
    option_type: Optional[str]


class DamageOptionSet(BaseModel):
    option_set_type: str
    options: Optional[List[DamageOption]] = None


class ActionDamage(BaseModel):
    choose: Optional[int] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[DamageType] = None
    dc: Optional[ActionDc] = None
    from_: Optional[DamageOptionSet] = Field(..., alias='from')
    type: str


class Damage(BaseModel):
    damage_dice: str
    damage_type: DamageType


class Attack(BaseModel):
    name: str
    dc: Optional[ActionDc] = None
    damage: Optional[Damage] = None


class BreathOption(BaseModel):
    damage: Optional[List[Damage]] = None
    dc: Optional[ActionDc] = None
    name: str
    option_type: Optional[str]


class BreathOptionSet(BaseModel):
    option_set_type: str
    options: Optional[List[BreathOption]] = None


class BreathChoice(BaseModel):
    choose: int
    type: str
    from_: Optional[BreathOptionSet] = Field(..., alias='from')


class Usage(BaseModel):
    dice: str
    min_value: int
    times: int
    rest_types: Optional[List[str]] = None
    type: Optional[str] = None


class MonsterAction(BaseModel):
    name: str
    damage: Optional[ActionDamage] = None
    actions: Optional[List[Action]] = None
    action_options: Optional[MonsterActionChoice] = None
    attack_bonus: Optional[int] = None
    attacks: Optional[List[Attack]] = None
    dc: Optional[ActionDc] = None
    desc: Optional[str] = None
    multiattack_type: Optional[str] = None
    options: Optional[BreathChoice] = None
    usage: Optional[Usage] = None


class EquipmentCategory(BaseModel):
    index: str
    name: str
    equipment: Optional[List[Equipment]] = None


class ArmorClass(BaseModel):
    base: int
    dex_bonus: bool
    max_bonus: int


class Cost(BaseModel):
    quantity: int
    unit: str


class Armor(BaseModel):
    armor_category: Optional[EquipmentCategory] = None
    armor_class: Optional[ArmorClass] = None
    cost: Optional[Cost] = None
    desc: List[str] = []
    equipment_category: Optional[EquipmentCategory] = None
    index: str
    name: str
    stealth_disadvantage: Optional[bool] = None
    str_minimum: Optional[int] = None
    weight: Optional[float] = None


class Condition(BaseModel):
    index: str
    name: str
    desc: Optional[List[str]] = None


class MonsterArmorClass(BaseModel):
    armor: Optional[Armor] = None
    condition: Optional[Condition] = None
    desc: Optional[str] = None
    spell: Optional[SpellResource] = None
    type: Optional[str] = None
    value: Optional[int] = None


class LegendaryAction(BaseModel):
    damage: Optional[List[Damage]] = None
    dc: Optional[ActionDc] = None
    desc: str
    name: str


class MonsterProficiency(BaseModel):
    value: int
    proficiency: Optional[Proficiency] = None


class Reaction(APIResource):
    dc: Optional[ActionDc] = None
    desc: str


class Senses(BaseModel):
    blindsight: Optional[str] = None
    darkvision: Optional[str] = None
    passive_perception: Optional[int] = None
    tremorsense: Optional[str] = None
    truesight: Optional[str] = None


class MonsterSpellSlot(BaseModel):
    level: int
    slots: int


class MonsterSpell(BaseModel):
    usage: Optional[Usage] = None
    spell: Optional[SpellResource] = None


class MonsterSpellcasting(BaseModel):
    ability: Optional[AbilityScore] = None
    components_required: Optional[List[str]] = None
    dc: int
    level: int
    modifier: int
    school: str
    slots: List[MonsterSpellSlot]
    spells: Optional[List[MonsterSpell]] = None


class SpecialAbility(APIResource):
    damage: Optional[Damage] = None
    dc: Optional[ActionDc] = None
    desc: str
    spellcasting: Optional[MonsterSpellcasting]
    usage: Optional[Usage] = None


class MonsterSpeed(BaseModel):
    burrow: Optional[str] = None
    climb: Optional[str] = None
    fly: Optional[str] = None
    hover: Optional[bool] = None
    swim: Optional[str] = None
    walk: Optional[str] = None


class Monster(APIResource):
    actions: Optional[List[MonsterAction]] = None
    alignment: str
    armor_class: Optional[List[MonsterArmorClass]] = None
    challange_rating: Optional[float] = None
    charisma: Optional[int] = None
    condition_immunities: Optional[List[Condition]] = None
    constitution: int = None
    damage_immunities: Optional[List[str]] = None
    damage_resistances: Optional[List[str]] = None
    damage_vulnerabilities: Optional[List[str]] = None
    desc: Optional[str] = None
    dexterity: Optional[int] = None
    forms: Optional[List['Monster']] = None
    hit_dice: str
    hit_points: int
    hit_points_roll: int
    image: str
    intelligence: Optional[int] = None
    languages: Optional[List[str]] = None
    legendary_actions: Optional[List[LegendaryAction]] = None
    proficiencies: Optional[List[MonsterProficiency]] = None
    proficiency_bonus: Optional[int] = None
    reactions: Optional[List[Reaction]] = None
    senses: Optional[Senses] = None
    size: str
    special_abilities: Optional[List[SpecialAbility]] = None
    speed: Optional[MonsterSpeed] = None
    strength: Optional[int] = None
    subtype: Optional[str] = None
    type: Optional[str] = None
    wisdom: int
    xp: int
