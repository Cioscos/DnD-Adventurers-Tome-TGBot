"""Esportazione del personaggio: download JSON e invio come documento in chat."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.routers.characters import _refresh_char_full
from api.schemas.character import CharacterFull
from api.schemas.ddb_import import DdbImportRequest, DdbImportResult
from api.schemas.transfer import CharacterExport
from api.services.character_response import build_character_response
from api.services.character_transfer import build_export, import_character, load_for_export
from api.services.class_features import sync_cataloged_features, sync_class_feature_abilities
from core.rules.feature_sync import mark_ability_bonuses
from api.services.ddb_import import (
    DdbImportError, ImportReport, ReportEntry, class_option_names, convert, fetch_ddb, parse_ddb_id,
)
from api.services.spell_slots import recalc_spell_slots
from api.services.telegram_notify import bot_token_configured, send_telegram_document
from core.data.classes import class_table_key
from core.rules.catalog import features_for
from core.rules.edition import character_edition, class_key
from core.rules.level_choices import active_choice_specs, apply_grants
from core.rules.types import RuleContext

router = APIRouter(prefix="/characters", tags=["transfer"])


async def _get_owned(char_id: int, user_id: int, session: AsyncSession):
    char = await load_for_export(session, char_id)
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


def _filename(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "personaggio"
    return f"{slug}-{datetime.now(timezone.utc):%Y%m%d}.json"


@router.get("/{char_id}/export", response_model=CharacterExport)
async def export_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> Response:
    char = await _get_owned(char_id, user_id, session)
    data = await build_export(session, char)
    return Response(
        content=data.model_dump_json(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{_filename(char.name)}"'},
    )


@router.post("/{char_id}/export/send")
async def send_export(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    char = await _get_owned(char_id, user_id, session)
    if not bot_token_configured():
        raise HTTPException(status_code=503, detail="Bot not configured")
    data = await build_export(session, char)
    ok = await send_telegram_document(
        user_id, _filename(char.name), data.model_dump_json().encode("utf-8"), caption=char.name
    )
    if not ok:
        raise HTTPException(status_code=502, detail="Telegram delivery failed")
    return {"ok": True}


_MAX_IMPORT_BYTES = 1_000_000
_SUFFIX = {"it": {"import": " (importato)", "dup": " (copia)"}, "en": {"import": " (imported)", "dup": " (copy)"}}


async def _import_body(request: Request) -> bytes:
    limit = _MAX_IMPORT_BYTES + 4096  # margine per l'envelope multipart
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail="File too large")
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > limit:
            raise HTTPException(status_code=413, detail="File too large")
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        sent = False

        async def replay():  # il body e' gia' stato consumato: lo riproponiamo a form()
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": raw, "more_body": False}

        upload = (await Request(request.scope, replay).form()).get("file")
        if upload is None or isinstance(upload, str):
            raise HTTPException(status_code=422, detail="Missing 'file' field")
        raw = await upload.read()
    if len(raw) > _MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    return raw


async def _create_from(session: AsyncSession, user_id: int, data: CharacterExport, lang: str, kind: str) -> CharacterFull:
    char = await import_character(session, user_id, data, name_suffix=_SUFFIX.get(lang, _SUFFIX["it"])[kind])
    char = await _refresh_char_full(session, char.id, user_id)
    if "rules_edition" in data.character.model_fields_set:
        await sync_cataloged_features(session, char, lang, retrofit=True)  # i punteggi del file sono già quelli finali (R34)
    else:  # un file vecchio resta com'è, ma i bonus ai punteggi si segnano comunque come applicati
        mark_ability_bonuses(char)
        await session.flush()
    char = await _refresh_char_full(session, char.id, user_id)
    return await build_character_response(session, char)


@router.post("/import", response_model=CharacterFull, status_code=status.HTTP_201_CREATED)
async def import_character_endpoint(
    request: Request,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    raw = await _import_body(request)
    try:
        data = CharacterExport.model_validate_json(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=422, detail=e.errors(include_url=False, include_context=False, include_input=False)
        )
    # Campaign ids belong to this server's DB: never trust them from a file.
    for rec in data.character.notes.values():
        if isinstance(rec, dict):
            rec.pop("campaign_id", None)
    return await _create_from(session, user_id, data, lang, "import")


_DDB_STATUS = {"ddb_unreachable": 502, "edition_required": 409}


def _ddb_error(code: str) -> HTTPException:
    return HTTPException(status_code=_DDB_STATUS.get(code, 422), detail={"code": code})


@router.post("/import/ddb", response_model=DdbImportResult, status_code=status.HTTP_201_CREATED)
async def import_ddb_character(
    body: DdbImportRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> DdbImportResult:
    ddb_id = parse_ddb_id(body.url)
    if ddb_id is None:
        raise _ddb_error("invalid_link")
    try:
        ddb = await fetch_ddb(ddb_id)
        export, report, feature_uses = convert(ddb, lang, body.rules_edition)
    except DdbImportError as e:
        raise _ddb_error(e.code)
    char = await import_character(session, user_id, export, name_suffix=_SUFFIX.get(lang, _SUFFIX["it"])["import"])
    char = await _refresh_char_full(session, char.id, user_id)
    _apply_class_options(char, class_option_names(ddb), report, lang)
    for cls in char.classes:
        if class_table_key(cls.class_name) is not None:
            await sync_class_feature_abilities(session, char, cls, lang=lang, retrofit=True)  # Beyond somma già i modificatori di classe
    await _apply_feature_uses(session, char, feature_uses)
    await recalc_spell_slots(session, char)
    char = await _refresh_char_full(session, char.id, user_id)
    return DdbImportResult(character=await build_character_response(session, char), report=report)


def _norm_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()).strip()


def _apply_class_options(char, option_names: list[dict], report: ImportReport, lang: str) -> None:
    """Opzioni scelte su DDB (Metamagia, Invocazioni...) -> `CharacterClass.options` secondo il catalogo
    dell'edizione. Quelle che nessun gruppo della classe riconosce restano nel report."""
    edition = character_edition(char)
    classes = sorted(char.classes, key=lambda c: c.id)  # stesso ordine di export.classes
    for idx, cls in enumerate(classes):
        wanted = [o["name"] for o in option_names if o["class_index"] == idx]
        if not wanted:
            continue
        ctx = RuleContext(char=char, edition=edition, class_row=cls, class_level=cls.level)
        specs = features_for(edition, class_key(cls))
        chosen: dict[str, list[str]] = {}
        free = list(wanted)  # ogni nome sulla scheda DDB riempie un posto solo (l'Aquila scelta due volte sono due nomi)
        for ch in active_choice_specs(char, cls):
            reached = [lvl for lvl in ch.levels if lvl <= cls.level]
            limit = ch.levels[max(reached)] if reached else 0
            names: dict[str, str] = {}
            families: dict[str, list[str]] = {}  # Ripetibili («Agonizing Blast: Eldritch Blast»): la famiglia è il nome prima dei due punti
            for key in (ch.import_options or ch.options)(ctx):
                for spec in specs:
                    if spec.option_group == ch.group and spec.option_key == key:
                        names.update({_norm_name(n): key for n in spec.name.values()})
                        for n in spec.name.values():
                            if ":" in n:
                                families.setdefault(_norm_name(n.split(":")[0]), []).append(key)
                if ch.label is not None:
                    label = ch.label(key).get("name", "")  # una stringa, o {it, en} come lo vuole l'interfaccia
                    for text in (label.values() if isinstance(label, dict) else [label]):
                        names[_norm_name(text)] = key
            for name in list(free):
                key = names.get(_norm_name(name))
                if key is not None and key not in chosen.get(ch.group, []) and len(chosen.get(ch.group, [])) < limit:
                    chosen.setdefault(ch.group, []).append(key)
                    free.remove(name)
            allowed: set[str] | None = None  # calcolato solo se serve: legge gli incantesimi del personaggio
            for name in list(free):  # DDB non dice il trucchetto: se il personaggio ne conosce uno solo ammesso, è quello
                if _norm_name(name) not in families:
                    continue
                allowed = set(ch.options(ctx)) if allowed is None else allowed
                picks = [k for k in dict.fromkeys(families[_norm_name(name)]) if k in allowed and k not in chosen.get(ch.group, [])]
                if len(picks) == 1 and len(chosen.get(ch.group, [])) < limit:
                    chosen.setdefault(ch.group, []).append(picks[0])
                    free.remove(name)
        if chosen:
            cls.options = {**(cls.options or {}), **chosen}
            for ch in active_choice_specs(char, cls):
                apply_grants(char, ch, chosen.get(ch.group, []))
        for name in free:
            report.approximated.append(ReportEntry(section="options", name=name, reason="ddb.reason.option_unknown"))


def _find_feature(char, cls_id: int, slug: str):
    # chiave come parole intere ovunque nel nome: "Font of Magic: Sorcery Points" -> sorcery_points
    return next((a for a in char.abilities if a.is_class_feature and a.source_class_id == cls_id
                 and a.feature_key and f"_{a.feature_key.split('.', 1)[-1]}_" in f"_{slug}_"), None)


# DDB 2024 chiama «Focus Points» i punti ki: l'alias vale anche per le classi a catalogo (la riserva ha la chiave 2014 `ki`)
_LEGACY_ALIASES = {"focus_points": "ki_points"}


async def _apply_feature_uses(session: AsyncSession, char, feature_uses: list[dict]) -> None:
    """Cariche usate DDB -> feature del nostro motore; il doppione generico del convertitore sparisce."""
    classes = sorted(char.classes, key=lambda c: c.id)  # stesso ordine di export.classes
    best: dict[int, tuple] = {}
    for fu in feature_uses:
        if not 0 <= fu["class_index"] < len(classes):
            continue
        slug = re.sub(r"[^a-z0-9]+", "_", fu["name"].lower()).strip("_")
        cls = classes[fu["class_index"]]
        feat = _find_feature(char, cls.id, slug)
        if feat is None:
            feat = _find_feature(char, cls.id, _LEGACY_ALIASES.get(slug, slug))
        # più voci DDB per la stessa feature ("Rage (Enter)" 6, "Rage: Regain Expended Uses" 1):
        # la riserva vera è quella con più cariche, le altre restano abilità a sé
        # chiave = oggetto, non feat.id: le feature appena create dal motore non hanno ancora un id
        if feat is not None and (id(feat) not in best or fu.get("max", 0) > best[id(feat)][1].get("max", 0)):
            best[id(feat)] = (feat, fu)
    edition = character_edition(char)
    owner = {c.id: c for c in classes}
    for feat, fu in best.values():
        # Classe a catalogo: il massimo lo calcola il motore per l'edizione del PG. Fuori catalogo vince quello di
        # DDB, perché la tabella 2014 non conosce le regole 2024 (es. Ira 2024 = 6, non illimitata).
        if fu.get("max") and not features_for(edition, class_key(owner[feat.source_class_id])):
            feat.max_uses = fu["max"]
        if feat.max_uses is not None:
            feat.uses = max(0, feat.max_uses - fu["used"])
        for dup in [a for a in char.abilities if not a.is_class_feature and a.name == fu["name"]]:
            char.abilities.remove(dup)
            await session.delete(dup)


@router.post("/{char_id}/duplicate", response_model=CharacterFull, status_code=status.HTTP_201_CREATED)
async def duplicate_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session)
    data = await build_export(session, char)
    return await _create_from(session, user_id, data, lang, "dup")
