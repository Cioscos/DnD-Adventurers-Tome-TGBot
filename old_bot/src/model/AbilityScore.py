from typing import List, Optional

from src.model.APIResource import APIResource


class AbilityScore(APIResource):
    full_name: str
    desc: List[str]
    skills: Optional[List[APIResource]]
    url: str

    def __repr__(self):
        self.__str__()

    def __str__(self):
        return (f"<b>Nome</b>: {self.full_name}\n"
                f"<b>Descrizione</b>: {" ".join(self.desc)}\n"
                f"<b>Skills</b>: {', '.join([skill.name for skill in self.skills]) if self.skills else "Non ci sono skill"}\n")
