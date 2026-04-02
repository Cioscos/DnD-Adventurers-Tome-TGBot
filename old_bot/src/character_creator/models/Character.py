from dataclasses import field, dataclass
from enum import Enum
from typing import List, Optional, Dict, Tuple, Any

from src.character_creator.models.Ability import Ability, RestorationType
from src.character_creator.models.Currency import Currency
from src.character_creator.models.FeaturePoints import FeaturePoints
from src.character_creator.models.Item import Item
from src.character_creator.models.MultiClass import MultiClass
from src.character_creator.models.Spell import Spell
from src.character_creator.models.SpellSlot import SpellSlot


class SpellsSlotMode(Enum):
    AUTOMATIC = 'automatic'
    MANUAL = 'manual'


@dataclass
class Character:
    VERSION = 8

    name: Optional[str] = field(default=None)
    race: Optional[str] = field(default=None)
    gender: Optional[str] = field(default=None)
    multi_class: MultiClass = field(default_factory=MultiClass)
    hit_points: int = field(default_factory=int)
    base_armor_class: int = field(default_factory=int)
    shield_armor_class: int = field(default_factory=int)
    magic_armor: int = field(default_factory=int)
    current_hit_points: int = field(default_factory=int)
    feature_points: FeaturePoints = field(default_factory=FeaturePoints)
    spell_slots_mode: SpellsSlotMode = field(default=None)
    spell_slots: Dict[int, SpellSlot] = field(default_factory=dict)
    MAX_SPELL_SLOT_LEVEL = 9
    bag: List[Item] = field(default_factory=list)
    spells: List[Spell] = field(default_factory=list)
    abilities: List[Ability] = field(default_factory=list)
    carry_capacity: int = field(default_factory=int)
    currency: Optional[Currency] = field(default_factory=Currency)
    encumbrance: int = field(default_factory=int)
    rolls_history: Optional[List[Tuple[str, list[int]]]] = field(default_factory=list)
    notes: Dict[str, str] = field(default_factory=dict)
    maps: Dict[str, List[str]] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)

    _version: int = field(default_factory=int)

    def __post_init__(self):
        # If the object does not have the version, migration is necessary
        if not hasattr(self, '_version'):
            self._version = 1

        # sets all the feature points to 10
        self.feature_points.points = {
            'strength': 10,
            'dexterity': 10,
            'constitution': 10,
            'intelligence': 10,
            'wisdom': 10,
            'charisma': 10
        }
        self.__reload_stats()

        if self._version < Character.VERSION:
            self.__migrate()

    def __reload_stats(self):
        self.carry_capacity = self.feature_points.strength * 15
        self.encumbrance = sum([item.weight for item in self.bag])

    def __migrate(self):
        """Migrates the data to the current version of the class."""
        if self._version < 2:
            # Migration for version 2: adding the rolls_history field
            if not hasattr(self, 'rolls_history'):
                self.rolls_history = []
        if self._version < 3:
            # Migration for version 3: adding notes
            if not hasattr(self, 'notes'):
                self.notes = {}
        if self._version < 4:
            # Migration for version 4: adding maps
            if not hasattr(self, 'maps'):
                self.maps = {}
        if self._version < 5:
            # Migration for version 5: adding settings
            if not hasattr(self, 'settings'):
                self.settings = {}
        if self._version < 6:
            if not hasattr(self, 'currency'):
                self.currency = Currency()
        if self._version < 8:
            if not hasattr(self, 'base_armor_class'):
                self.base_armor_class = 0
            if not hasattr(self, 'shield_armor_class'):
                self.shield_armor_class = 0
            if not hasattr(self, 'magic_armor'):
                self.magic_armor = 0
        # Update version's object
        self._version = Character.VERSION

    def __setstate__(self, state):
        """Method called during deserialisation"""
        # Updates the status of the object
        self.__dict__.update(state)

        # If the deserialised object does not have a version, we set the default version
        if not hasattr(self, '_version'):
            self._version = 1

        # Migrate if necessary
        if self._version < Character.VERSION:
            self.__migrate()

        self.__reload_stats()

    def add_item(self, item: Item):
        """Add an item to the character's bag and update the encumbrance."""
        # Check if the item already exists in the bag
        for existing_item in self.bag:
            if existing_item == item:
                # Item exists, update the quantity and encumbrance
                existing_item.quantity += item.quantity
                self.encumbrance += item.weight * item.quantity
                return

        # If the item doesn't exist, add it to the bag
        self.bag.append(item)
        self.encumbrance += item.weight * item.quantity

    def increment_item_quantity(self, item_name: str, quantity: int = 1):
        """Increment the quantity of an existing item in the character's bag by a certain amount."""
        for item in self.bag:
            if item.name == item_name:
                item.quantity += quantity
                self.encumbrance += item.weight * quantity
                return

    def decrement_item_quantity(self, item: str, quantity: int = 1):
        """Remove a specific quantity of an item from the character's bag by name."""
        for existing_item in self.bag:
            if existing_item.name == item:
                if existing_item.quantity > quantity:
                    # Reduce the quantity and update encumbrance
                    existing_item.quantity -= quantity
                    self.encumbrance -= existing_item.weight * quantity
                else:
                    # Remove the item completely and update encumbrance
                    self.bag.remove(existing_item)
                    self.encumbrance -= existing_item.weight * existing_item.quantity
                break

    def remove_item(self, item: Item):
        """Remove a specific item from the character's bag."""
        for existing_item in self.bag:
            if existing_item == item:
                # Update encumbrance based on the item's total weight and remove it from the bag
                self.encumbrance -= existing_item.weight * existing_item.quantity
                self.bag.remove(existing_item)
                break

    def list_items(self):
        """List all items in the character's bag."""
        return [str(item) for item in self.bag]

    def available_space(self):
        """Return how much weight is still supportable from the character"""
        return self.carry_capacity - self.encumbrance

    def learn_spell(self, spell: Spell):
        """Adds a spell to the character's spellbook."""
        self.spells.append(spell)

    def forget_spell(self, spell_name: str):
        """Removes a spell from the character's spellbook by name."""
        self.spells = [spell for spell in self.spells if spell.name != spell_name]

    def list_spells(self):
        """Lists all spells the character has learned."""
        return [str(spell) for spell in self.spells]

    def learn_ability(self, ability: Ability):
        """Adds an ability to the character's abilities list."""
        self.abilities.append(ability)

    def use_ability(self, ability: Ability):
        """Use an ability decreasing the uses from the ability object"""
        a = next((a for a in self.abilities if a == ability), None)
        if a:
            a.use_ability()

    def toggle_activate_ability(self, ability: Ability):
        """Activate a passive ability"""
        a = next((a for a in self.abilities if a == ability), None)
        if a:
            a.toggle_activate_ability()

    def forget_ability(self, ability_name: str):
        """Removes an ability from the character's abilities list by name."""
        self.abilities = [ability for ability in self.abilities if ability.name != ability_name]

    def list_abilities(self):
        """Lists all abilities the character has learned."""
        return [str(ability) for ability in self.abilities]

    def use_spell(self, spell_to_use: Spell, spell_level: int = None):
        """Use a spell consuming the proper spell slot"""
        for spell in self.spells:
            if spell.name == spell_to_use.name:
                if spell_level is None:
                    self.use_spell_slot(spell.level.value)
                else:
                    self.use_spell_slot(spell_level)

    def add_spell_slot(self, spell_slot: SpellSlot):
        """Adds or updates a spell slot at a given level."""
        self.spell_slots[spell_slot.level] = spell_slot

    def use_spell_slot(self, level: int):
        """Uses a spell slot at the specified level."""
        if level not in self.spell_slots:
            raise ValueError(f"Nessun slot incantesimo disponibile al livello {level}.")
        self.spell_slots[level].use_slot()

    def restore_spell_slot(self, level: int):
        """Restores a used spell slot at the specified level."""
        if level not in self.spell_slots:
            raise ValueError(f"Nessun slot incantesimo disponibile al livello {level}.")
        self.spell_slots[level].restore_slot()

    def restore_all_spell_slots(self):
        """Restores all used spell slots."""
        for slot in self.spell_slots.values():
            slot.restore_all_slots()

    def add_class(self, class_name: str, levels: int = 1):
        """Adds levels to a specified class using multiclassing."""
        self.multi_class.add_class(class_name, levels)

    def remove_class(self, class_name: str):
        """Removes a class from the character's multiclass."""
        self.multi_class.remove_class(class_name)

    def get_class_level(self, class_name: str) -> Optional[int]:
        """Gets the level of a specified class."""
        return self.multi_class.get_class_level(class_name)

    def list_classes(self) -> str:
        """Lists all classes and their levels for the character."""
        return self.multi_class.list_classes()

    def total_levels(self) -> int:
        """Returns the total number of levels across all classes."""
        return self.multi_class.total_levels()

    def total_classes(self) -> int:
        """Returns the total number of classes across all classes."""
        return len(self.multi_class.classes)

    def list_spell_slots(self):
        """Lists all spell slots and their statuses."""
        return [str(slot) for slot in self.spell_slots.values()]

    def get_rolls_history(self):
        """Return a formatted string of the rolls history"""
        return_str = ''
        for die_name, die_rolls in self.rolls_history:
            return_str += f"{len(die_rolls)}{die_name}: [{', '.join([str(roll) for roll in die_rolls])}] = {sum(die_rolls)}\n"

        return return_str

    def delete_rolls_history(self):
        """Deletes the rolls history"""
        self.rolls_history.clear()

    def change_feature_points(self, feature_points: Dict[str, int]):
        self.feature_points.points = feature_points
        self.__reload_stats()

    def long_rest(self):
        """Do a long rest, restore hitpoints, restore all spell slots, restores abilities which require long rest"""
        self.current_hit_points = self.hit_points
        self.restore_all_spell_slots()
        for ability in self.abilities:
            if ability.restoration_type == RestorationType.LONG_REST:
                ability.uses = ability.max_uses

    def short_rest(self):
        """
        Do a short rest, restores abilities which require short rest.
        It will also restore some hit points in the future implementations
        """
        for ability in self.abilities:
            if ability.restoration_type == RestorationType.SHORT_REST:
                ability.uses = ability.max_uses

    @property
    def ac(self):
        return self.base_armor_class + self.shield_armor_class + self.magic_armor
