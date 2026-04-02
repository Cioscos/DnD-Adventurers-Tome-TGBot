from typing import List, Optional, Dict

from pydantic import BaseModel, Field

from src.model.APIResource import APIResource
from src.model.subclasses import DamageType


class AreaOfEffect(BaseModel):
    type: str
    size: int


class Damage(BaseModel):
    damage_type: DamageType
    damage_at_slot_level: Optional[Dict[str, str]] = None
    damage_at_character_level: Optional[Dict[str, str]] = None


class Dc(BaseModel):
    dc_type: APIResource
    dc_success: str


class SpellOption(BaseModel):
    item: 'SpellResource'
    option_type: str


class SpellOptionSet(BaseModel):
    option_set_type: str
    options: Optional[List[SpellOption]] = None


class SpellChoice(BaseModel):
    choose: int
    type: str
    from_: SpellOptionSet = Field(..., alias='from')


class SpellResource(APIResource):
    desc: List[str]
    higher_level: Optional[List[str]] = None
    range: str
    components: List[str]
    material: Optional[str] = None
    ritual: bool
    duration: str
    concentration: bool
    casting_time: str
    level: int
    area_of_effect: Optional[AreaOfEffect] = None
    school: APIResource
    damage: Optional[Damage] = None
    dc: Optional[Dc] = None
    school: Optional[APIResource] = None
    classes: Optional[List[APIResource]] = None
    subclasses: Optional[List[APIResource]] = None
    url: str

    class Config:
        arbitrary_types_allowed = True

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        desc_str = "\n".join(self.desc)
        higher_level_str = " ".join(
            self.higher_level) if self.higher_level else "L'incantesimo non cambia a livelli più alti"
        components_str = ", ".join(self.components)
        material_str = self.material if self.material else "L'incantesimo non usa risorse"
        area_of_effect_str = (f"{self.area_of_effect.type} ({self.area_of_effect.size})"
                              if self.area_of_effect else "L'incantesimo non ha effetti ad aria")

        damage_str = ''
        if self.damage:
            if self.damage.damage_at_slot_level:
                damage_str = (
                    f"{self.damage.damage_type.name}: {', '.join([f'Level {k}: {v}' for k, v in self.damage.damage_at_slot_level.items()])}"
                    if self.damage else "None")
            elif self.damage.damage_at_character_level:
                damage_str = (
                    f"{self.damage.damage_type.name}: {', '.join([f'Level {k}: {v}' for k, v in self.damage.damage_at_character_level.items()])}"
                    if self.damage else "None")

        if self.dc:
            dc_str = f"{self.dc.dc_type.name}"
            if self.dc.dc_success == "half":
                dc_str += f", al superamento della CD subisce metà dei danni"
        else:
            dc_str = "L'incantesimo non ha classe difficoltà"

        classes_str = ", ".join([cls.name for cls in (self.classes or [])])
        subclasses_str = ", ".join([subcls.name for subcls in (self.subclasses or [])])

        return_str = (f"<b>Spell</b>: {self.name}\n"
                      f"<b>Description</b>:\n{desc_str}\n"
                      f"<b>Higher Level</b>: {higher_level_str}\n"
                      f"<b>Range</b>: {self.range}\n"
                      f"<b>Components</b>: {components_str}\n"
                      f"<b>Material</b>: {material_str}\n"
                      f"<b>Ritual</b>: {'Yes' if self.ritual else 'No'}\n"
                      f"<b>Duration</b>: {self.duration}\n"
                      f"<b>Concentration</b>: {'Yes' if self.concentration else 'No'}\n"
                      f"<b>Casting Time</b>: {self.casting_time}\n"
                      f"<b>Level</b>: {self.level}\n"
                      f"<b>Area of Effect</b>: {area_of_effect_str}\n"
                      f"<b>School</b>: {self.school.name if self.school else 'None'}\n")

        if damage_str:
            return_str += f"<b>Damage</b>: {damage_str}\n"

        return_str += (f"<b>DC</b>: {dc_str}\n"
                       f"<b>Classes</b>: {classes_str}\n"
                       f"<b>Subclasses</b>: {subclasses_str}\n")

        return return_str
