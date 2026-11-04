from pydantic import BaseModel


class SubclassRead(BaseModel):
    key: str
    name: dict[str, str]
    choice_level: int


class ProficiencyGrantRead(BaseModel):
    armor: list[str]
    weapons: list[str]
    tools: list[str]
    saves: list[str]
    skills_from: list[str]
    skills_count: int
    languages: list[str]


class RollOptionCost(BaseModel):
    feature_key: str | None = None
    amount: int = 1
    spell_slot_min: int | None = None


class RollOptionSlot(BaseModel):
    level: int
    available: int
    dice: str | None = None


class RollOptionRead(BaseModel):
    key: str
    phase: str
    label: str
    source: str
    dice: str | None = None
    bonus: int | None = None
    mode: str | None = None
    multiplier: float | None = None
    once_per_turn: bool = False
    slot: str | None = None
    needs: str | None = None
    requires_input: str | None = None
    input_options: list[RollOptionSlot] = []
    auto_fail: bool = False
    cost: RollOptionCost | None = None
