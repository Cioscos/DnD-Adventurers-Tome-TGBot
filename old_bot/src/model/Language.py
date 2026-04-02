from typing import List, Optional

from pydantic import BaseModel, Field

from src.model.APIResource import APIResource


class Language(APIResource):
    desc: str
    type: str
    typical_speakers: List[str]
    script: str

    def __repr__(self):
        self.__str__()

    def __str__(self):
        return (f"<b>Nome</b>: {self.name}\n"
                f"<b>Descrizione</b>: {self.desc}\n"
                f"<b>Parlanti tipici</b>: {', '.join(self.typical_speakers)}\n"
                f"<b>Script</b>: {self.script}")


class LanguageOption(BaseModel):
    option_type: str
    item: Language


class LanguageOptionSet(BaseModel):
    option_set_type: str
    options: Optional[List[LanguageOption]] = None


class LanguageChoice(BaseModel):
    type: str
    choose: int
    from_: LanguageOptionSet = Field(..., alias='from')
