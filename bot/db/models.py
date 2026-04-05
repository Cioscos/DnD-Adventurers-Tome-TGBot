"""SQLAlchemy ORM models for D&D character management.

All models use async-compatible patterns.  The ``Base`` is shared across all
tables so ``init_db()`` can create everything in one call.
"""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SpellSlotsMode(str, PyEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class RestorationType(str, PyEnum):
    LONG_REST = "long_rest"
    SHORT_REST = "short_rest"
    NONE = "none"


class FileType(str, PyEnum):
    PHOTO = "photo"
    DOCUMENT = "document"


class PartyMode(str, PyEnum):
    PUBLIC = "public"
    PRIVATE = "private"


# ---------------------------------------------------------------------------
# Character (root entity)
# ---------------------------------------------------------------------------

class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Optional lore fields
    race: Mapped[Optional[str]] = mapped_column(String(100))
    gender: Mapped[Optional[str]] = mapped_column(String(50))

    # Hit points
    hit_points: Mapped[int] = mapped_column(Integer, default=0)
    current_hit_points: Mapped[int] = mapped_column(Integer, default=0)

    # Armor class components
    base_armor_class: Mapped[int] = mapped_column(Integer, default=10)
    shield_armor_class: Mapped[int] = mapped_column(Integer, default=0)
    magic_armor: Mapped[int] = mapped_column(Integer, default=0)

    # Encumbrance
    carry_capacity: Mapped[int] = mapped_column(Integer, default=150)
    encumbrance: Mapped[float] = mapped_column(Float, default=0.0)

    # Spell slots
    spell_slots_mode: Mapped[str] = mapped_column(
        Enum(SpellSlotsMode), default=SpellSlotsMode.MANUAL
    )

    # Concentration tracking
    concentrating_spell_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("spells.id", ondelete="SET NULL"), nullable=True
    )

    # Flexible JSON fields
    rolls_history: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Party feature: whether this character is the user's active party character
    is_party_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # Active conditions (JSON dict: condition_slug → bool or int for exhaustion)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Relationships
    classes: Mapped[List["CharacterClass"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    ability_scores: Mapped[List["AbilityScore"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    spells: Mapped[List["Spell"]] = relationship(
        back_populates="character", cascade="all, delete-orphan",
        foreign_keys="[Spell.character_id]",
    )
    spell_slots: Mapped[List["SpellSlot"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    items: Mapped[List["Item"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    currency: Mapped[Optional["Currency"]] = relationship(
        back_populates="character",
        cascade="all, delete-orphan",
        uselist=False,
    )
    abilities: Mapped[List["Ability"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    maps: Mapped[List["Map"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )

    @property
    def ac(self) -> int:
        return self.base_armor_class + self.shield_armor_class + self.magic_armor

    @property
    def total_level(self) -> int:
        return sum(c.level for c in self.classes)

    @property
    def class_summary(self) -> str:
        if not self.classes:
            return "Nessuna classe"
        parts = []
        for c in self.classes:
            part = f"{c.class_name} {c.level}"
            if c.subclass:
                part += f" ({c.subclass})"
            parts.append(part)
        return " / ".join(parts)

    def recalculate_encumbrance(self) -> None:
        self.encumbrance = sum(i.weight * i.quantity for i in self.items)

    def recalculate_carry_capacity(self) -> None:
        strength_score = next(
            (s.value for s in self.ability_scores if s.name == "strength"), 10
        )
        self.carry_capacity = strength_score * 15


# ---------------------------------------------------------------------------
# CharacterClass (multiclassing)
# ---------------------------------------------------------------------------

class CharacterClass(Base):
    __tablename__ = "character_classes"
    __table_args__ = (UniqueConstraint("character_id", "class_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    subclass: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    character: Mapped["Character"] = relationship(back_populates="classes")
    resources: Mapped[List["ClassResource"]] = relationship(
        back_populates="character_class", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# AbilityScore (FOR, DES, COS, INT, SAG, CAR)
# ---------------------------------------------------------------------------

ABILITY_NAMES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


# ---------------------------------------------------------------------------
# ClassResource (class-specific resource like Ki points, Rage uses, etc.)
# ---------------------------------------------------------------------------

class ClassResource(Base):
    """A class-specific resource (Ki points, Rage uses, etc.) linked to a CharacterClass."""
    __tablename__ = "class_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("character_classes.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    current: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    restoration_type: Mapped[str] = mapped_column(
        Enum(RestorationType), default=RestorationType.NONE
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    character_class: Mapped["CharacterClass"] = relationship(back_populates="resources")

    def use(self) -> None:
        if self.current <= 0:
            raise ValueError(f"Nessuna risorsa disponibile: '{self.name}'.")
        self.current -= 1

    def restore_all(self) -> None:
        self.current = self.total


class AbilityScore(Base):
    __tablename__ = "ability_scores"
    __table_args__ = (UniqueConstraint("character_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=10)

    character: Mapped["Character"] = relationship(back_populates="ability_scores")

    @property
    def modifier(self) -> int:
        return (self.value - 10) // 2


# ---------------------------------------------------------------------------
# Spell
# ---------------------------------------------------------------------------

class Spell(Base):
    __tablename__ = "spells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Extended D&D 5e properties
    casting_time: Mapped[Optional[str]] = mapped_column(String(100))
    range_area: Mapped[Optional[str]] = mapped_column(String(100))
    components: Mapped[Optional[str]] = mapped_column(String(200))
    duration: Mapped[Optional[str]] = mapped_column(String(100))
    is_concentration: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ritual: Mapped[bool] = mapped_column(Boolean, default=False)
    higher_level: Mapped[Optional[str]] = mapped_column(Text)
    attack_save: Mapped[Optional[str]] = mapped_column(String(100))
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    character: Mapped["Character"] = relationship(
        back_populates="spells", foreign_keys=[character_id]
    )


# ---------------------------------------------------------------------------
# SpellSlot
# ---------------------------------------------------------------------------

class SpellSlot(Base):
    __tablename__ = "spell_slots"
    __table_args__ = (UniqueConstraint("character_id", "level"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[int] = mapped_column(Integer, default=0)

    character: Mapped["Character"] = relationship(back_populates="spell_slots")

    @property
    def available(self) -> int:
        return max(0, self.total - self.used)

    def use_slot(self) -> None:
        if self.used >= self.total:
            raise ValueError(f"Nessuno slot disponibile al livello {self.level}.")
        self.used += 1

    def restore_slot(self) -> None:
        if self.used > 0:
            self.used -= 1

    def restore_all(self) -> None:
        self.used = 0


# ---------------------------------------------------------------------------
# Item (bag)
# ---------------------------------------------------------------------------

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    character: Mapped["Character"] = relationship(back_populates="items")


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

class Currency(Base):
    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    copper: Mapped[int] = mapped_column(Integer, default=0)
    silver: Mapped[int] = mapped_column(Integer, default=0)
    electrum: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    platinum: Mapped[int] = mapped_column(Integer, default=0)

    character: Mapped["Character"] = relationship(back_populates="currency")

    # Conversion rates to copper
    RATES = {"copper": 1, "silver": 10, "electrum": 50, "gold": 100, "platinum": 1000}

    def total_in_copper(self) -> int:
        return sum(
            getattr(self, k) * v for k, v in self.RATES.items()
        )

    def convert(self, source: str, target: str, amount: int) -> bool:
        """Convert *amount* of *source* currency to *target*. Returns True on success."""
        source_copper = self.RATES[source] * amount
        target_amount = source_copper // self.RATES[target]
        remainder_copper = source_copper % self.RATES[target]
        if getattr(self, source) < amount:
            return False
        setattr(self, source, getattr(self, source) - amount)
        setattr(self, target, getattr(self, target) + target_amount)
        self.copper += remainder_copper
        return True


# ---------------------------------------------------------------------------
# Ability (special abilities / features)
# ---------------------------------------------------------------------------

class Ability(Base):
    __tablename__ = "abilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer)
    uses: Mapped[Optional[int]] = mapped_column(Integer)
    is_passive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    restoration_type: Mapped[str] = mapped_column(
        Enum(RestorationType), default=RestorationType.NONE
    )

    character: Mapped["Character"] = relationship(back_populates="abilities")

    def use(self) -> None:
        if self.max_uses is not None and self.uses is not None:
            if self.uses <= 0:
                raise ValueError(f"Nessun uso rimanente per '{self.name}'.")
            self.uses -= 1

    def restore(self) -> None:
        if self.max_uses is not None:
            self.uses = self.max_uses


# ---------------------------------------------------------------------------
# Map (zone → Telegram file_id)
# ---------------------------------------------------------------------------

class Map(Base):
    __tablename__ = "maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    zone_name: Mapped[str] = mapped_column(String(200), nullable=False)
    file_id: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(Enum(FileType), default=FileType.PHOTO)

    character: Mapped["Character"] = relationship(back_populates="maps")


# ---------------------------------------------------------------------------
# GroupMember (party feature — tracks who has written in each group)
# ---------------------------------------------------------------------------

class GroupMember(Base):
    """Records every Telegram user that has ever sent a message in a group."""

    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


# ---------------------------------------------------------------------------
# PartySession (party feature — one active session per group)
# ---------------------------------------------------------------------------

class PartySession(Base):
    """An active party tracking session for a Telegram group."""

    __tablename__ = "party_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # One session per group at a time
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    group_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    mode: Mapped[str] = mapped_column(Enum(PartyMode), default=PartyMode.PUBLIC)
    # Where the live party message lives (group_id for public, master's user_id for private)
    message_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
