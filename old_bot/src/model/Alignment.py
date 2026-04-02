from src.model.APIResource import APIResource


class Alignment(APIResource):
    abbreviation: str
    desc: str

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return (f"<b>Nome: </b> {self.name}\n"
                f"<b>Descrizione: </b> {self.desc}\n")
