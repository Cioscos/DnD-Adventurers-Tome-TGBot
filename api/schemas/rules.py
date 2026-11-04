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
