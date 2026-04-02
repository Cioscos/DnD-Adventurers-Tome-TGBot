from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class MultiClass:
    classes: Dict[str, int] = field(default_factory=dict)
    max_level: int = 20  # Maximum level a character can reach

    def add_class(self, class_name: str, levels: int = 1):
        """Adds levels to a specified class. If the class does not exist, it is added."""
        if levels < 1:
            raise ValueError("I livelli da aggiungere devono essere un numero intero positivo.")
        if self.total_levels() + levels > self.max_level:
            raise ValueError(
                f"Aggiungere {levels} livelli a {class_name} farebbe eccedere il livello massimo di {self.max_level}.")

        if class_name in self.classes:
            self.classes[class_name] += levels
        else:
            self.classes[class_name] = levels

    def set_class_level(self, class_name: str, levels: int):
        """Sets the level of a specified class. Raises an error if total level exceeds the maximum."""
        if levels < 1:
            raise ValueError("Level must be a positive integer.")
        if class_name not in self.classes:
            raise ValueError(f"Class {class_name} does not exist in this multiclass.")

        current_total_levels = self.total_levels() - self.classes[class_name]
        if current_total_levels + levels > self.max_level:
            raise ValueError(f"Setting {class_name} to level {levels} exceeds the maximum level of {self.max_level}.")

        self.classes[class_name] = levels

    def remove_class(self, class_name: str):
        """Removes a class entirely from the multiclass list."""
        if class_name in self.classes:
            del self.classes[class_name]
        else:
            raise ValueError(f"Class {class_name} does not exist in this multiclass.")

    def get_class_level(self, class_name: str) -> Optional[int]:
        """Returns the level of the specified class, or None if the class is not present."""
        return self.classes.get(class_name, None)

    def total_levels(self) -> int:
        """Returns the total number of levels across all classes."""
        return sum(self.classes.values())

    def list_classes(self) -> str:
        """Returns a string listing all classes and their levels."""
        return '\n'.join(f"{class_name} (Level {level})" for class_name, level in self.classes.items())

    def level_up(self, class_name: str):
        """Levels up the specified class, checking against the maximum total level."""
        if self.total_levels() >= self.max_level:
            raise ValueError(
                f"Cannot level up {class_name}. The character has already reached the maximum level of {self.max_level}.")

        if class_name not in self.classes:
            raise ValueError(f"Class {class_name} does not exist in this multiclass.")

        self.classes[class_name] += 1

    def level_down(self, class_name: str):
        """Levels down the specified class, ensuring it doesn't go below level 1."""
        if class_name not in self.classes:
            raise ValueError(f"Class {class_name} does not exist in this multiclass.")

        if self.classes[class_name] <= 1:
            raise ValueError(f"Cannot level down {class_name}. It is already at the minimum level of 1.")

        self.classes[class_name] -= 1

    def __str__(self):
        return f"MultiClass(classes={self.classes})"

    def __repr__(self):
        return f"MultiClass(classes={self.classes!r})"
