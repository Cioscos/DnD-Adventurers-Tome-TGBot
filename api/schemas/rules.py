from pydantic import BaseModel


class SubclassRead(BaseModel):
    key: str
    name: dict[str, str]
    choice_level: int
