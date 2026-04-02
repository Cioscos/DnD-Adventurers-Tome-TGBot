from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SpellLevel(Enum):
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5
    LEVEL_6 = 6
    LEVEL_7 = 7
    LEVEL_8 = 8
    LEVEL_9 = 9


@dataclass
class Spell:
    name: Optional[str] = field(default=None)
    description: Optional[str] = field(default=None)
    level: SpellLevel = SpellLevel.LEVEL_1  # Default to LEVEL_1 if not specified

    def __post_init__(self):
        # Validate that the name and description are not empty if provided
        if self.name is None or self.name == "":
            raise ValueError("Spell name cannot be empty.")

        # If description is not provided, default it to an empty string
        if self.description is None:
            self.description = ""

    def __str__(self):
        desc = self.description if self.description else "No description provided"
        return f"Spell(name={self.name}, description={desc}, level={self.level.name})"

    def __repr__(self):
        return f"Spell(name={self.name!r}, description={self.description!r}, level={self.level.name!r})"
