# Design — Gruppo H: Chat/cronologia integrata

**Data:** 2026-04-24
**Stato:** design validato, pronto per plan
**Branch:** `feat/chat-history-gruppo-h`
**Sezioni `istruzioni.md` coperte:** §3 (Cronologia).

---

## 1. Scope

Fondere chat + cronologia in un unico feed nella sessione di gioco:

1. Endpoint `GET /sessions/{code}/feed` — mix di messaggi chat + eventi history degli char nella sessione, filtrati per sessione corrente e ordinati cronologicamente.
2. Redaction per-viewer delle azioni HP altrui (heal → "Si è curato", set → "Ha modificato i PF"; damage passthrough).
3. Frontend: SessionRoom sostituisce il box chat con un feed misto (`SessionFeed` component dedicato). Bottone "Carica precedenti" per paginazione.
4. `CharacterHistory` acquisisce un campo `meta: JSON` per facilitare redaction pulita (op per HP events).

### Out of scope
- Pagina `/char/:id/history` (Gestore Personaggio) invariata — resta solo-own, nessuna redaction. L'utente vede sempre la propria cronologia completa lì.
- Nessun infinite-scroll automatico — solo bottone "Carica precedenti" esplicito.
- Nessuna modifica al motore di chat (send/receive messages) — resta via `POST /sessions/{id}/messages`.

---

## 2. Decisioni chiave

| Tema | Scelta | Motivo |
|---|---|---|
| Integrazione chat/history | Feed unico cronologico misto | §3 "integrata nella chat" |
| Scope eventi | Subset gaming-relevant (hp_change, rest, skill_roll, saving_throw, attack_roll, death_save, condition_change, concentration_save, hit_dice) | Bilanciamento rumore vs completezza |
| Finestra temporale | `session.created_at` → presente | §3 "solo sessione corrente" |
| Endpoint | Unico `/sessions/{code}/feed` con schema misto | Meno roundtrip rispetto a due query separate |
| Paginazione | Bottone "Carica precedenti" (tap) con cursor `before=<ts>` | Esplicito, controllato |
| Gestore personaggio | Invariato (only-own) | Distinzione netta tra contesto privato e pubblico |

### Mapping redaction (solo per viewer != owner AND !is_gm)

| Event type + op | Description esposta al viewer |
|---|---|
| `hp_change` op=HEAL | `"<character_name> si è curato"` |
| `hp_change` op=SET_CURRENT / SET_MAX / SET_TEMP | `"<character_name> ha modificato i PF"` |
| `hp_change` op=DAMAGE | passthrough (già visibile via HP bucket in session-live) |
| Altri event_type | passthrough (nessuna redaction) |

---

## 3. Backend

### 3.1 Schema change — `character_history.meta`

Aggiungere nullable JSON column:

```python
# core/db/models.py — CharacterHistory
class CharacterHistory(Base):
    __tablename__ = "character_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # new
```

Migration in `core/db/engine.py::_MIGRATIONS`:
```python
("character_history", "meta", "ALTER TABLE character_history ADD COLUMN meta JSON"),
```

Aggiornare `_add_history(session, char_id, event_type, description, meta=None)` in `api/routers/characters.py` (o modulo dove vive). Per `hp_change`, il caller passa `meta={'op': 'HEAL'|'DAMAGE'|'SET_CURRENT'|'SET_MAX'|'SET_TEMP'}`.

Legacy rows: `meta is None` → redaction cade in fallback parsing description.

### 3.2 Endpoint `GET /sessions/{code}/feed`

**Path:** `/sessions/{code}/feed`
**Auth:** `get_current_user` + `_assert_participant` (partecipante della session).
**Query params:**
- `since` (opt, ISO): ritorna items con `timestamp > since`, asc.
- `before` (opt, ISO): ritorna items con `timestamp < before`, desc; flipped to asc client-side.
- `limit` (opt, default 100, max 500).
- `since` e `before` sono **mutex** (se entrambi presenti → 400).
- Assenza di entrambi: ultimi `limit` items, asc.

**Response:**

```python
class SessionFeedItem(BaseModel):
    type: Literal["message", "event"]
    timestamp: str                               # ISO, always

    # message-only fields
    message_id: Optional[int] = None
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    role: Optional[str] = None                   # "game_master" | "player"
    body: Optional[str] = None
    recipient_user_id: Optional[int] = None

    # event-only fields
    event_id: Optional[int] = None
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    owner_user_id: Optional[int] = None
    event_type: Optional[str] = None
    description: Optional[str] = None            # redacted per viewer
    op: Optional[str] = None                     # from meta.op, when present (hp_change)


class SessionFeedResponse(BaseModel):
    items: list[SessionFeedItem]
    has_more: bool = False                       # true if limit was reached
```

**Logica:**

1. Load session by code; assert participant caller.
2. Query `SessionMessage.where(session_id, sent_at >= session.created_at, timestamp filter)`.
3. Query `CharacterHistory.where(character_id IN participants_char_ids, timestamp >= session.created_at, event_type IN allowed_set, timestamp filter)`.
   - `allowed_set = {'hp_change', 'rest', 'skill_roll', 'saving_throw', 'attack_roll', 'death_save', 'condition_change', 'concentration_save', 'hit_dice'}`.
4. Build items:
   - Messages: filter whisper visibility — se `recipient_user_id != None` e viewer `!= sender && != recipient && !is_gm` → escludi.
   - Events: enrich con `character_name` (join Character) + `owner_user_id`. Apply redaction per viewer.
5. Merge + sort ASC by timestamp; stable tie-breaker by `type` then numeric id.
6. If `since`: cap at top N=limit, asc.
   If `before`: take last N items before cursor (desc query, then reverse).
7. Return `items[]` + `has_more`.

### 3.3 Redaction function

```python
def redact_event_description(
    event: CharacterHistory,
    character_name: str,
    viewer_user_id: int,
    owner_user_id: int,
    is_gm: bool,
) -> str:
    # Owner or GM see raw.
    if viewer_user_id == owner_user_id or is_gm:
        return event.description

    # Only hp_change is redacted.
    if event.event_type != "hp_change":
        return event.description

    meta = event.meta or {}
    op = (meta.get("op") or "").upper()

    if op == "HEAL":
        return f"{character_name} si è curato"
    if op in ("SET_CURRENT", "SET_MAX", "SET_TEMP"):
        return f"{character_name} ha modificato i PF"
    if op == "DAMAGE":
        return event.description  # passthrough

    # Legacy fallback (meta missing): heuristic on description text.
    desc_lower = event.description.lower()
    if "curat" in desc_lower or "heal" in desc_lower:
        return f"{character_name} si è curato"
    if "danno" in desc_lower or "damage" in desc_lower:
        return event.description  # passthrough
    # Unknown: treat as safe-default "ha modificato i PF"
    return f"{character_name} ha modificato i PF"
```

I18n: le stringhe "si è curato" / "ha modificato i PF" possono essere tradotte/personalizzate. Per semplicità vengono hardcoded backend in italiano (l'app è italiana primaria). Una futura i18n su backend-generated strings richiederebbe locale hints dal client — YAGNI.

### 3.4 `_add_history` signature change

```python
def _add_history(
    session,
    char_id: int,
    event_type: str,
    description: str,
    meta: dict | None = None,
) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
        meta=meta,
    ))
```

Chiamata interna di ogni HP op esistente: passare `meta={"op": op.upper()}` dove `op` ∈ {"HEAL", "DAMAGE", "SET_CURRENT", "SET_MAX", "SET_TEMP"}`. Check in `api/routers/hp.py` where HP mutations happen.

---

## 4. Frontend

### 4.1 Nuovo componente `SessionFeed.tsx`

Path: `webapp/src/pages/session/SessionFeed.tsx`.

**Props:**
```ts
interface Props {
  code: string
  sessionId: number
  amGm: boolean
  gmUserId: number | null
  myUserId: number
  participants: SessionParticipant[]
}
```

**Stato:**
```ts
const [items, setItems] = useState<SessionFeedItem[]>([])
const [hasMore, setHasMore] = useState(false)
const [chatInput, setChatInput] = useState('')
const [whisperTo, setWhisperTo] = useState<number | null>(null)
```

**Polling:** TanStack Query `useQuery({ queryKey: ['session-feed', code, latestTs], queryFn: ..., refetchInterval: 3000 })`. Endpoint chiamato con `since` = timestamp dell'ultimo item in state (incremental fetch). Merge append.

**Initial fetch:** `GET /sessions/{code}/feed?limit=100` (no `since`/`before`).

**Carica precedenti:** bottone in cima. Al click: `GET /sessions/{code}/feed?before=<oldest_ts>&limit=50`. Prepend risultato. Se `has_more=false` o risposta vuota → nascondi bottone.

**Render items:**
- `type: "message"`: chat bubble esistente (mine gold, other surface, whisper amber).
- `type: "event"`: bubble di sistema, centered, stile discreto:

```tsx
<div className="flex items-center gap-2 text-xs text-dnd-text-muted italic justify-center px-3 py-1.5 opacity-80">
  <Icon size={12} className={meta.tone} />
  <span className="font-body">{item.description}</span>
  <span className="font-mono text-[10px] text-dnd-text-faint">
    {formatTime(item.timestamp)}
  </span>
</div>
```

**Send message:** `POST /sessions/{id}/messages` invariato. Su `onSuccess`: `qc.invalidateQueries(['session-feed', code, ...])` per fetch immediato.

**Auto-scroll:** dopo ogni merge items, scroll bottom (ref a scroll container). "Carica precedenti" NON auto-scroll (preserva posizione utente).

### 4.2 Estrazione `EVENT_META`

Da `webapp/src/pages/History.tsx` a `webapp/src/lib/eventMeta.ts`:

```ts
import type { LucideIcon } from 'lucide-react'
import {
  Heart, Moon, Shield, Swords, Gem, Sparkles, Backpack,
  Coins, Zap, Skull, CircleDot, Pin, Target, ShieldAlert,
  FlaskConical, Dices,
} from 'lucide-react'

export interface EventMeta {
  icon: LucideIcon
  tone: string
}

export const EVENT_META: Record<string, EventMeta> = {
  hp_change: { ... },
  rest: { ... },
  // ...all entries from History.tsx...
  other: { icon: Pin, tone: '...' },
}
```

`History.tsx` importa dal nuovo modulo. `SessionFeed.tsx` idem.

### 4.3 Modifica `SessionRoom.tsx`

Sostituisci il box chat inline con:

```tsx
<SectionDivider>
  {t('session.chat_and_history')}
</SectionDivider>

<SessionFeed
  code={live.code}
  sessionId={live.id}
  amGm={amGm}
  gmUserId={gmUserId}
  myUserId={myUserId}
  participants={live.participants}
/>
```

Rimuovi tutto lo stato locale di chat (chatCache, sendMutation, scrollerRef, whisperTo → spostati dentro SessionFeed).

**Nota refactor:** la logica di whisper-target, input, send, polling è interamente spostata a `SessionFeed`. SessionRoom conserva solo la parte participants + banner + leave/close.

### 4.4 API client + types

`webapp/src/types/index.ts`:

```ts
export interface SessionFeedItem {
  type: 'message' | 'event'
  timestamp: string

  // message
  message_id?: number | null
  user_id?: number | null
  display_name?: string | null
  role?: string | null
  body?: string | null
  recipient_user_id?: number | null

  // event
  event_id?: number | null
  character_id?: number | null
  character_name?: string | null
  owner_user_id?: number | null
  event_type?: string | null
  description?: string | null
  op?: string | null
}

export interface SessionFeedResponse {
  items: SessionFeedItem[]
  has_more: boolean
}
```

`webapp/src/api/client.ts`:
```ts
sessions: {
  // ...existing...
  getFeed: (code: string, opts?: { since?: string; before?: string; limit?: number }) => {
    const params = new URLSearchParams()
    if (opts?.since) params.set('since', opts.since)
    if (opts?.before) params.set('before', opts.before)
    if (opts?.limit) params.set('limit', String(opts.limit))
    const q = params.toString()
    return request<SessionFeedResponse>(
      `/sessions/${encodeURIComponent(code)}/feed${q ? `?${q}` : ''}`
    )
  },
}
```

### 4.5 i18n keys nuove

```json
"session": {
  "chat_and_history": "Chat e cronologia",
  "feed_empty": "Nessun messaggio o evento ancora",
  "load_previous": "Carica precedenti",
  "loading_previous": "Caricamento…"
}
```

(Mirror EN: "Chat & History", "No messages or events yet", "Load previous", "Loading…".)

---

## 5. File impattati

### Nuovi
- `webapp/src/lib/eventMeta.ts`
- `webapp/src/pages/session/SessionFeed.tsx`

### Modificati backend
- `core/db/models.py` (CharacterHistory `meta` column).
- `core/db/engine.py` (migration).
- `api/routers/characters.py` (`_add_history` signature + callers passing `meta`).
- `api/routers/hp.py` (HP op → meta passed through).
- `api/schemas/session.py` (`SessionFeedItem`, `SessionFeedResponse`).
- `api/routers/sessions.py` (endpoint `/feed`).

### Modificati frontend
- `webapp/src/pages/History.tsx` (import `EVENT_META` da lib).
- `webapp/src/pages/SessionRoom.tsx` (sostituisce chat inline con `<SessionFeed />`).
- `webapp/src/types/index.ts` (`SessionFeedItem`, `SessionFeedResponse`).
- `webapp/src/api/client.ts` (`api.sessions.getFeed`).
- `webapp/src/locales/it.json` + `en.json` (nuove chiavi).

### Invariati
- `api/routers/history.py` (endpoint `/characters/{id}/history` invariato).
- Bot.

---

## 6. Edge cases

1. Sessione zero eventi → feed vuoto, placeholder `session.feed_empty`.
2. Char cancellato durante sessione → FK cascade cancella eventi; scompaiono dal feed.
3. Join tardivo → vede tutta la sessione da `created_at` (scelta 4A).
4. Whisper → filtrato backend per viewer (sender, recipient, GM).
5. Send message → `qc.invalidateQueries(['session-feed', ...])` per vedere proprio messaggio senza attendere poll.
6. Legacy `meta = None` → fallback heuristic; default safe "ha modificato i PF" su ambiguo.
7. Session chiusa → endpoint 404/403; SessionRoom gestisce già.
8. Timestamp clash stesso secondo → tie-breaker `type` + numeric id stable.
9. `since` e `before` entrambi → 400 Bad Request.
10. `has_more=false` → "Carica precedenti" nascosto.
11. `CharacterHistory.character_id IN (...)` lista vuota (sessione senza player con char) → query skippata, solo messaggi ritornati.

---

## 7. Acceptance criteria

- [ ] Migration `meta` column crea campo senza rompere DB esistente.
- [ ] HP ops (damage, heal, set_*) loggano con `meta.op`.
- [ ] Endpoint `/feed` ritorna items misti ordinati ASC.
- [ ] Redaction applicata solo per non-owner non-GM su hp_change.
- [ ] Damage events passthrough; heal → "si è curato"; set → "ha modificato i PF".
- [ ] Legacy events senza meta → fallback ragionevole.
- [ ] Whisper visibili solo a sender, recipient, GM.
- [ ] Paginazione `before` funziona; `has_more` corretto.
- [ ] Frontend SessionFeed sostituisce chat box inline.
- [ ] Bottone "Carica precedenti" visibile se `has_more`.
- [ ] Send message invalida query + appare immediatamente.
- [ ] `EVENT_META` condiviso tra History.tsx e SessionFeed senza duplicazione.
- [ ] Gestore personaggio `/char/:id/history` invariato.
- [ ] Nessuna regressione chat/whisper esistente.

---

## 8. Dipendenze / rischi

- **Migration DB** — `meta` column è nullable, retrocompatibile. `_migrate_schema` esegue al lifespan API (CLAUDE.md).
- **Rischio basso** refactor SessionRoom — estrazione feed in component dedicato separa concerns; chat state (cacheLocal, polling, whisper) tutto in SessionFeed.
- **Performance**: ogni polling carica fino a 100 items. Se sessione molto lunga con molti eventi, può crescere. `since` cursor mitiga (fetch incrementale solo nuovi).
- **Ordering tie-break**: messaggio e evento con stesso timestamp-secondo → ordine stabile ma arbitrario. Accettabile per UI.
