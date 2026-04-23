# Privacy Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split character identity fields into public/private, expose a per-character `show_private_identity` setting, and add a session-room flow to view another participant's identity via a bottom-sheet respecting that setting.

**Architecture:** Flag stored in existing `char.settings` JSON (no DB migration). New backend endpoint `GET /sessions/{code}/participants/{user_id}/identity` returns `IdentityView` with public fields always populated and private fields populated only when target's flag is `True` (or caller == target). Frontend reorganizes `Identity.tsx` into public/private blocks, adds a `Privacy` sub-section to `Settings.tsx`, makes non-GM participant rows in `SessionRoom.tsx` clickable to open a new `ParticipantIdentitySheet` modal.

**Tech Stack:** FastAPI/Pydantic (backend), SQLAlchemy async session, React + TypeScript + TanStack Query (frontend), Tailwind + framer-motion.

**Branch:** `feat/privacy-identity-gruppo-e` (already created from main).

**Testing note:** The repo has no test suite (per `CLAUDE.md`: *"No test suite or linter is configured"*). For each task verification = (1) `cd webapp && npx tsc --noEmit` for frontend typecheck, (2) manual verification on the running dev server (user has `uvicorn --host 127.0.0.1 --port 8000 --reload` + `cd webapp && npm run dev` in Windows shells), (3) commit. Per CLAUDE.md rule, do NOT run `uv sync`/`uv run`/`uv venv` from WSL — backend verifications must be performed by asking the user to hit the endpoint in their browser / test runner.

**Commit convention:** conventional commits, italian summaries aligned with recent history (see `git log`).

---

## Mappa dei file

### Nuovi
- `webapp/src/pages/session/ParticipantIdentitySheet.tsx` — bottom-sheet readonly component con fetch + render public/private sections (~150 LOC).

### Modificati
- `api/schemas/session.py` — aggiungere `IdentityView` Pydantic schema.
- `api/routers/sessions.py` — aggiungere `GET /{code}/participants/{user_id}/identity` endpoint.
- `webapp/src/types/index.ts` — aggiungere `ParticipantIdentity` interface.
- `webapp/src/api/client.ts` — aggiungere method `api.sessions.getParticipantIdentity(code, userId)`.
- `webapp/src/pages/Settings.tsx` — aggiungere sub-section Privacy con toggle `show_private_identity`.
- `webapp/src/pages/Identity.tsx` — spostare `background` nel blocco Personalità, aggiungere badge "Private" visivo.
- `webapp/src/pages/SessionRoom.tsx` — rendere row cliccabile per player non-GM, stato `identityTarget`, montare `ParticipantIdentitySheet`.
- `webapp/src/locales/it.json` + `webapp/src/locales/en.json` — nuove chiavi i18n.
- `docs/superpowers/roadmap.md` — marcare Gruppo E done alla fine.

### Invariati
- `core/db/models.py` (Character) — nessuna migration, flag in JSON `settings`.
- `core/utils/session_view.py`, `CharacterLiveSnapshot` — snapshot live non tocca identity.

---

## Task 1: i18n keys

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

Add keys under `character.settings.privacy.*`, `character.identity.private_badge`, and `session.identity.*`. Keys will be consumed by Tasks 4-7.

- [ ] **Step 1: Locate insertion points**

```bash
grep -n '"settings"\|"privacy"\|"identity"\|"session"' webapp/src/locales/it.json | head -20
```

Note line where `character.settings` subtree ends (new `privacy` subkey goes inside), where `character.identity` subtree lives (adds `private_badge`), and where `session` subtree lives (new `identity` subkey).

- [ ] **Step 2: Add keys to `webapp/src/locales/it.json`**

Inside `character.settings` (next to existing `hp`, `spell_slots_mode`, etc.), add:

```json
"privacy": {
  "title": "Privacy",
  "show_private_label": "Mostra info private a GM e altri player",
  "show_private_hint": "Se attivo, personalità, ideali, legami, difetti e background saranno visibili durante la sessione di gioco."
}
```

Inside `character.identity` (next to existing keys), add a key:

```json
"private_badge": "Info private"
```

Inside `session` (at top-level, next to `players`, `chat`, etc.), add:

```json
"identity": {
  "title": "Identità",
  "fisicita": "Fisicità",
  "cultura": "Cultura",
  "personalita": "Personalità",
  "private_hidden": "Info private nascoste",
  "no_data": "Nessuna informazione disponibile",
  "loading": "Caricamento…",
  "error": "Errore nel caricamento"
}
```

- [ ] **Step 3: Mirror in `webapp/src/locales/en.json`**

Add under `character.settings`:
```json
"privacy": {
  "title": "Privacy",
  "show_private_label": "Show private info to GM and other players",
  "show_private_hint": "If enabled, personality traits, ideals, bonds, flaws and background become visible during game sessions."
}
```

Under `character.identity`:
```json
"private_badge": "Private info"
```

Under `session`:
```json
"identity": {
  "title": "Identity",
  "fisicita": "Physicality",
  "cultura": "Culture",
  "personalita": "Personality",
  "private_hidden": "Private info hidden",
  "no_data": "No information available",
  "loading": "Loading…",
  "error": "Loading failed"
}
```

- [ ] **Step 4: Validate JSON**

```bash
cd webapp
node -e "require('./src/locales/it.json'); require('./src/locales/en.json'); console.log('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "$(cat <<'EOF'
feat(webapp): i18n keys for privacy identity (Gruppo E)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Backend — `IdentityView` schema + endpoint

**Files:**
- Modify: `api/schemas/session.py`
- Modify: `api/routers/sessions.py`

### Step 1: Add `IdentityView` schema

Append to `api/schemas/session.py` (after existing `GameSessionLiveRead`):

```python
class IdentityView(BaseModel):
    """Public + optionally private identity fields for a session participant.

    Private fields (background, personality_traits, ideals, bonds, flaws)
    are populated only when the target has enabled `show_private_identity`
    or when the caller is the target themselves.
    """

    user_id: int
    character_id: int
    # public (always populated)
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    alignment: Optional[str] = None
    speed: Optional[int] = None
    languages: Optional[str] = None  # comma-joined for display
    general_proficiencies: Optional[str] = None  # comma-joined for display
    # private (null if target has show_private_identity = False)
    background: Optional[str] = None
    personality_traits: Optional[str] = None
    ideals: Optional[str] = None
    bonds: Optional[str] = None
    flaws: Optional[str] = None
    show_private: bool = False
```

- [ ] **Step 2: Verify existing helpers in `api/routers/sessions.py`**

The router already exposes:
- `_load_session_by_code(code, db) -> GameSession` (loads with participants).
- `_assert_participant(session, user_id) -> SessionParticipant` (raises 403 if not a participant).

You'll use both. Also import the `Character` model + `selectinload` if not yet in scope (they're already imported for `_load_live_characters`).

- [ ] **Step 3: Add endpoint**

Add import at top of `api/routers/sessions.py` if missing:

```python
from api.schemas.session import (
    # ...existing imports...
    IdentityView,
)
```

Add the endpoint AFTER `post_message` (near the end of the file, before any catch-all). Paste:

```python
@router.get(
    "/{code}/participants/{user_id}/identity",
    response_model=IdentityView,
)
async def get_participant_identity(
    code: str,
    user_id: int,
    caller_user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IdentityView:
    session = await _load_session_by_code(code, db)
    _assert_participant(session, caller_user_id)  # caller must be a participant

    target = next((p for p in session.participants if p.user_id == user_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    if target.character_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant has no character",
        )

    result = await db.execute(
        select(Character).where(Character.id == target.character_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )

    settings_ = char.settings or {}
    show_private = bool(settings_.get("show_private_identity")) or caller_user_id == user_id

    # Join list fields for display — frontend shows these read-only.
    def _join_list(val) -> Optional[str]:
        if not val:
            return None
        if isinstance(val, list):
            cleaned = [str(x).strip() for x in val if str(x).strip()]
            return ", ".join(cleaned) if cleaned else None
        return str(val) or None

    personality = char.personality or {}

    return IdentityView(
        user_id=target.user_id,
        character_id=char.id,
        name=char.name,
        race=char.race,
        gender=char.gender,
        alignment=char.alignment,
        speed=char.speed,
        languages=_join_list(char.languages),
        general_proficiencies=_join_list(char.general_proficiencies),
        background=char.background if show_private else None,
        personality_traits=(personality.get("traits") or None) if show_private else None,
        ideals=(personality.get("ideals") or None) if show_private else None,
        bonds=(personality.get("bonds") or None) if show_private else None,
        flaws=(personality.get("flaws") or None) if show_private else None,
        show_private=show_private,
    )
```

Note: the existing `_assert_participant` raises `HTTPException(403, ...)` if caller is not a participant; this is the correct authorization gate for this endpoint.

If `Annotated`, `Depends`, `AsyncSession`, `get_current_user`, `get_db`, `Character`, `select`, `status`, `HTTPException` aren't already imported at top of `sessions.py`, add missing ones. They should be — all existing endpoints use them.

- [ ] **Step 4: Quick import check**

```bash
grep -n "^from\|^import" api/routers/sessions.py | head -30
```

Confirm `Character` is imported (from `core.db.models`) and `select` from `sqlalchemy`. If not — add.

- [ ] **Step 5: Ask user to verify backend**

Ask the user to:
1. Let `uvicorn` reload (should be automatic with `--reload`).
2. Open DevTools → Network, trigger any session route in the webapp, and manually call (via browser console):
   ```js
   fetch('http://localhost:8000/sessions/<CODE>/participants/<USER_ID>/identity', {
     headers: { 'X-Telegram-Init-Data': '<valid init data or DEV mode>' }
   }).then(r => r.json()).then(console.log)
   ```
   Verify response shape matches `IdentityView` (user_id, character_id, name, race, gender, ..., show_private).
3. Toggle the target's `settings.show_private_identity` in a DB tool (or later via Settings UI after Task 4) and confirm private fields flip between populated and null, while `show_private` flag reflects that.

- [ ] **Step 6: Commit**

```bash
git add api/schemas/session.py api/routers/sessions.py
git commit -m "$(cat <<'EOF'
feat(api): IdentityView schema + participants identity endpoint

GET /sessions/{code}/participants/{user_id}/identity returns public
fields always; private fields (background, personality.*) populated
only if target's settings.show_private_identity is true or caller
is the target.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Frontend TS type + API client method

**Files:**
- Modify: `webapp/src/types/index.ts`
- Modify: `webapp/src/api/client.ts`

### Step 1: Add TS interface

In `webapp/src/types/index.ts`, append at the end (or near other session-related types):

```ts
export interface ParticipantIdentity {
  user_id: number
  character_id: number
  name: string
  race: string | null
  gender: string | null
  alignment: string | null
  speed: number | null
  languages: string | null
  general_proficiencies: string | null
  background: string | null
  personality_traits: string | null
  ideals: string | null
  bonds: string | null
  flaws: string | null
  show_private: boolean
}
```

### Step 2: Add API client method

In `webapp/src/api/client.ts`, locate the `sessions:` object (grep for `sessions:`). Add a new method inside it:

```ts
getParticipantIdentity: (code: string, userId: number) =>
  request<ParticipantIdentity>(
    `/sessions/${encodeURIComponent(code)}/participants/${userId}/identity`
  ),
```

Also add the import in the top import block of `client.ts`:
```ts
import type {
  // ...existing...
  ParticipantIdentity,
} from '@/types'
```

### Step 3: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 4: Commit

```bash
git add webapp/src/types/index.ts webapp/src/api/client.ts
git commit -m "$(cat <<'EOF'
feat(webapp): ParticipantIdentity type + API client method

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `Settings.tsx` — Privacy sub-section

**Files:**
- Modify: `webapp/src/pages/Settings.tsx`

### Step 1: Add Eye icon import

At top of `webapp/src/pages/Settings.tsx`, update the `lucide-react` import to include `Eye`:

```tsx
import { Settings2, Languages, Sparkles, Gem, Dices, RefreshCw, Eye } from 'lucide-react'
```

### Step 2: Insert Privacy section

After the existing HP auto-calc section (around the bottom, before the closing `</Layout>`), add:

```tsx
<SectionDivider icon={<Eye size={11} />} align="center">
  {t('character.settings.privacy.title')}
</SectionDivider>

<Surface variant="elevated">
  <label className="flex items-center justify-between gap-3 cursor-pointer py-1">
    <div className="min-w-0">
      <p className="text-sm font-cinzel text-dnd-gold-bright">
        {t('character.settings.privacy.show_private_label')}
      </p>
      <p className="text-xs text-dnd-text-muted italic mt-1">
        {t('character.settings.privacy.show_private_hint')}
      </p>
    </div>
    <input
      type="checkbox"
      checked={(settings.show_private_identity as boolean | undefined) === true}
      onChange={(e) =>
        updateMutation.mutate({
          ...settings,
          show_private_identity: e.target.checked,
        })
      }
      className="w-5 h-5 shrink-0"
      aria-label={t('character.settings.privacy.show_private_label')}
    />
  </label>
</Surface>
```

If there's an existing pattern for the `hp_auto_calc` toggle in the same file, match its exact style (class names, `Surface variant`, haptic feedback if any) — the snippet above mirrors the expected pattern but adapt to match the current `hp_auto_calc` block's style for visual consistency.

### Step 3: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 4: Ask user to verify

1. Open `#/char/1/settings` → new "Privacy" section visible with Eye icon.
2. Toggle switches `settings.show_private_identity` to true/false (verify via DevTools Network → `PATCH /characters/1` body should include `show_private_identity: true/false`).
3. Refresh page → toggle state persists.

### Step 5: Commit

```bash
git add webapp/src/pages/Settings.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): Privacy sub-section in Settings with show_private_identity toggle

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `Identity.tsx` — reorganize into Public / Private blocks

**Files:**
- Modify: `webapp/src/pages/Identity.tsx`

### Step 1: Add Lock icon import

In the `lucide-react` import, add `Lock`:

```tsx
import { User, Feather, Globe2, Lock } from 'lucide-react'
```

(Adjust existing import accordingly — keep only what's used.)

### Step 2: Remove `background` from Physicality block

Find the Physicality block (grid with race, gender, background, alignment). Delete the `background` `<Surface>`:

```tsx
{/* BEFORE */}
<div className="grid grid-cols-2 gap-2 md:grid-cols-4">
  <Surface variant="elevated" className="!p-3">
    <Input label={t('character.identity.race')} ... />
  </Surface>
  <Surface variant="elevated" className="!p-3">
    <Input label={t('character.identity.gender')} ... />
  </Surface>
  <Surface variant="elevated" className="!p-3">  {/* ← DELETE this whole Surface */}
    <Input label={t('character.identity.background')} ... />
  </Surface>
  <Surface variant="elevated" className="!p-3">
    <Input label={t('character.identity.alignment')} ... />
  </Surface>
</div>
```

Change the grid from `md:grid-cols-4` to `md:grid-cols-3` so the remaining 3 items flow nicely:

```tsx
<div className="grid grid-cols-2 gap-2 md:grid-cols-3">
  <Surface variant="elevated" className="!p-3">
    <Input label={t('character.identity.race')} value={draft.race} onChange={set('race')} placeholder={t('character.identity.placeholder_race')} />
  </Surface>
  <Surface variant="elevated" className="!p-3">
    <Input label={t('character.identity.gender')} value={draft.gender} onChange={set('gender')} placeholder={t('character.identity.placeholder_gender')} />
  </Surface>
  <Surface variant="elevated" className="!p-3">
    <Input label={t('character.identity.alignment')} value={draft.alignment} onChange={set('alignment')} placeholder={t('character.identity.placeholder_alignment')} />
  </Surface>
</div>
```

### Step 3: Add badge and background to Personality block

Find the Personality section. BEFORE the `<SectionDivider>`, keep the existing divider but add a small inline badge right AFTER the section divider:

```tsx
<SectionDivider icon={<Feather size={11} />} align="center">
  {t('character.identity.personality', { defaultValue: 'Personalità' })}
</SectionDivider>
<div className="flex items-center justify-center gap-1 -mt-2 mb-3 text-dnd-gold-dim">
  <Lock size={10} />
  <span className="text-[10px] font-cinzel uppercase tracking-wider">
    {t('character.identity.private_badge')}
  </span>
</div>
```

INSERT `background` as a new Surface BEFORE the personality grid:

```tsx
<Surface variant="parchment" className="!pt-5 !px-4 !pb-4 relative mb-3">
  <span className="absolute -top-2.5 left-4 px-2 bg-dnd-surface-raised text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim rounded">
    {t('character.identity.background')}
  </span>
  <Input
    value={draft.background}
    onChange={set('background')}
    placeholder={t('character.identity.placeholder_background')}
    className="[&_input]:!border-transparent [&_input]:!bg-transparent"
  />
</Surface>
```

Then keep the existing personality grid (`personalitySections.map(...)`) as-is — 4 Surface items for traits/ideals/bonds/flaws.

### Step 4: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 5: Ask user to verify

1. `#/char/1/identity` loads → Fisicità block has race/gender/alignment (no background).
2. Speed stays in its own block below.
3. Personalità block now shows a "Lock Info private" badge below the divider.
4. Background field appears as the FIRST item in the Personalità block (above traits).
5. Save changes → backend `PATCH /characters/1` body still contains `background` and `personality.traits/...`. Nothing lost.

### Step 6: Commit

```bash
git add webapp/src/pages/Identity.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): Identity page — reorganize into Public/Private sections

Background moved from Fisicità to Personalità (private). Lock+badge
indicates Personalità as private. No schema change — only visual reclass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `ParticipantIdentitySheet` component

**Files:**
- Create: `webapp/src/pages/session/ParticipantIdentitySheet.tsx`

### Step 1: Ensure directory exists

```bash
ls webapp/src/pages/session/ 2>/dev/null || mkdir -p webapp/src/pages/session
```

### Step 2: Write the component

Create `webapp/src/pages/session/ParticipantIdentitySheet.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { EyeOff, Lock, User, Globe2, Feather } from 'lucide-react'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import SectionDivider from '@/components/ui/SectionDivider'
import Surface from '@/components/ui/Surface'
import type { ParticipantIdentity, SessionParticipant } from '@/types'

interface Props {
  code: string
  target: SessionParticipant | null
  onClose: () => void
}

interface FieldRowProps {
  label: string
  value: string | number | null
}

function FieldRow({ label, value }: FieldRowProps) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim shrink-0">
        {label}
      </span>
      <span className="text-sm text-dnd-text text-right">{value}</span>
    </div>
  )
}

function BlockRow({ label, value }: FieldRowProps) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="py-2">
      <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
        {label}
      </p>
      <p className="text-sm text-dnd-text italic whitespace-pre-wrap">{value}</p>
    </div>
  )
}

export default function ParticipantIdentitySheet({ code, target, onClose }: Props) {
  const { t } = useTranslation()

  const { data, isLoading, isError } = useQuery<ParticipantIdentity>({
    queryKey: ['session-identity', code, target?.user_id],
    queryFn: () => api.sessions.getParticipantIdentity(code, target!.user_id),
    enabled: !!target,
    staleTime: 30_000,
  })

  return (
    <Sheet
      open={!!target}
      onClose={onClose}
      title={data?.name ?? t('session.identity.title')}
    >
      <div className="space-y-3 p-1">
        {isLoading && (
          <p className="text-center text-sm text-dnd-text-muted py-8">
            {t('session.identity.loading')}
          </p>
        )}

        {isError && (
          <p className="text-center text-sm text-[var(--dnd-crimson-bright)] py-8">
            {t('session.identity.error')}
          </p>
        )}

        {data && (
          <>
            {/* Public — Fisicità */}
            <SectionDivider icon={<User size={11} />} align="center">
              {t('session.identity.fisicita')}
            </SectionDivider>
            <Surface variant="elevated">
              <FieldRow label={t('character.identity.race')} value={data.race} />
              <FieldRow label={t('character.identity.gender')} value={data.gender} />
              <FieldRow label={t('character.identity.alignment')} value={data.alignment} />
              <FieldRow label={t('character.identity.speed')} value={data.speed !== null ? `${data.speed} ft` : null} />
            </Surface>

            {/* Public — Cultura */}
            <SectionDivider icon={<Globe2 size={11} />} align="center">
              {t('session.identity.cultura')}
            </SectionDivider>
            <Surface variant="elevated">
              <FieldRow label={t('character.identity.languages')} value={data.languages} />
              <FieldRow label={t('character.identity.proficiencies')} value={data.general_proficiencies} />
            </Surface>

            {/* Private — Personalità */}
            <SectionDivider icon={<Feather size={11} />} align="center">
              {t('session.identity.personalita')}
            </SectionDivider>
            <div className="flex items-center justify-center gap-1 -mt-2 mb-2 text-dnd-gold-dim">
              <Lock size={10} />
              <span className="text-[10px] font-cinzel uppercase tracking-wider">
                {t('character.identity.private_badge')}
              </span>
            </div>

            {data.show_private ? (
              <Surface variant="parchment">
                <BlockRow label={t('character.identity.background')} value={data.background} />
                <BlockRow label={t('character.identity.personality')} value={data.personality_traits} />
                <BlockRow label={t('character.identity.ideals')} value={data.ideals} />
                <BlockRow label={t('character.identity.bonds')} value={data.bonds} />
                <BlockRow label={t('character.identity.flaws')} value={data.flaws} />
              </Surface>
            ) : (
              <Surface variant="elevated" className="text-center !py-6">
                <EyeOff size={24} className="mx-auto text-dnd-text-muted mb-2" />
                <p className="text-sm text-dnd-text-muted italic">
                  {t('session.identity.private_hidden')}
                </p>
              </Surface>
            )}
          </>
        )}
      </div>
    </Sheet>
  )
}
```

Imports assume `Surface` lives at `@/components/ui/Surface` — verify:

```bash
ls webapp/src/components/ui/Surface.tsx
```

If the path differs, adjust.

### Step 3: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 4: Commit

```bash
git add webapp/src/pages/session/ParticipantIdentitySheet.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): ParticipantIdentitySheet — readonly view of a participant's identity

Fetches GET /sessions/{code}/participants/{user_id}/identity and
renders public (Fisicità, Cultura) + private (Personalità) sections,
with a fallback message when target hasn't shared private info.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `SessionRoom.tsx` — wire click + mount sheet

**Files:**
- Modify: `webapp/src/pages/SessionRoom.tsx`

### Step 1: Add imports

At top of `webapp/src/pages/SessionRoom.tsx`:

```tsx
import ParticipantIdentitySheet from '@/pages/session/ParticipantIdentitySheet'
```

Keep existing imports.

### Step 2: Change `ParticipantRow` interaction model

Find the `ParticipantRow` function. Currently it takes `onOwnClick: (charId: number) => void` and only renders as `<button>` when `isOwn`. Change to a more generalized click handler:

Replace the existing props interface:

```tsx
function ParticipantRow({
  participant,
  snapshot,
  isGm,
  isMe,
  isOwn,
  onOwnClick,
  onOtherClick,
  t,
}: {
  participant: SessionParticipant
  snapshot?: CharacterLiveSnapshot
  isGm: boolean
  isMe: boolean
  isOwn: boolean
  onOwnClick: (charId: number) => void
  onOtherClick: (participant: SessionParticipant) => void
  t: TFunction
}) {
```

Update `handleClick`:

```tsx
const handleClick = () => {
  if (isOwn && snapshot) {
    onOwnClick(snapshot.id)
  } else if (!isGm && !isMe && participant.character_id) {
    onOtherClick(participant)
  }
}
```

Update the wrapper decision — the row becomes interactive if `isOwn` OR (non-GM && non-me && has character):

```tsx
const isClickable = isOwn || (!isGm && !isMe && !!participant.character_id)
const Wrapper: any = isClickable ? 'button' : 'div'
const wrapperProps = isClickable
  ? { type: 'button', onClick: handleClick, className: 'w-full text-left cursor-pointer' }
  : {}
```

The hover class `hover:border-dnd-gold-bright` is already conditionally applied on `isOwn` — extend it to `isClickable`:

Find:
```tsx
${isOwn ? 'hover:border-dnd-gold-bright' : ''}
```

Replace with:
```tsx
${isClickable ? 'hover:border-dnd-gold-bright' : ''}
```

### Step 3: Add state and wire sheet in the parent component

Inside the main `SessionRoom` component body (where `participants` and `live` already exist), add:

```tsx
const [identityTarget, setIdentityTarget] = useState<SessionParticipant | null>(null)
```

(Note: `useState` is already imported from `react` if not, add it.)

Find the `live.participants.map((p) => ...` block and update the `ParticipantRow` render to pass `onOtherClick`:

```tsx
<ParticipantRow
  key={`${p.user_id}-${p.joined_at}`}
  participant={p}
  snapshot={snap}
  isGm={p.role === 'game_master'}
  isMe={isMe}
  isOwn={isOwn}
  onOwnClick={(cid) => navigate(`/char/${cid}`)}
  onOtherClick={(target) => setIdentityTarget(target)}
  t={t}
/>
```

Mount the sheet near the end of the component's JSX (next to other sheets/modals — look for where `confirmLeave` or similar modals are rendered):

```tsx
<ParticipantIdentitySheet
  code={live.code}
  target={identityTarget}
  onClose={() => setIdentityTarget(null)}
/>
```

If the `live.code` access path is different (e.g., `live.session.code`), adapt — but based on `GameSessionLiveRead` schema `live.code` is correct.

### Step 4: Typecheck

```bash
cd webapp
npx tsc --noEmit
```

Expected: 0 errors.

### Step 5: Ask user to verify

With 2+ participants in a session:
1. `#/session/<id>` → see participant list.
2. Click own row → navigate to `/char/<id>` (unchanged behavior).
3. Click GM row → no-op (not clickable; cursor not pointer).
4. Click other player row → bottom sheet opens with their identity.
5. Case A: target has `show_private_identity = false` → sheet shows public sections + "Info private nascoste" in Personalità.
6. Case B: toggle target's setting ON in Settings, re-open sheet → Personalità shows background + traits + ideals + bonds + flaws (only non-empty ones).
7. Drag-down or tap outside → closes sheet.
8. No regression on HP/AC/conditions privacy redaction in the row itself.

### Step 6: Commit

```bash
git add webapp/src/pages/SessionRoom.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): SessionRoom — click participant to view identity

Non-GM, non-self participant rows are now clickable. Opens
ParticipantIdentitySheet which fetches and renders the target's
identity respecting their show_private_identity setting.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Build prod + roadmap + commit

**Files:**
- Modify: `docs/superpowers/roadmap.md`
- Build: `docs/app/*` (via `npm run build:prod`)

### Step 1: Build prod

```bash
cd webapp
npm run build:prod
```

The script will:
1. Switch `.env.local` to prod URL (`https://api.cischi.dev`).
2. Run `tsc && vite build`.
3. Restore `.env.local` to dev.
4. `git add docs/app/`.

If it fails on TS: fix and re-run. Do NOT skip.

### Step 2: Update `docs/superpowers/roadmap.md`

Three edits:

**a) Line 5 (Stato globale):** change
```
**Stato globale:** Gruppi A, B, C, D, F, G completati e mergeati; E, H pending.
```
to
```
**Stato globale:** Gruppi A, B, C, D, E, F, G completati e mergeati; H pending.
```

**b) Table row for Gruppo E (around line 19):** change
```
| E | Privacy identità | §1.7 + §4 | 🟡 Parziale (base già fatto pre-roadmap) | — |
```
to
```
| E | Privacy identità | §1.7 + §4 | ✅ Done (PR #XX merged → main) | `feat/privacy-identity-gruppo-e` |
```

(`#XX` is a placeholder; the user will update it after merge.)

**c) "Ordine consigliato" block (around line 284):** change
```
✅ A → ✅ B → ✅ F → ✅ G → ✅ C → ✅ D → E completion → H
```
to
```
✅ A → ✅ B → ✅ F → ✅ G → ✅ C → ✅ D → ✅ E → H
```

### Step 3: Commit

```bash
git add docs/app/ docs/superpowers/roadmap.md
git commit -m "$(cat <<'EOF'
docs(roadmap): mark Gruppo E as done + prod build

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Step 4: End-to-end manual check (ask user)

- [ ] Owner view `/char/1/identity` → Fisicità has race/gender/alignment (no background). Personalità block shows Lock badge and has background + traits/ideals/bonds/flaws.
- [ ] `/char/1/settings` → Privacy section with toggle. Default OFF.
- [ ] In a session with 2+ players, target's setting OFF:
  - Clicking target → sheet shows public info + "Info private nascoste".
- [ ] Same target, setting ON:
  - Clicking target → sheet shows all fields populated (that were non-empty).
- [ ] Own row → navigate to `/char/:id` (unchanged).
- [ ] GM row → no interaction.
- [ ] `caller == target` edge case: if you click your OWN row while `show_private_identity = false`, you still see your own data via `/char/:id` nav (not the sheet). Sheet itself is not triggered for self.

### Step 5: Do NOT push or open PR

The user handles push + PR manually.

### Step 6: Verify final state

```bash
git log --oneline main..HEAD | head -15
git status
cat webapp/.env.local
```

Confirm: head is the docs+build commit; working tree clean (only gitignored files); `.env.local` = dev URL.

---

## Self-review

**Spec coverage:**
- §1.7 split private/public + setting → Tasks 1, 4, 5 (i18n, Privacy toggle, Identity reorg).
- §1.7 background moved to private → Task 5.
- §4 click altro player for identity → Tasks 6, 7 (sheet + wire).
- Endpoint + privacy respect → Task 2.
- Owner sees always tutto (scelta 5A) → Task 5 (no toggle in-page).
- GM excluded → Task 7 (`!isGm` in click gate).
- Default `false` → Task 2 (`bool(settings_.get(...))` returns False when key missing or None).

**Placeholder scan:** no TBD/TODO. PR `#XX` is intentional per convention.

**Type consistency:**
- `ParticipantIdentity` (TS) field names match `IdentityView` (Python) — verified.
- `show_private` flag present on both — verified.
- `api.sessions.getParticipantIdentity(code, userId)` signature matches Task 6 usage.
- `SessionParticipant` type already exists (imported in SessionRoom today).

**Edge cases:**
- Backend 404s covered (session not found, participant not found, no character, character not found).
- Frontend sheet `enabled: !!target` ensures no fetch when sheet closed.
- `data.show_private` gates the private render; fallback message otherwise.
- Sheet has `staleTime: 30_000` — refetch on reopen after 30s (reasonable for identity which rarely changes).

**Nothing missing.** Plan covers all spec items.
