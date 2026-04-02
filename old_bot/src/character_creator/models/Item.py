from dataclasses import dataclass, field
from typing import Optional

from src.model.models import Currency


@dataclass
class Item:
    VERSION = 2

    name: str
    description: Optional[str] = field(default=None)
    quantity: int = 0
    weight: int = 0
    currency: Optional[Currency] = field(default=None)

    _version: int = field(default_factory=int)

    def __migrate(self):
        """Migrates the data to the current version of the class."""
        if self._version < 2:
            # Migration for version 2: adding the rolls_history field
            if not hasattr(self, 'currency'):
                self.currency = None

    def __setstate__(self, state):
        """Method called during deserialisation"""
        # Updates the status of the object
        self.__dict__.update(state)

        # If the deserialised object does not have a version, we set the default version
        if not hasattr(self, '_version'):
            self._version = 1

        # Migrate if necessary
        if self._version < Item.VERSION:
            self.__migrate()

    def __post_init__(self):
        # If the object does not have the version, migration is necessary
        if not hasattr(self, '_version'):
            self._version = 1

        if self._version < Item.VERSION:
            self.__migrate()

        # Validation for name and description
        if not self.name:
            raise ValueError("Item name cannot be empty.")
        if self.description is None:
            self.description = ""  # Default to empty string if no description provided

        # Validation for quantity
        if not isinstance(self.quantity, int) or self.quantity < 0:
            raise ValueError("Quantity must be a non-negative integer.")

    def __str__(self):
        desc = self.description if self.description else "No description provided"
        return f"Item(name={self.name}, description={desc}, quantity={self.quantity})"

    def __repr__(self):
        return f"Item(name={self.name!r}, description={self.description!r}, quantity={self.quantity!r})"

    def __eq__(self, other):
        if not isinstance(other, Item):
            return NotImplemented
        return self.name == other.name

    def increase_quantity(self, amount: int):
        """Increase the quantity by the given amount."""
        if amount < 0:
            raise ValueError("Increase amount must be non-negative.")
        self.quantity += amount

    def decrease_quantity(self, amount: int):
        """Decrease the quantity by the given amount."""
        if amount < 0:
            raise ValueError("Decrease amount must be non-negative.")
        if amount > self.quantity:
            raise ValueError("Cannot decrease quantity below zero.")
        self.quantity -= amount
