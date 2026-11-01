"""Import da D&D Beyond: richiesta (link della scheda) e risposta (PG creato + report)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from api.schemas.character import CharacterFull
from api.services.ddb_import import ImportReport


class DdbImportRequest(BaseModel):
    url: str = Field(max_length=300)


class DdbImportResult(BaseModel):
    character: CharacterFull
    report: ImportReport
