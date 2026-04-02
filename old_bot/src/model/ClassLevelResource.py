from typing import Optional, Any, Dict, List

from pydantic import BaseModel, Field, PrivateAttr

from src.DndService import DndService
from .APIResource import APIResource
from .Feature import Feature


class SpellCasting(BaseModel):
    cantrips_known: Optional[int] = None
    spells_known: Optional[int] = None
    spell_slots_level_1: Optional[int] = 0
    spell_slots_level_2: Optional[int] = 0
    spell_slots_level_3: Optional[int] = 0
    spell_slots_level_4: Optional[int] = 0
    spell_slots_level_5: Optional[int] = 0
    spell_slots_level_6: Optional[int] = 0
    spell_slots_level_7: Optional[int] = 0
    spell_slots_level_8: Optional[int] = 0
    spell_slots_level_9: Optional[int] = 0

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        spell_slots_str = ""
        for level in range(1, 10):
            slots = getattr(self, f"spell_slots_level_{level}")
            if slots is not None:
                spell_slots_str += f"Level {level} Slots: {slots}\n"
        return (f"<b>Cantrips Known</b>: {self.cantrips_known if self.cantrips_known is not None else 'None'}\n"
                f"<b>Spells Known</b>: {self.spells_known if self.spells_known is not None else 'None'}\n"
                f"{spell_slots_str}")


class ClassLevelResource(BaseModel):
    level: int
    ability_score_bonuses: int
    prof_bonus: int
    features: Optional[List[APIResource]] = None
    _fetched_features: List[Feature] = PrivateAttr(default_factory=list)  # Private attribute
    spellcasting: Optional[SpellCasting] = None
    class_specific: Optional[Dict[str, Any]] = None
    index: str
    class_: APIResource = Field(..., alias='class')
    url: str

    class Config:
        arbitrary_types_allowed = True

    async def fetch_features(self):
        for feature in self.features:
            async with DndService() as dnd_service:
                resource_details = await dnd_service.get_resource_by_class_resource(feature.url)

            self._fetched_features.append(Feature(**resource_details))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        features_str = ''
        if self._fetched_features:
            for feature in self._fetched_features:
                features_str += f"\n<b>{feature.name} (Lvl. {feature.level})</b> - {" ".join(feature.desc)}"
                if feature.prerequisites:
                    features_str += f"Prerequisites: {feature.prerequisites}"

        spellcasting_str = ""
        if self.spellcasting:
            spellcasting_parts = []
            if self.spellcasting.cantrips_known is not None:
                spellcasting_parts.append(f"Cantrips Known: {self.spellcasting.cantrips_known}")
            if self.spellcasting.spells_known is not None:
                spellcasting_parts.append(f"Spells Known: {self.spellcasting.spells_known}")
            for level in range(1, 10):
                slots = getattr(self.spellcasting, f'spell_slots_level_{level}')
                if slots is not None:
                    spellcasting_parts.append(f"Spell Slots Level {level}: {slots}")
            spellcasting_str = "\n".join(spellcasting_parts)
        class_specific_str = "\n".join([f"{k}: {v}" for k, v in (self.class_specific or {}).items()])

        return_str = (f"<b>Level</b>: {self.level}\n"
                      f"<b>Ability Score Bonuses</b>: {self.ability_score_bonuses}\n"
                      f"<b>Proficiency Bonus</b>: {self.prof_bonus}\n")

        if self._fetched_features:
            return_str += f"<b>Features</b>:{features_str}\n"

        return_str += (f"<b>Spellcasting</b>:\n{spellcasting_str if spellcasting_str else 'None'}\n"
                       f"<b>Class Specific</b>:\n{class_specific_str if class_specific_str else 'None'}\n")

        return return_str
