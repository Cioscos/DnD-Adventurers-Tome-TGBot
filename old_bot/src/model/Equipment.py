from typing import List, Optional, Union

from pydantic import BaseModel

from src.model.APIResource import APIResource


class Cost(BaseModel):
    quantity: int
    unit: str


class Damage(BaseModel):
    damage_dice: str
    damage_type: APIResource


class Range(BaseModel):
    long: Optional[int] = None
    normal: Optional[int] = None


class ArmorClass(BaseModel):
    base: Optional[int] = None
    dex_bonus: Optional[bool] = None
    max_bonus: Optional[int] = None


class Speed(BaseModel):
    quantity: int
    unit: str


class Rarity(BaseModel):
    name: str


class Content(BaseModel):
    quantity: int
    item: APIResource


class Equipment(APIResource):
    cost: Optional[Cost] = None
    desc: List[str]
    equipment_category: APIResource
    weight: Optional[float] = None

    # weapon
    category_range: Optional[str] = None
    damage: Optional[Damage] = None
    properties: Optional[List[APIResource]] = None
    range: Optional[Range] = None
    special: Optional[List[str]] = None
    throw_range: Optional[Range] = None
    two_handed_damage: Optional[Damage] = None
    weapon_category: Optional[Union[str, APIResource]] = None
    weapon_range: Optional[str] = None

    # tool
    tool_category: Optional[Union[str, APIResource]] = None

    # gear
    gear_category: Optional[Union[str, APIResource]] = None

    # pack
    contents: Optional[List[Content]] = None

    # Ammunition
    quantity: Optional[int] = None

    # Armor
    armor_category: Optional[Union[str, APIResource]] = None
    armor_class: Optional[ArmorClass] = None
    stealth_disadvantage: Optional[bool] = None
    str_minimum: Optional[int] = None

    # vehicle
    capacity: Optional[str] = None
    speed: Optional[Speed] = None
    vehicle_category: Optional[Union[str, APIResource]] = None

    # Magic item
    rarity: Optional[Rarity] = None

    class Config:
        arbitrary_types_allowed = True

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        desc_str = "\n".join(self.desc)
        properties_str = ", ".join([prop.name for prop in (self.properties or [])])
        special_str = "\n".join(self.special or [])

        details = (
            f"<b>Name</b>: {self.name} ({self.index})\n"
            f"<b>Cost</b>: {self.cost.quantity} {self.cost.unit}\n" if self.cost else ""
                                                                                      f"<b>Description</b>:\n{desc_str}\n"
                                                                                      f"<b>Category</b>: {self.equipment_category.name} ({self.equipment_category.index})\n"
        )

        if self.weight:
            details += f"<b>Weight</b>: {self.weight} lb\n"
        if self.category_range:
            details += f"<b>Category Range</b>: {self.category_range}\n"
        if self.damage:
            details += (
                f"<b>Damage</b>: {self.damage.damage_dice} "
                f"({self.damage.damage_type.name})\n"
            )
        if properties_str:
            details += f"<b>Properties</b>: {properties_str}\n"
        if self.range:
            details += (
                f"<b>Range</b>: Normal {self.range.normal} ft., "
                f"Long {self.range.long or 'N/A'} ft.\n"
            )
        if special_str:
            details += f"<b>Special</b>:\n{special_str}\n"
        if self.throw_range:
            details += (
                f"<b>Throw Range</b>: Normal {self.throw_range.normal} ft., "
                f"Long {self.throw_range.long or 'N/A'} ft.\n"
            )
        if self.two_handed_damage:
            details += (
                f"<b>Two-Handed Damage</b>: {self.two_handed_damage.damage_dice} "
                f"({self.two_handed_damage.damage_type.name})\n"
            )
        if self.weapon_category:
            details += f"<b>Weapon Category</b>: {self.weapon_category if isinstance(self.weapon_category, str) else self.weapon_category.name}\n"
        if self.weapon_range:
            details += f"<b>Weapon Range</b>: {self.weapon_range}\n"
        if self.tool_category:
            details += f"<b>Tool Category</b>: {self.tool_category if isinstance(self.tool_category, str) else self.tool_category.name}\n"
        if self.gear_category:
            details += f"<b>Gear Category</b>: {self.gear_category if isinstance(self.gear_category, str) else self.gear_category.name}\n"
        if self.quantity:
            details += f"<b>Quantity</b>: {self.quantity}\n"
        if self.armor_category:
            details += f"<b>Armor Category</b>: {self.armor_category if isinstance(self.armor_category, str) else self.armor_category.name}\n"
        if self.armor_class:
            details += (
                f"<b>Armor Class</b>: Base {self.armor_class.base}, "
                f"Dex Bonus {'Yes' if self.armor_class.dex_bonus else 'No'}"
            )
            if self.armor_class.max_bonus:
                details += f", Max Bonus {self.armor_class.max_bonus}"
            details += "\n"
        if self.stealth_disadvantage:
            details += f"<b>Stealth Disadvantage</b>: {'Yes' if self.stealth_disadvantage else 'No'}\n"
        if self.str_minimum:
            details += f"<b>Strength Minimum</b>: {self.str_minimum}\n"
        if self.capacity:
            details += f"<b>Capacity</b>: {self.capacity}\n"
        if self.speed:
            details += f"<b>Speed</b>: {self.speed.quantity} {self.speed.unit}\n"
        if self.vehicle_category:
            details += f"<b>Vehicle Category</b>: {self.vehicle_category if isinstance(self.vehicle_category, str) else self.vehicle_category.name}\n"
        if self.rarity:
            details += f"<b>Rarity</b>: {self.rarity.name}\n"

        return details
