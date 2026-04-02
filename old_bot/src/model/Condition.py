from typing import List

from src.model.APIResource import APIResource


class Condition(APIResource):
    desc: List[str]

    def __repr__(self):
        self.__str__()

    def __str__(self):
        return (f"<b>Nome</b>: {self.name}\n"
                f"<b>Descrizione</b>:\n{"\n".join(self.desc)}")
