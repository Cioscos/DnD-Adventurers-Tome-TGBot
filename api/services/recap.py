"""End-of-evening recap: snapshot computed when a game session closes.

Single close path (``close_game_session``) shared by ``POST /sessions/{id}/close``,
the GM leaving and the idle sweep (api/tasks/session_cleanup.py). The recap is
best effort: a failing computation or Telegram send never blocks the close.
Spec: docs/superpowers/specs/2026-11-03-diario-lore-riepilogo-calendario-design.md
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.services import telegram_notify
from api.services.telegram_notify import recipient_lang
from api.services.campaigns import STASH_USER_ID
from api.services.rules_turn import set_surprised
from core.data.labels import condition_label
from core.db.models import (
    BotUser, Campaign, CampaignMember, Character, CharacterHistory, Combatant, Encounter,
    GameSession, SessionMessage, SessionParticipant, SessionStatus,
)

logger = logging.getLogger(__name__)

# Same abbreviations as the webapp (webapp/src/hooks/useTradeMutation.ts), both languages.
_COIN_ABBR = {"copper": "CP", "silver": "SP", "electrum": "EP", "gold": "GP", "platinum": "PP"}
_MAX_TEXT = 4096


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _duration(created: str, last: str) -> int:
    try:
        return max(0, int((datetime.fromisoformat(last) - datetime.fromisoformat(created)).total_seconds()))
    except (TypeError, ValueError):
        return 0


def dice_baseline(gs: GameSession, char: Character) -> dict:
    """dice_stats_start for a (re)joining PG: the earlier snapshot if it already left this evening."""
    prev = next((d for d in gs.departed or [] if d.get("character_id") == char.id), None)
    if prev is not None and prev.get("dice_stats_start") is not None:
        return copy.deepcopy(prev["dice_stats_start"])
    return copy.deepcopy(char.dice_stats or {})


def record_departure(gs: GameSession, p: SessionParticipant) -> None:
    """Keep a leaving player in the recap: first baseline wins (rejoin reuses it, see dice_baseline)."""
    if p.character_id is None:
        return
    rest = [d for d in gs.departed or [] if d.get("character_id") != p.character_id]
    prev = next((d for d in gs.departed or [] if d.get("character_id") == p.character_id), None)
    start = p.dice_stats_start if prev is None or prev.get("dice_stats_start") is None else prev["dice_stats_start"]
    gs.departed = rest + [{"user_id": p.user_id, "character_id": p.character_id, "dice_stats_start": start}]


def _summary(items: list[dict], coins: dict) -> str:
    """'Pozione ×2, Corda, 15 GP' from a feed payload's item snapshots + coins."""
    parts = [f"{i.get('name')} ×{i['quantity']}" if (i.get("quantity") or 1) > 1 else str(i.get("name"))
             for i in items or []]
    parts += [f"{n} {_COIN_ABBR.get(c, c)}" for c, n in (coins or {}).items() if n]
    return ", ".join(parts)


def _dice(start: dict | None, now: dict | None) -> tuple[int, int, int]:
    """(rolls, nat20, nat1) from the dice_stats diff (clamped: stats may be reset mid-evening).

    start None = joined before the snapshot existed: no baseline, so no dice stats (not a lifetime diff).
    """
    if start is None:
        return 0, 0, 0
    now = now or {}
    diff = {
        kind: {face: max(0, int(n) - int((start.get(kind) or {}).get(face, 0))) for face, n in faces.items()}
        for kind, faces in now.items()
    }
    d20 = diff.get("d20", {})
    return sum(sum(f.values()) for f in diff.values()), d20.get("20", 0), d20.get("1", 0)


def _char_stats(char: Character, start_stats: dict | None, rows: list[CharacterHistory],
                window: tuple[str, str], player_name: str | None) -> dict:
    lo, hi = window
    rolls, nat20, nat1 = _dice(start_stats, char.dice_stats)
    totals = [e.get("total") for e in (char.rolls_history or [])
              if isinstance(e, dict) and lo <= str(e.get("timestamp") or "") <= hi
              and isinstance(e.get("total"), int)]
    st = {
        "character_id": char.id, "name": char.name, "player_name": player_name,
        "class_summary": char.class_summary, "level": char.total_level,
        "dice": {"rolls": rolls, "nat20": nat20, "nat1": nat1, "highest": max(totals) if totals else None},
        "damage_taken": 0, "healed": 0, "downed": 0,
        "death_saves": {"successes": 0, "failures": 0},
        "spells_cast": 0, "slots_used": {}, "rests": {"short": 0, "long": 0}, "conditions": [], "condition_levels": {},
    }
    slots = st["slots_used"]
    for r in rows:
        m, ev = r.meta or {}, r.event_type
        if ev == "hp_change" and m.get("op") == "DAMAGE":
            st["damage_taken"] += int(m.get("amount") or 0)
            st["downed"] += 1 if m.get("to_zero") else 0
        elif ev == "hp_change" and m.get("op") == "HEAL":
            st["healed"] += int(m.get("amount") or 0)
        elif ev == "hit_dice":
            st["healed"] += int(m.get("healed") or 0)
        elif ev == "death_save" and m.get("ds") in ("success", "failure"):
            st["death_saves"]["successes" if m["ds"] == "success" else "failures"] += int(m.get("n") or 1)
        elif ev in ("spell_cast", "spell_ritual_cast"):
            st["spells_cast"] += 1
            if m.get("slot_level") is not None:
                key = str(m["slot_level"])
                slots[key] = slots.get(key, 0) + 1
        elif ev == "spell_slot_used" and m.get("slot_level") is not None:
            key = str(m["slot_level"])
            slots[key] = slots.get(key, 0) + int(m.get("count") or 1)
        elif ev == "rest" and m.get("kind") in ("short", "long"):
            st["rests"][m["kind"]] += 1
        elif ev == "condition_change" and m.get("active") and m.get("slug"):
            if m["slug"] not in st["conditions"]:
                st["conditions"].append(m["slug"])
            if m.get("level"):  # il livello (Spossatezza) è quello dell'ultima modifica; i recap vecchi non l'hanno
                st["condition_levels"][m["slug"]] = int(m["level"])
    return st


def _highlights(chars: list[dict]) -> list[dict]:
    picks = (
        ("unluckiest", lambda c: c["dice"]["nat1"]),
        ("luckiest", lambda c: c["dice"]["nat20"]),
        ("most_damage", lambda c: c["damage_taken"]),
        ("top_healer", lambda c: c["healed"]),
    )
    out = []
    for key, val in picks:
        best = max(chars, key=val, default=None)  # ties: first character wins
        if best is not None and val(best) >= 1:
            out.append({"key": key, "character_id": best["character_id"], "name": best["name"],
                        "value": val(best)})
    return out


async def build_recap(db: AsyncSession, gs: GameSession, ended_at: str) -> dict:
    window = (gs.created_at, ended_at)
    camp = await db.get(Campaign, gs.campaign_id) if gs.campaign_id is not None else None
    number = None
    if camp is not None:
        earlier = await db.scalar(select(func.count()).select_from(GameSession).where(
            GameSession.campaign_id == camp.id, GameSession.status == SessionStatus.CLOSED,
            GameSession.id != gs.id,
            or_(GameSession.created_at < gs.created_at,
                and_(GameSession.created_at == gs.created_at, GameSession.id < gs.id)),
        ))
        number = int(earlier or 0) + 1

    parts = (await db.execute(
        select(SessionParticipant).where(SessionParticipant.session_id == gs.id)
        .order_by(SessionParticipant.id)
    )).scalars().all()
    # (character_id, dice_stats_start): players still at the table, then those who left early.
    pcs = [(p.character_id, p.dice_stats_start) for p in parts if p.character_id is not None]
    present = {cid for cid, _ in pcs}
    pcs += [(d["character_id"], d.get("dice_stats_start")) for d in gs.departed or []
            if d.get("character_id") is not None and d["character_id"] not in present]
    ids = [cid for cid, _ in pcs]
    chars = {c.id: c for c in (await db.execute(
        select(Character).options(selectinload(Character.classes)).where(Character.id.in_(ids))
    )).scalars()} if ids else {}
    player_names: dict[int, str | None] = {}
    if camp is not None and ids:
        player_names = dict((await db.execute(
            select(CampaignMember.character_id, CampaignMember.player_name)
            .where(CampaignMember.character_id.in_(ids))
        )).all())
    rows_by_char: dict[int, list[CharacterHistory]] = {}
    if ids:
        for r in (await db.execute(
            select(CharacterHistory).where(
                CharacterHistory.character_id.in_(ids),
                CharacterHistory.timestamp >= window[0], CharacterHistory.timestamp <= window[1],
            ).order_by(CharacterHistory.id)
        )).scalars():
            rows_by_char.setdefault(r.character_id, []).append(r)
    characters = [
        _char_stats(chars[cid], start, rows_by_char.get(cid, []), window, player_names.get(cid))
        for cid, start in pcs if cid in chars
    ]
    name_by_user = {c.user_id: c.name for c in chars.values()}

    encs = (await db.execute(
        select(Encounter).options(selectinload(Encounter.combatants))
        .where(Encounter.session_id == gs.id, Encounter.started_at.is_not(None))
        .order_by(Encounter.id)
    )).scalars().all()
    monsters: list[str] = []
    for e in encs:
        for c in sorted(e.combatants, key=lambda c: c.id):
            # shortcut: "Goblin 2" -> "Goblin" also strips a number that is part of a real name
            name = re.sub(r" \d+$", "", c.name) if c.kind == "monster" else None
            if name and name not in monsters:
                monsters.append(name)

    gm_grants, trades, stash, lore, places = [], [], [], [], []
    lore_seen: set = set()
    place_seen: set = set()
    for m in (await db.execute(
        select(SessionMessage).where(SessionMessage.session_id == gs.id).order_by(SessionMessage.id)
    )).scalars():
        if m.trade_payload:
            try:
                pl = json.loads(m.trade_payload)
            except ValueError:
                continue
            kind = pl.get("kind")
            frm, to = (pl.get("from") or {}).get("name"), (pl.get("to") or {}).get("name")
            if kind == "lore_reveal":
                if pl.get("lore_id") in lore_seen:  # revealed twice in one evening: list it once
                    continue
                lore_seen.add(pl.get("lore_id"))
                lore.append({"id": pl.get("lore_id"), "title": pl.get("title")})
            elif kind == "atlas_reveal":
                key = (pl.get("map_id"), pl.get("marker_id"))
                if key in place_seen:  # same map/marker revealed again in one evening: list it once
                    continue
                place_seen.add(key)
                places.append({"map_id": pl.get("map_id"), "marker_id": pl.get("marker_id"), "title": pl.get("title")})
            elif kind == "trade":
                trades.append({"from": frm, "to": to, "summary": _summary(pl.get("items"), pl.get("coins"))})
            elif kind in ("stash_put", "stash_take", "gm_stash_add", "gm_stash_remove"):
                who = to if kind == "stash_take" else frm  # "gm" for the GM rows
                stash.append({"kind": kind, "who": who, "summary": _summary(pl.get("items"), pl.get("coins"))})
        elif m.item_name is not None:
            gm_grants.append({"to": name_by_user.get(m.recipient_user_id), "item": m.item_name,
                              "quantity": m.item_quantity or 1})

    return {
        "version": 1, "session_id": gs.id, "campaign_id": gs.campaign_id,
        "campaign_name": camp.name if camp is not None else None, "number": number,
        "started_at": gs.created_at, "ended_at": ended_at,
        "duration_seconds": _duration(gs.created_at, gs.last_activity_at),
        "characters": characters,
        "combat": {"encounters": len(encs), "rounds": sum(e.round or 0 for e in encs), "monsters": monsters},
        "items": {"gm_grants": gm_grants, "trades": trades, "stash": stash},
        "lore": lore,
        "places": places,
        "highlights": _highlights(characters),
    }


async def free_surprised(db: AsyncSession, gs: GameSession) -> None:
    """La sorpresa 2014 è del combattimento: chiusa la sessione nessun GM può più toglierla, quindi cade qui."""
    ids = (await db.execute(select(SessionParticipant.character_id).where(
        SessionParticipant.session_id == gs.id, SessionParticipant.character_id.is_not(None)))).scalars().all()
    if not ids:
        return
    for char in (await db.execute(select(Character).where(Character.id.in_(ids)))).scalars():
        set_surprised(char, False)


async def close_game_session(db: AsyncSession, gs: GameSession) -> None:
    """Close an active session, snapshot its recap, commit, then message the table."""
    if gs.status != SessionStatus.ACTIVE:
        return
    ended_at = _now()
    try:
        recap = await build_recap(db, gs, ended_at)
    except Exception:  # noqa: BLE001 — the close must never fail because of the recap
        logger.exception("Recap build failed for session %s", gs.id)
        recap = None
    gs.status = SessionStatus.CLOSED
    gs.closed_at = ended_at
    gs.recap = recap
    await free_surprised(db, gs)
    await db.commit()
    try:
        await send_recap_messages(db, gs)
    except Exception:  # noqa: BLE001
        logger.exception("Recap messages failed for session %s", gs.id)


# ---------------------------------------------------------------------------
# Telegram text
# ---------------------------------------------------------------------------

_V2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")

_T = {
    "it": {
        "title": "Riepilogo della serata", "evening": "Serata n. {n}", "player": "giocatore",
        "dice": "🎲 {rolls} tiri · {nat20}× 20 naturale · {nat1}× 1 naturale",
        "highest": " · massimo {v}",
        "hp": "❤️ {dmg} danni subiti · {healed} PF curati",
        "downed": " · a 0 PF {n} volte", "ds": "💀 TS morte: {s} successi, {f} fallimenti",
        "spells": "✨ {n} incantesimi", "slots": " · slot {s}",
        "rests": "🏕 Riposi: {s} brevi, {l} lunghi", "conds": "🌀 Condizioni: {c}",
        "combat": "⚔️ Combattimenti: {e} · round {r}", "monsters": "Avversari: {m}",
        "items": "🎁 Oggetti e monete", "grant": "Il master a {to}: {what}", "trade": "{frm} → {to}: {what}",
        "stash_put": "{who} nel deposito: {what}", "stash_take": "{who} dal deposito: {what}",
        "gm_stash_add": "Il master nel deposito: {what}", "gm_stash_remove": "Il master dal deposito: {what}",
        "lore": "📜 Lore rivelata", "places": "🗺 Luoghi scoperti", "highlights": "🏆 Curiosità",
        "unluckiest": "Il più sfortunato ai dadi: {name} ({v}× 1 naturale)",
        "luckiest": "Il più fortunato ai dadi: {name} ({v}× 20 naturale)",
        "most_damage": "Chi ha subito più danni: {name} ({v})",
        "top_healer": "Chi è stato curato di più: {name} ({v} PF)",
        "button": "Apri il riepilogo", "hours": "{h} h {m} min", "minutes": "{m} min",
    },
    "en": {
        "title": "Evening recap", "evening": "Evening #{n}", "player": "player",
        "dice": "🎲 {rolls} rolls · {nat20}× natural 20 · {nat1}× natural 1",
        "highest": " · highest {v}",
        "hp": "❤️ {dmg} damage taken · {healed} HP healed",
        "downed": " · dropped to 0 HP {n} times", "ds": "💀 Death saves: {s} successes, {f} failures",
        "spells": "✨ {n} spells", "slots": " · slots {s}",
        "rests": "🏕 Rests: {s} short, {l} long", "conds": "🌀 Conditions: {c}",
        "combat": "⚔️ Encounters: {e} · rounds {r}", "monsters": "Foes: {m}",
        "items": "🎁 Items and coins", "grant": "GM to {to}: {what}", "trade": "{frm} → {to}: {what}",
        "stash_put": "{who} into the stash: {what}", "stash_take": "{who} from the stash: {what}",
        "gm_stash_add": "GM into the stash: {what}", "gm_stash_remove": "GM from the stash: {what}",
        "lore": "📜 Lore revealed", "places": "🗺 Places discovered", "highlights": "🏆 Highlights",
        "unluckiest": "Unluckiest with dice: {name} ({v}× natural 1)",
        "luckiest": "Luckiest with dice: {name} ({v}× natural 20)",
        "most_damage": "Took the most damage: {name} ({v})",
        "top_healer": "Most healed: {name} ({v} HP)",
        "button": "Open the recap", "hours": "{h} h {m} min", "minutes": "{m} min",
    },
}


def _esc(value: object) -> str:
    """MarkdownV2 escape (every reserved character, backslash included)."""
    return _V2_SPECIAL.sub(r"\\\1", str(value))


def _cond_label(slug: str, lang: str) -> str:
    if recipient_lang(lang) == "it":
        return condition_label(slug)
    return slug.removeprefix("custom:").replace("_", " ").capitalize()


def format_recap_text(recap: dict, lang: str) -> str:
    """MarkdownV2 text, ≤ 4096 chars: cut at a line boundary (markup stays balanced) + «…»."""
    t = _T[recipient_lang(lang)]

    def tr(key: str, **kw) -> str:  # translated template with escaped values
        return _esc(t[key].format(**kw))

    secs = int(recap.get("duration_seconds") or 0)
    h, m = divmod(secs // 60, 60)
    head = [f"*{tr('title')}*"]
    if recap.get("campaign_name"):
        sub = f"*{_esc(recap['campaign_name'])}*"
        if recap.get("number"):
            sub += f" · {tr('evening', n=recap['number'])}"
        head.append(sub)
    head.append(_esc(f"{str(recap.get('started_at') or '')[:10]} · ")
                + (tr("hours", h=h, m=m) if h else tr("minutes", m=m)))
    blocks: list[list[str]] = [head]

    for c in recap.get("characters") or []:
        who = f"*{_esc(c['name'])}*"
        info = [x for x in (c.get("player_name"), c.get("class_summary")) if x]
        if info:
            who += " " + _esc(f"({' · '.join(info)})")
        d = c["dice"]
        dice = t["dice"].format(rolls=d["rolls"], nat20=d["nat20"], nat1=d["nat1"])
        if d.get("highest") is not None:
            dice += t["highest"].format(v=d["highest"])
        hp = t["hp"].format(dmg=c["damage_taken"], healed=c["healed"])
        if c["downed"]:
            hp += t["downed"].format(n=c["downed"])
        lines = [who, _esc(dice), _esc(hp)]
        ds = c["death_saves"]
        if ds["successes"] or ds["failures"]:
            lines.append(tr("ds", s=ds["successes"], f=ds["failures"]))
        if c["spells_cast"] or c["slots_used"]:
            sp = t["spells"].format(n=c["spells_cast"])
            if c["slots_used"]:
                sp += t["slots"].format(s=", ".join(f"{k}°×{v}" for k, v in sorted(c["slots_used"].items())))
            lines.append(_esc(sp))
        if c["rests"]["short"] or c["rests"]["long"]:
            lines.append(tr("rests", s=c["rests"]["short"], l=c["rests"]["long"]))
        if c["conditions"]:
            lv = c.get("condition_levels") or {}
            lines.append(tr("conds", c=", ".join(
                _cond_label(x, lang) + (f" {lv[x]}" if x in lv else "") for x in c["conditions"])))
        blocks.append(lines)

    combat = recap.get("combat") or {}
    if combat.get("encounters"):
        lines = [tr("combat", e=combat["encounters"], r=combat.get("rounds", 0))]
        if combat.get("monsters"):
            lines.append(tr("monsters", m=", ".join(combat["monsters"])))
        blocks.append(lines)

    items = recap.get("items") or {}
    item_lines = [tr("grant", to=g.get("to") or "?", what=f"{g['item']} ×{g['quantity']}")
                  for g in items.get("gm_grants") or []]
    item_lines += [tr("trade", frm=x.get("from"), to=x.get("to"), what=x.get("summary"))
                   for x in items.get("trades") or []]
    item_lines += [tr(x["kind"], who=x.get("who"), what=x.get("summary"))
                   for x in items.get("stash") or [] if x.get("kind") in t]
    if item_lines:
        blocks.append([f"*{tr('items')}*"] + [_esc("• ") + ln for ln in item_lines])
    if recap.get("lore"):
        blocks.append([f"*{tr('lore')}*"] + [_esc(f"• {x.get('title')}") for x in recap["lore"]])
    if recap.get("places"):  # missing key on pre-Task-3 recaps: simply no block
        blocks.append([f"*{tr('places')}*"] + [_esc(f"• {x.get('title')}") for x in recap["places"]])
    if recap.get("highlights"):
        blocks.append([f"*{tr('highlights')}*"] + [
            tr(x["key"], name=x["name"], v=x["value"]) for x in recap["highlights"] if x.get("key") in t])

    out: list[str] = []
    size = 0
    for i, block in enumerate(blocks):
        for ln in ([""] if i else []) + block:
            if size + len(ln) + 1 > _MAX_TEXT - 2:  # room for "\n…"
                return "\n".join(out) + "\n…"
            out.append(ln)
            size += len(ln) + 1
    return "\n".join(out)


async def send_recap_messages(db: AsyncSession, gs: GameSession) -> int:
    """Private recap to the GM and every participant. Only with SEND_CAMPAIGN_MESSAGES=1."""
    if os.environ.get("SEND_CAMPAIGN_MESSAGES") != "1" or not telegram_notify.bot_token_configured():
        return 0
    if not gs.recap:
        return 0
    users = list((await db.execute(
        select(SessionParticipant.user_id).where(SessionParticipant.session_id == gs.id)
    )).scalars())
    users += [d["user_id"] for d in gs.departed or [] if d.get("user_id") is not None]
    recipients = [u for u in dict.fromkeys([gs.gm_user_id, *users]) if u != STASH_USER_ID]
    langs = dict((await db.execute(
        select(BotUser.user_id, BotUser.language_code).where(BotUser.user_id.in_(recipients))
    )).all()) if recipients else {}
    sent = 0
    for uid in recipients:
        lang = recipient_lang(langs.get(uid))
        button = None
        if gs.campaign_id is not None:
            button = (_T[lang]["button"], telegram_notify.miniapp_url(f"/campaign/{gs.campaign_id}/recap/{gs.id}"))
        if await telegram_notify.send_telegram_message(
                uid, format_recap_text(gs.recap, lang), parse_mode="MarkdownV2", button=button):
            sent += 1
    return sent
