from dataclasses import dataclass


@dataclass
class SpellSlot:
    level: int
    total_slots: int
    used_slots: int = 0

    def use_slot(self):
        """Uses one spell slot if available."""
        if self.used_slots >= self.total_slots:
            raise ValueError(f"Non ci sono slot di livello {self.level} disponibili!")
        self.used_slots += 1

    def restore_slot(self):
        """Restores one used spell slot."""
        if self.used_slots <= 0:
            raise ValueError(f"Tutti gli slot incantesimo di livello {self.level} sono già disponibili!")
        self.used_slots -= 1

    def restore_all_slots(self):
        """Restores all used spell slots to their total amount."""
        self.used_slots = 0

    def slots_remaining(self) -> int:
        """Returns the number of remaining spell slots."""
        return self.total_slots - self.used_slots

    def __str__(self):
        return (f"SpellSlot(level={self.level}, total_slots={self.total_slots}, "
                f"used_slots={self.used_slots}, remaining_slots={self.slots_remaining()})")

    def __repr__(self):
        return (f"SpellSlot(level={self.level!r}, total_slots={self.total_slots!r}, "
                f"used_slots={self.used_slots!r}, remaining_slots={self.slots_remaining()!r})")
