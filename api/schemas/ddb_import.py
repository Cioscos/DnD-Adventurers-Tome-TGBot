"""Import da D&D Beyond: richiesta (link della scheda) e risposta (PG creato + report)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from api.schemas.character import CharacterFull
from api.services.ddb_import import ImportReport
from core.rules.types import Edition


class DdbImportRequest(BaseModel):
    url: str = Field(max_length=300)
    # Edizione scelta dall'utente; serve solo se le classi del PG non ne indicano una sola (409 edition_required)
    rules_edition: Optional[Edition] = None


class DdbImportResult(BaseModel):
    character: CharacterFull
    report: ImportReport
