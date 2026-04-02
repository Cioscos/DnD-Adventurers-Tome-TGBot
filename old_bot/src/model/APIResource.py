from pydantic import BaseModel


class APIResource(BaseModel):
    index: str
    name: str
    url: str

    def __repr__(self):
        return f"{self.name} ({self.index})"
