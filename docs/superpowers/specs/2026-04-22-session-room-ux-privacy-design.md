# Session Room UX & Privacy — Design

**Date:** 2026-04-22
**Scope:** Telegram Mini App — session room and character-delete interaction
**Status:** Approved, ready for implementation plan

## Goals

Seven user-reported improvements to the in-session experience:

1. **Clickable own character** from participant row (navigation to `/char/{id}`)
2. **Privacy summary** of HP and armor for other players (bucketed, not raw)
3. **GM↔player whispers** — private 1:1 chat within a session
4. **Hide invite code** from players (GM-only)
5. **Gate join button** — disabled until code + character are valid
6. **Fix message sender label** — show character name, not `#{user_id}`
7. **Auto-leave session** when character is deleted

Plus one carry from Spec B for UI consistency: use interpolated exhaustion label in ParticipantRow condition pills.

---

## Non-goals

- Real-time WebSocket chat (polling stays)
- Player↔player whispers (explicitly scoped out — GM ↔ player only)
- Whisper ephemerality (messages persist and cascade-delete with session)
- New armor-category column on Character (derived from equipped Item)

---

## Schema changes

Two additive columns in `session_messages`, registered in `core/db/engine.py::_MIGRATIONS`:

```sql
ALTER TABLE session_messages ADD COLUMN recipient_user_id BIGINT NULL;
CREATE INDEX ix_session_messages_recipient ON session_messages(recipient_user_id);
ALTER TABLE session_messages ADD COLUMN sender_display_name VARCHAR(120) NULL;
```

- `recipient_user_id IS NULL` → broadcast (existing behavior preserved for prior rows).
- `recipient_user_id` non-null → whisper; visible only to sender and recipient.
- `sender_display_name` snapshot at send-time — survives participant leave / character rename.

SQLAlchemy model update in `core/db/models.py::SessionMessage`:

```python
recipient_user_id: Mapped[Optional[int]] = mapped_column(
    BigInteger, nullable=True, index=True
)
sender_display_name: Mapped[Optional[str]] = mapped_column(
    String(120), nullable=True
)
```

Cascade already set on `session_messages.session_id` — whisper cleanup is automatic on session close.

---

## API — privacy redaction

`GET /sessions/{id}/live` computes `CharacterLiveSnapshot` per viewer.

**Viewer is GM or owns this character** → full snapshot (all existing fields preserved, plus new `hp_bucket`, `armor_category`).

**Viewer is other player** → redacted snapshot:
- `hit_points`, `current_hit_points`, `temp_hp`, `ac` → `None`
- `death_saves` → `None`
- `hp_bucket`, `armor_category` → always populated (source of truth for redacted view)
- `name`, `class_summary`, `race`, `total_level`, `conditions`, `heroic_inspiration`, `last_roll` → visible

**`hp_bucket` computation** (server-side, in `_load_live_characters` or a new helper):

```
if char.death_saves.get("failures", 0) >= 3: "dead"
elif char.current_hit_points <= 0:          "dying"
else:
    pct = (current_hit_points / hit_points) * 100
    if pct >= 76: "healthy"
    elif pct >= 51: "lightly_wounded"
    elif pct >= 1:  "badly_wounded"
    else:           "dying"   # guard for 0 HP edge
```

**`armor_category` computation:**

```
Load characters with selectinload(Character.items).
For each char:
    equipped_armor = next(
        (i for i in char.items if i.item_type == "armor" and i.is_equipped),
        None,
    )
    if equipped_armor is None: "unarmored"
    else:
        meta = json.loads(equipped_armor.item_metadata or "{}")
        category = meta.get("armor_type") or "unarmored"  # "light" | "medium" | "heavy"
```

Schema update — `api/schemas/session.py::CharacterLiveSnapshot`:

```python
hit_points: Optional[int] = None           # was int
current_hit_points: Optional[int] = None   # was int
temp_hp: Optional[int] = None              # was int = 0
ac: Optional[int] = None                   # was int
death_saves: Optional[dict[str, Any]] = None
hp_bucket: Optional[str] = None           # NEW
armor_category: Optional[str] = None      # NEW
```

Making existing fields `Optional` is backwards-compatible for self/GM views (still populated) and correctly expresses the redacted shape.

---

## API — whispers

`SessionMessageCreate` extends:

```python
class SessionMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    recipient_user_id: Optional[int] = None
```

`SessionMessageRead` extends:

```python
recipient_user_id: Optional[int] = None
sender_display_name: Optional[str] = None
```

`POST /sessions/{id}/messages` validation:

1. If `recipient_user_id is not None`:
   - Must be a participant of the same session (else 400 `"Recipient not in session"`).
   - Cannot equal sender (else 400 `"Cannot whisper to yourself"`).
   - Either sender's role == `GAME_MASTER` **or** recipient's role == `GAME_MASTER` (else 403 `"Whispers are GM-only"`).
2. Compute `sender_display_name`:
   - If sender role == GM → store literal `"__GM__"` sentinel.
   - Else → store `participant.display_name` (character name captured at join; fallback to `f"#{user_id}"` if null).

`GET /sessions/{id}/messages` visibility filter:

```sql
SELECT * FROM session_messages
WHERE session_id = :sid
  AND (
    recipient_user_id IS NULL       -- broadcast
    OR recipient_user_id = :me      -- whisper to me
    OR user_id = :me                -- whisper from me
  )
ORDER BY id ASC;
```

Existing `after_id` + `limit` params continue to work.

---

## API — character delete auto-leave

`DELETE /characters/{id}` in `api/routers/characters.py`:

```python
# Before deleting the character, remove any active SessionParticipant row
# that pins this character. Runs in the same transaction as the delete.
stmt = (
    select(SessionParticipant)
    .join(GameSession, GameSession.id == SessionParticipant.session_id)
    .where(
        SessionParticipant.user_id == user_id,
        SessionParticipant.character_id == char.id,
        GameSession.status == SessionStatus.ACTIVE,
    )
)
participant = (await db.execute(stmt)).scalar_one_or_none()
if participant is not None:
    # Only players are bound to a character; GM participant has character_id=None.
    await db.delete(participant)
    # touch session activity
    session = await db.get(GameSession, participant.session_id)
    if session: session.last_activity_at = _now()

# Proceed with existing delete flow (cascade handles items/spells/etc.)
```

No schema change — `character_id` foreign key on `SessionParticipant` already uses `ondelete="SET NULL"`, which we explicitly avoid by removing the row first.

---

## Frontend — SessionRoom

**`webapp/src/pages/SessionRoom.tsx`:**

### Hero card

Wrap code-display `Surface` in `{amGm && (...)}`. For non-GM, render replacement:

```tsx
<Surface variant="sigil" ornamented>
  <FancyHeader
    title={live.title ?? t('session.active_session_banner')}
    subtitle={t('session.role_player')}
  />
</Surface>
```

### ParticipantRow refactor

New prop: `isOwn: boolean`. When `isOwn` → wrap row content in `<button>` with `onClick={() => navigate(\`/char/\${snapshot.id}\`)}`. Otherwise static `<div>` (no click). GM clicking a player's row does not navigate (constraint per Q6).

Redacted rendering branch: when `snapshot.hit_points === null`:
- Hide the `current/max` + temp HP display; replace with bucket badge:
  ```tsx
  <span className="text-xs font-cinzel uppercase tracking-wider">
    {t(`session.hp_bucket.${snapshot.hp_bucket}`)}
  </span>
  ```
- Hide AC number; replace with armor-category chip (shield icon + localized category).
- Replace HP gradient bar with a solid color tied to bucket (healthy=emerald, lightly=gold, badly=amber, dying=crimson, dead=neutral/black).
- Death saves UI already hidden by existing conditional.

### Chat sender label

Render `m.sender_display_name` with one sentinel swap:

```tsx
function senderLabel(m: SessionMessage, t): string {
  if (m.sender_display_name === '__GM__' || (m.role === 'game_master' && !m.sender_display_name))
    return t('session.game_master')
  return m.sender_display_name ?? t('session.unknown_sender')
}
```

### Whisper UI

Below chat input, pre-send recipient selector:

- **Player:** single toggle chip `[🔒 Sussurra al GM]`. Off by default. Clicking flips — when on, input has amber border and send dispatches with `recipient_user_id = gm_user_id`.
- **GM:** dropdown `<select>` of `[Tutti, <player1>, <player2>, ...]`. Default `Tutti` (broadcast). Selecting a player makes send a whisper to them.

Whisper message rendering:
- Border/background tinted amber + lock icon prefix.
- Italic body.
- Always show `→ {recipient_name}` label at top of the bubble (both for sender and recipient of the whisper).

### Shared condition helper

Extract `formatCondition(key, val, t)` to new `webapp/src/lib/conditions.ts`:

```ts
export function formatCondition(
  key: string,
  val: unknown,
  t: (k: string, opts?: any) => string,
): string {
  if (key === 'exhaustion' && typeof val === 'number' && val > 0)
    return t('character.conditions.exhaustion', { level: val })
  return t(`character.conditions.${key}`)
}
```

Reused in `SessionRoom.conditionLabels` and `CharacterMain.tsx:319`.

---

## Frontend — SessionJoin

**`webapp/src/pages/SessionJoin.tsx`:**

```tsx
const canJoin = code.trim().length === 6 && effectiveCharId !== null
// ...
<Button
  disabled={!canJoin || joinMutation.isPending}
  loading={joinMutation.isPending}
  onClick={submit}
>
```

Remove the client-side validation branches for "code-length" and "no-character" inside `submit()` (the button can no longer fire when they would fail). Keep `ApiError` handling for server rejections (409, 410, etc).

---

## Frontend — i18n keys added

Both `it.json` and `en.json`:

```
session.hp_bucket.healthy          = "In salute"          / "Healthy"
session.hp_bucket.lightly_wounded  = "Lievemente ferito"  / "Lightly wounded"
session.hp_bucket.badly_wounded    = "Gravemente ferito"  / "Badly wounded"
session.hp_bucket.dying            = "Morente"            / "Dying"
session.hp_bucket.dead             = "Morto"              / "Dead"
session.armor_category.unarmored   = "Senza armatura"     / "Unarmored"
session.armor_category.light       = "Armatura leggera"   / "Light armor"
session.armor_category.medium      = "Armatura media"     / "Medium armor"
session.armor_category.heavy       = "Armatura pesante"   / "Heavy armor"
session.whisper.to_gm              = "Sussurra al GM"     / "Whisper to GM"
session.whisper.broadcast          = "Tutti"              / "Everyone"
session.whisper.recipient_prefix   = "→ {{name}}"         / "→ {{name}}"
session.unknown_sender             = "Sconosciuto"        / "Unknown"
```

---

## TypeScript types (webapp/src/types.ts)

Extend existing:

```ts
export type HpBucket = 'healthy' | 'lightly_wounded' | 'badly_wounded' | 'dying' | 'dead'
export type ArmorCategory = 'unarmored' | 'light' | 'medium' | 'heavy'

export interface CharacterLiveSnapshot {
  id: number
  name: string
  // ... existing fields; these become nullable:
  hit_points: number | null
  current_hit_points: number | null
  temp_hp: number | null
  ac: number | null
  death_saves: Record<string, unknown> | null
  // NEW:
  hp_bucket: HpBucket | null
  armor_category: ArmorCategory | null
}

export interface SessionMessage {
  id: number
  user_id: number
  role: string
  body: string
  sent_at: string
  recipient_user_id: number | null  // NEW
  sender_display_name: string | null // NEW
}
```

`api/client.ts` `sendMessage` signature extends to accept optional `recipient_user_id`.

---

## Testing strategy (manual)

No automated test suite in repo. Two-browser local stack + `DEV_USER_ID` swap between Chrome and Firefox (or two Chrome profiles):

| # | Scenario | Pass criteria |
|---|---|---|
| 1 | GM creates session | Code visible in hero, player view shows no code |
| 2 | HP privacy | Damage GM's test char; player sees bucket change healthy → lightly → badly → dying |
| 3 | Armor privacy | Equip light vs heavy armor on GM's char; player view reflects category change |
| 4 | Whisper isolation | GM whispers player A; player B `/messages` response (Network tab) must not include whisper row |
| 5 | Player↔player whisper blocked | POST `/sessions/.../messages` with two player IDs → 403 |
| 6 | Chat sender name | Player posts message → GM view shows character name, not `#user_id` |
| 7 | Historical name preserved | Player leaves session → old message from that player still shows their character name |
| 8 | Character delete auto-leave | Player deletes character while in session → participant row gone, session list updates |
| 9 | Join gating | Join page button disabled until 6-char code + char selected |
| 10 | Own-card click | Clicking own ParticipantRow navigates to `/char/{id}`; others do nothing |
| 11 | Migration idempotency | Restart API twice; no ALTER error |

---

## Open questions / risks

- **Session polling and whisper staleness:** polling interval is 2s. Whispers appear with up to 2s lag — acceptable per existing UX baseline.
- **GM leaving session:** existing `leave_session` closes the session when GM leaves, which matches whisper lifecycle (cascades). No new logic needed.
- **Migration data for existing messages:** new columns default to NULL; existing rows remain broadcast (correct). `sender_display_name` for old rows stays NULL → fallback renderer shows `#{user_id}` for pre-migration messages only (acceptable — no data loss, only historical messages affected).
