from typing import List, Optional

from src.model.APIResource import APIResource
from src.model.subclasses import ProficiencyChoice, StartingEquipment, StartingEquipmentOption, MultiClassing, \
    Spellcasting


class ClassResource(APIResource):
    hit_die: int
    proficiency_choices: List[ProficiencyChoice]
    proficiencies: List[APIResource]
    saving_throws: List[APIResource]
    starting_equipment: List[StartingEquipment]
    starting_equipment_options: List[StartingEquipmentOption]
    class_levels: str
    multi_classing: MultiClassing
    subclasses: List[APIResource]
    spellcasting: Optional[Spellcasting] = None
    spells: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        proficiency_choices_str = "\n".join([f"  - {choice.desc} (Choose {choice.choose})" for choice in (self.proficiency_choices or [])])
        proficiencies_str = ", ".join([prof.name for prof in (self.proficiencies or [])])
        saving_throws_str = ", ".join([st.name for st in (self.saving_throws or [])])
        starting_equipment_str = "\n".join([f"  - {equip.quantity}x {equip.equipment.name}" for equip in (self.starting_equipment or [])])
        starting_equipment_options_str = "\n".join([f"  - {option.desc} (Choose {option.choose})" for option in (self.starting_equipment_options or [])])
        subclasses_str = ", ".join([subclass.name for subclass in (self.subclasses or [])])
        spellcasting_info_str = "\n".join([f"  - {info.name}: {', '.join(info.desc)}" for info in (self.spellcasting.info if self.spellcasting else [])]) if self.spellcasting else 'There are no spells'

        multi_classing_prerequisites_str = "\n".join([str(prereq) for prereq in (self.multi_classing.prerequisites if self.multi_classing and self.multi_classing.prerequisites else [])])
        multi_classing_proficiencies_str = ", ".join([prof.name for prof in (self.multi_classing.proficiencies if self.multi_classing and self.multi_classing.proficiencies else [])])

        return (f"🛡️ <b>Class</b>: {self.name}\n"
                f"🎲 <b>Hit Die</b>: {self.hit_die}\n"
                f"📜 <b>Proficiency Choices</b>:\n{proficiency_choices_str}\n"
                f"🛠️ <b>Proficiencies</b>: {proficiencies_str}\n"
                f"🛡️ <b>Saving Throws</b>: {saving_throws_str}\n"
                f"🗡️ <b>Starting Equipment</b>:\n{starting_equipment_str}\n"
                f"🗡️ <b>Starting Equipment Options</b>:\n{starting_equipment_options_str}\n"
                f"🔀 <b>Multi-classing Prerequisites</b>:\n{multi_classing_prerequisites_str}\n"
                f"🔀 <b>Multi-classing Proficiencies</b>: {multi_classing_proficiencies_str}\n"
                f"📚 <b>Subclasses</b>: {subclasses_str}\n"
                f"✨ <b>Spellcasting Level</b>: {self.spellcasting.level if self.spellcasting else 'There are no spells'}\n"
                f"✨ <b>Spellcasting Ability</b>: {self.spellcasting.spellcasting_ability.name if self.spellcasting else 'There are no spells'}\n"
                f"✨ <b>Spellcasting Info</b>:\n{spellcasting_info_str}\n")
