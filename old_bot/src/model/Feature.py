from typing import List

from pydantic import Field

from src.model.APIResource import APIResource
from src.model.subclasses import Prerequisite


class Feature(APIResource):
    class_: APIResource = Field(..., alias='class')
    level: int
    prerequisites: List[Prerequisite]
    desc: List[str]
    url: str

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        prerequisites_str = "\n".join([str(prereq) for prereq in (self.prerequisites or [])])
        desc_str = "\n".join(self.desc)

        return (f"<b>Feature</b>: {self.name} ({self.index})\n"
                f"<b>Class</b>: {self.class_.name} ({self.class_.index})\n"
                f"<b>Level</b>: {self.level}\n"
                f"<b>Prerequisites</b>:\n{prerequisites_str if prerequisites_str else 'None'}\n"
                f"<b>Description</b>:\n{desc_str}\n"
                f"<b>URL</b>: {self.url}")
