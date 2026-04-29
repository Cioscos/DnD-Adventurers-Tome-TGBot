# Session Grants & UI Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quattro fix bundlate in un solo PR: portal dei modali equipaggiamento (PaperDoll) per evitare clipping dentro `CharacterSwiper` (transformed track), spaziatura corretta tra ultimo messaggio e input nella chat di sessione, popup "ricompensa" su grant del GM con queue persistente, e click sul messaggio di grant che porta all'inventario evidenziando l'oggetto con pulse glow.

**Architecture:** Backend aggiunge tre colonne nullable a `session_messages` (`item_id`, `item_name`, `item_quantity`) popolate da `gm_grant_item` e restituite dal feed. Frontend riconosce il messaggio di grant via `item_id != null && recipient_user_id === myUserId`, lo accoda in `sessionStorage['reward-queue']` e mostra `RewardPopup` su entrata in `SessionRoom`. Click sul messaggio (o CTA del popup) naviga `/char/:charId/inventory` con `location.state.highlightItemId`; `Inventory` espande, scrolla e applica per 3 s un'animazione `pulse-glow`. I modali `SlotActionSheet` e `EquipItemPicker` vengono wrap'd in `createPortal(document.body)` come già fatto per `ProgressionFullTableModal`.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, framer-motion, react-router-dom (HashRouter), TanStack Query, Zustand, sonner (toast), FastAPI, SQLAlchemy async, SQLite.

**Branch:** prosegui sul branch corrente `feat/character-menu-3-screens` (oppure crea `feat/session-grants-ui-fixes` se preferito).

**Note sul testing:** il repo non ha una suite di test (CLAUDE.md: *"No test suite or linter is configured"*). Il ciclo di verifica per ogni task è: (1) `cd webapp && npx tsc --noEmit` per il typecheck del frontend; (2) avvio del dev server (Windows shell — vedi CLAUDE.md, **MAI** `uv sync` da WSL): `uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload` in una shell, `cd webapp && npm run dev` nell'altra, e verifica manuale; (3) commit. I passi di verifica manuale sono espliciti in ogni task.

**Convenzione commit:** conventional commits, scope `webapp` o `api` a seconda del cambio. Co-author footer come negli altri commit recenti.

---

## Mappa dei file

### Nuovi
- `webapp/src/lib/rewardQueue.ts` — utility FIFO su `sessionStorage`. ~50 LOC.
- `webapp/src/components/session/RewardPopup.tsx` — modale "Hai ricevuto un oggetto". ~110 LOC.

### Modificati (backend)
- `core/db/models.py` — `SessionMessage`: tre nuovi campi.
- `core/db/engine.py` — `_MIGRATIONS`: tre nuove entry.
- `api/schemas/session.py` — `SessionFeedItem`: tre nuovi campi opzionali.
- `api/routers/sessions.py` — `gm_grant_item`: popola i campi nel whisper; `get_session_feed`: include i campi nel mapping `SessionMessage` → `SessionFeedItem`.

### Modificati (frontend)
- `webapp/src/types/index.ts` — `SessionFeedItem`: tre nuovi campi opzionali.
- `webapp/src/components/character/SlotActionSheet.tsx` — wrap return in `createPortal(..., document.body)`.
- `webapp/src/components/character/EquipItemPicker.tsx` — idem.
- `webapp/src/index.css` — keyframe `pulse-glow` + utility class.
- `webapp/src/pages/SessionRoom.tsx` — passa `myCharId` a `SessionFeed`; integra `RewardPopup` con queue.
- `webapp/src/pages/session/SessionFeed.tsx` — `mt-4` su input, enqueue grant per recipient su nuovi messaggi, click handler con lookup item.
- `webapp/src/pages/Inventory.tsx` — legge `location.state.highlightItemId`, gestisce highlight via ref map e fade timer.
- `webapp/src/locales/it.json`, `webapp/src/locales/en.json` — nuove chiavi `session.reward.*` e `session.feed.grant_chip`.

---

## Task 1: Backend — colonne `item_id` / `item_name` / `item_quantity` su `session_messages`

Aggiunge i tre campi al modello SQLAlchemy e alla migration idempotente. Nessun cambiamento di comportamento ancora — solo schema.

**Files:**
- Modify: `core/db/models.py:578-599`
- Modify: `core/db/engine.py:40-99`

- [ ] **Step 1: Aggiungi i campi al modello `SessionMessage`**

In `core/db/models.py`, dopo `sender_display_name` (riga 596), inserisci:

```python
    item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=False
    )
    item_name: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True
    )
    item_quantity: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
```

- [ ] **Step 2: Aggiungi le tre entry alla lista `_MIGRATIONS`**

In `core/db/engine.py`, in fondo alla lista `_MIGRATIONS` (subito prima della parentesi `]` a riga 99), aggiungi:

```python
    # GM grant payload on session whispers
    ("session_messages", "item_id", "BIGINT", None),
    ("session_messages", "item_name", "VARCHAR(120)", None),
    ("session_messages", "item_quantity", "INTEGER", None),
```

- [ ] **Step 3: Verifica typecheck/import (Windows)**

Da PowerShell (CLAUDE.md vieta `uv sync` da WSL):

```powershell
uv run python -c "from core.db.models import SessionMessage; print(SessionMessage.__table__.columns.keys())"
```

Output atteso: la lista deve includere `item_id`, `item_name`, `item_quantity`.

- [ ] **Step 4: Verifica idempotenza migration**

Da PowerShell, avvia l'API una prima volta (crea/aggiorna lo schema) e poi una seconda volta:

```powershell
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Stoppa con Ctrl+C e riavvia. Nessun errore "duplicate column" su `session_messages`.

- [ ] **Step 5: Commit**

```bash
git add core/db/models.py core/db/engine.py
git commit -m "$(cat <<'EOF'
feat(api): add item payload columns to session_messages

Adds nullable item_id/item_name/item_quantity to SessionMessage so the
GM grant whisper can carry the structured grant payload back to the
recipient via the session feed. Migration is idempotent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Backend — popola i campi in `gm_grant_item` ed esponi nel feed

Riempie i tre campi nuovi sul `SessionMessage` creato dall'endpoint, e li include nel mapping del feed.

**Files:**
- Modify: `api/schemas/session.py:120-142`
- Modify: `api/routers/sessions.py:706-723` (whisper construction)
- Modify: `api/routers/sessions.py:809-818` (feed mapping)

- [ ] **Step 1: Estendi lo schema `SessionFeedItem`**

In `api/schemas/session.py`, dentro la classe `SessionFeedItem` (riga 120-141), in fondo alla sezione message-only (dopo `recipient_user_id: Optional[int] = None`), aggiungi:

```python
    # message-only — GM grant payload
    item_id: Optional[int] = None
    item_name: Optional[str] = None
    item_quantity: Optional[int] = None
```

- [ ] **Step 2: Popola i campi nel whisper di `gm_grant_item`**

In `api/routers/sessions.py`, sostituisci la costruzione di `msg` (righe 707-715) con:

```python
        msg = SessionMessage(
            session_id=session_obj.id,
            user_id=user_id,
            role=SessionRole.GAME_MASTER,
            body=whisper_body,
            sent_at=now_iso,
            recipient_user_id=rid,
            sender_display_name="__GM__",
            item_id=granted_item_id,
            item_name=body.item.name,
            item_quantity=body.item.quantity,
        )
```

- [ ] **Step 3: Includi i campi nel mapping del feed**

In `api/routers/sessions.py`, sostituisci l'`items.append(SessionFeedItem(...))` per il ramo `messages` (righe 809-818) con:

```python
        items.append(SessionFeedItem(
            type="message",
            timestamp=m.sent_at,
            message_id=m.id,
            user_id=m.user_id,
            display_name=m.sender_display_name,
            role=sender_role,
            body=m.body,
            recipient_user_id=m.recipient_user_id,
            item_id=m.item_id,
            item_name=m.item_name,
            item_quantity=m.item_quantity,
        ))
```

- [ ] **Step 4: Verifica manuale via curl/HTTPie (Windows)**

Avvia l'API in una shell PowerShell. In un'altra:

1. Crea due character (uno GM, uno player) usando i tuoi ID di sviluppo, oppure usa i flussi esistenti del Mini App per arrivare ad una sessione attiva con almeno un player.
2. Da GM: `POST /sessions/{id}/gm/grant_item` con body `{"recipient_user_ids": [<playerId>], "item": {"name": "Test", "weight": 1, "quantity": 2, "item_type": "generic", "item_metadata": null, "is_equipped": false}}`.
3. Da player (o GM): `GET /sessions/{code}/feed?limit=20`.

Atteso: nel JSON di risposta, l'item più recente ha `type: "message"`, `recipient_user_id` = playerId, `item_id` non null, `item_name: "Test"`, `item_quantity: 2`. Per i messaggi normali (non grant) i campi `item_*` sono `null`.

- [ ] **Step 5: Commit**

```bash
git add api/schemas/session.py api/routers/sessions.py
git commit -m "$(cat <<'EOF'
feat(api): expose grant item payload on session feed messages

gm_grant_item now stores item_id/item_name/item_quantity on the
recipient's whisper, and get_session_feed propagates them on the feed
response so the Mini App can render a clickable grant message and
trigger the reward popup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Frontend — estendi il tipo `SessionFeedItem`

Allinea il tipo TS al payload backend.

**Files:**
- Modify: `webapp/src/types/index.ts:312-332`

- [ ] **Step 1: Aggiungi i tre campi opzionali**

Sostituisci il blocco `// message` dentro `SessionFeedItem` (righe 316-322) con:

```ts
  // message
  message_id?: number | null
  user_id?: number | null
  display_name?: string | null
  role?: string | null
  body?: string | null
  recipient_user_id?: number | null
  // message — GM grant payload
  item_id?: number | null
  item_name?: string | null
  item_quantity?: number | null
```

- [ ] **Step 2: Typecheck**

```bash
cd webapp && npx tsc --noEmit
```

Atteso: zero errori.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/types/index.ts
git commit -m "$(cat <<'EOF'
feat(webapp): extend SessionFeedItem with grant payload fields

Mirrors the backend extension so the SessionFeed component can detect
GM-grant whispers and route the player to inventory.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Frontend — portal dei modali equipaggiamento

Risolve il bug visivo (`fix #1`): i modal vengono ancorati al body invece che al track del swiper transformato. Pattern identico a `ProgressionFullTableModal.tsx`.

**Files:**
- Modify: `webapp/src/components/character/SlotActionSheet.tsx`
- Modify: `webapp/src/components/character/EquipItemPicker.tsx`

- [ ] **Step 1: SlotActionSheet — import `createPortal`**

In `webapp/src/components/character/SlotActionSheet.tsx`, aggiungi all'inizio (sopra l'import di `framer-motion`):

```ts
import { createPortal } from 'react-dom'
```

- [ ] **Step 2: SlotActionSheet — wrap del return in createPortal**

Sostituisci `return (` (riga 33) con `return createPortal(` e l'ultima parentesi `)` di chiusura (dopo `</AnimatePresence>` a riga 81) con `,\n    document.body,\n  )`. Risultato finale del return:

```tsx
  return createPortal(
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        {/* ...resto invariato... */}
      </m.div>
    </AnimatePresence>,
    document.body,
  )
```

- [ ] **Step 3: EquipItemPicker — import `createPortal`**

In `webapp/src/components/character/EquipItemPicker.tsx`, aggiungi:

```ts
import { createPortal } from 'react-dom'
```

(Nota: esiste già un import da `lucide-react`; aggiungi la nuova riga dopo gli import esistenti.)

- [ ] **Step 4: EquipItemPicker — wrap del return in createPortal**

Stessa trasformazione di Step 2: sostituisci `return (` (riga 41) con `return createPortal(` e chiudi con `,\n    document.body,\n  )` dopo `</AnimatePresence>`.

- [ ] **Step 5: Typecheck**

```bash
cd webapp && npx tsc --noEmit
```

Atteso: zero errori.

- [ ] **Step 6: Verifica manuale**

Avvia il dev stack (API + webapp) e apri `http://localhost:5173`. Vai su un character → swipe alla schermata Equipment (screen 2/3). Tap su uno slot vuoto: il picker deve apparire centrato/full-width sul viewport (nessuna parte fuori dai bordi). Tap su uno slot con un item: il SlotActionSheet deve emergere dal basso ancorato al fondo viewport. Ripeti su screen 1 e 3 (Hero e Menu) — non ci sono modali lì, ma assicurati che il swipe non trascini più il modal con sé.

- [ ] **Step 7: Commit**

```bash
git add webapp/src/components/character/SlotActionSheet.tsx \
        webapp/src/components/character/EquipItemPicker.tsx
git commit -m "$(cat <<'EOF'
fix(webapp): portal equipment modals to body to escape swiper transform

SlotActionSheet and EquipItemPicker were rendered inside the
CharacterSwiper transformed track, so position:fixed used the track as
containing block and the modals ended up clipped or off-screen. Wrap
both with createPortal(document.body), matching the
ProgressionFullTableModal fix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Frontend — spaziatura input chat (`fix #2`)

Aggiunge `mt-4` al wrapper della input row in `SessionFeed`.

**Files:**
- Modify: `webapp/src/pages/session/SessionFeed.tsx:351`

- [ ] **Step 1: Aggiungi `mt-4` al wrapper**

In `webapp/src/pages/session/SessionFeed.tsx`, riga 351, sostituisci:

```tsx
      <div className="flex items-center gap-2">
```

con:

```tsx
      <div className="mt-4 flex items-center gap-2">
```

- [ ] **Step 2: Verifica manuale**

Apri SessionRoom, manda due/tre messaggi. Visivamente l'input box ora ha respiro tra l'ultimo bubble e il bordo superiore della input. Apri/chiudi la modalità whisper: la chip giallo-ambra deve continuare a stare sopra l'input (chip ha già `mt-3 mb-2` proprio).

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/session/SessionFeed.tsx
git commit -m "$(cat <<'EOF'
fix(webapp): add breathing room above session chat input

User feedback: input box was sticking to the last message. Adds mt-4
to the input row so the bubble doesn't crowd the field.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Frontend — utility `rewardQueue.ts`

FIFO persistente su `sessionStorage` con safe try/catch.

**Files:**
- Create: `webapp/src/lib/rewardQueue.ts`

- [ ] **Step 1: Crea il file con l'API completa**

Contenuto integrale di `webapp/src/lib/rewardQueue.ts`:

```ts
const KEY = 'reward-queue'

export interface Reward {
  message_id: number
  item_id: number
  item_name: string
  item_quantity: number
  char_id: number
  granted_at: string // ISO
}

function readQueue(): Reward[] {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Reward[]) : []
  } catch (err) {
    console.warn('[rewardQueue] read failed', err)
    return []
  }
}

function writeQueue(q: Reward[]): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(q))
  } catch (err) {
    console.warn('[rewardQueue] write failed', err)
  }
}

export function enqueue(r: Reward): void {
  const q = readQueue()
  // dedup by message_id (in case the same incremental fetch fires twice)
  if (q.some((x) => x.message_id === r.message_id)) return
  q.push(r)
  writeQueue(q)
}

export function peek(): Reward | null {
  const q = readQueue()
  return q.length > 0 ? q[0] : null
}

export function dequeue(): Reward | null {
  const q = readQueue()
  if (q.length === 0) return null
  const head = q[0]
  writeQueue(q.slice(1))
  return head
}

export function clear(): void {
  writeQueue([])
}

export function pruneOlderThan(maxAgeMs: number): void {
  const q = readQueue()
  const now = Date.now()
  const fresh = q.filter((r) => {
    const t = Date.parse(r.granted_at)
    return Number.isFinite(t) && now - t < maxAgeMs
  })
  if (fresh.length !== q.length) writeQueue(fresh)
}
```

- [ ] **Step 2: Typecheck**

```bash
cd webapp && npx tsc --noEmit
```

Atteso: zero errori.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/lib/rewardQueue.ts
git commit -m "$(cat <<'EOF'
feat(webapp): sessionStorage FIFO queue for GM grant rewards

Used by SessionFeed to enqueue incoming grants and by SessionRoom to
peek/dequeue reward popups in order. Wraps storage ops in try/catch
for private-mode/quota safety; dedups by message_id.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend — animazione `pulse-glow` CSS

Definisce keyframe e utility class usata sia da `RewardPopup` (entry) sia da `Inventory` per evidenziare l'item.

**Files:**
- Modify: `webapp/src/index.css`

- [ ] **Step 1: Individua il file CSS globale**

```bash
ls webapp/src/index.css
```

Se manca, individua `webapp/src/main.css` o `webapp/src/styles/*.css`. Il punto d'aggancio è il file CSS già importato da `webapp/src/main.tsx`. Comando per trovarlo:

```bash
grep -n "import.*\.css" webapp/src/main.tsx
```

- [ ] **Step 2: Aggiungi keyframe e classe in fondo al file**

Aggiungi (in fondo al file CSS già caricato):

```css
@keyframes pulse-glow {
  0%   { box-shadow: 0 0 0 0 rgba(212, 175, 55, 0); }
  20%  { box-shadow: 0 0 12px 4px rgba(212, 175, 55, 0.7); }
  100% { box-shadow: 0 0 0 0 rgba(212, 175, 55, 0); }
}

.animate-pulse-glow {
  animation: pulse-glow 1s ease-out 0s 3;
  border: 1px solid var(--dnd-gold-bright, #d4af37);
  border-radius: 1rem;
}
```

- [ ] **Step 3: Verifica visiva (placeholder)**

Niente verifica isolata in questo task — sarà osservabile in Task 12 (Inventory highlight).

- [ ] **Step 4: Commit**

```bash
git add webapp/src/index.css
git commit -m "$(cat <<'EOF'
feat(webapp): add pulse-glow animation for inventory highlight

Three-cycle gold glow used to mark the item the player just received
from a GM grant when navigating from the chat message or reward popup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Frontend — `RewardPopup` component

Modale centrato portal'd a body. Mostra nome/qty/descrizione (se presente) e due CTA.

**Files:**
- Create: `webapp/src/components/session/RewardPopup.tsx`

- [ ] **Step 1: Crea la directory se mancante**

```bash
ls webapp/src/components/session/ || mkdir -p webapp/src/components/session/
```

- [ ] **Step 2: Crea il file**

Contenuto integrale di `webapp/src/components/session/RewardPopup.tsx`:

```tsx
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Gift } from 'lucide-react'
import Button from '@/components/ui/Button'
import type { Reward } from '@/lib/rewardQueue'

interface Props {
  reward: Reward
  description?: string | null
  onDismiss: () => void
  onGoToInventory: () => void
}

export default function RewardPopup({ reward, description, onDismiss, onGoToInventory }: Props) {
  const { t } = useTranslation()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDismiss()
    }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onDismiss])

  return createPortal(
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onDismiss}
      >
        <m.div
          className="w-full max-w-sm bg-dnd-surface-raised border border-dnd-gold rounded-2xl p-5 space-y-4"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 220, damping: 26 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex flex-col items-center text-center gap-2">
            <Gift size={36} className="text-dnd-gold-bright" />
            <h2 className="text-base font-cinzel uppercase tracking-widest text-dnd-gold-bright">
              {t('session.reward.title', { defaultValue: 'Hai ricevuto un oggetto!' })}
            </h2>
          </div>

          <div className="text-center space-y-1">
            <p className="font-display font-bold text-dnd-gold text-lg break-words">
              {reward.item_name}
            </p>
            {reward.item_quantity > 1 && (
              <p className="text-sm font-mono text-dnd-text-muted">
                ×{reward.item_quantity}
              </p>
            )}
            {description && (
              <p className="text-xs text-dnd-text-muted italic line-clamp-3 pt-1">
                {description}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2 pt-2">
            <Button variant="primary" fullWidth onClick={onGoToInventory}>
              {t('session.reward.cta_inventory', { defaultValue: "Vedi nell'inventario" })}
            </Button>
            <Button variant="secondary" fullWidth onClick={onDismiss}>
              {t('session.reward.cta_dismiss', { defaultValue: 'OK' })}
            </Button>
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>,
    document.body,
  )
}
```

- [ ] **Step 3: Typecheck**

```bash
cd webapp && npx tsc --noEmit
```

Atteso: zero errori.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/components/session/RewardPopup.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): RewardPopup modal for GM-granted items

Centered, body-portal'd modal with Gift icon, item name + qty +
description, and two CTAs (open inventory / dismiss). Locks body
scroll while open and closes on ESC or scrim tap.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Frontend — chiavi i18n

Aggiunge le stringhe IT + EN per popup, CTA, toast e chip.

**Files:**
- Modify: `webapp/src/locales/it.json`
- Modify: `webapp/src/locales/en.json`

- [ ] **Step 1: Individua la sezione `session.*` esistente**

```bash
grep -n '"session"' webapp/src/locales/it.json | head
```

Identifica l'oggetto `session: { ... }`. Aggiungi al suo interno una sotto-chiave `reward` e `feed` (se non esiste già `feed`).

- [ ] **Step 2: Modifica `it.json`**

Dentro l'oggetto `session` (in `webapp/src/locales/it.json`), aggiungi (mantenendo la sintassi JSON valida — ricordati le virgole tra chiavi):

```json
  "reward": {
    "title": "Hai ricevuto un oggetto!",
    "cta_inventory": "Vedi nell'inventario",
    "cta_dismiss": "OK",
    "item_not_found_toast": "Oggetto non più presente nel tuo inventario"
  },
  "feed": {
    "grant_chip": "Tocca per aprire nell'inventario"
  }
```

Se `session.feed.*` esiste già con altre chiavi, fondi `grant_chip` dentro l'oggetto `feed` esistente.

- [ ] **Step 3: Modifica `en.json`**

Stessa cosa in `webapp/src/locales/en.json`:

```json
  "reward": {
    "title": "You received an item!",
    "cta_inventory": "View in inventory",
    "cta_dismiss": "OK",
    "item_not_found_toast": "Item is no longer in your inventory"
  },
  "feed": {
    "grant_chip": "Tap to open in inventory"
  }
```

- [ ] **Step 4: Verifica JSON valido**

```bash
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/it.json','utf8'))" \
  && node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/en.json','utf8'))" \
  && echo OK
```

Atteso: stampa `OK`. Se uno dei due ritorna `SyntaxError`, correggi virgole/parentesi.

- [ ] **Step 5: Commit**

```bash
git add webapp/src/locales/it.json webapp/src/locales/en.json
git commit -m "$(cat <<'EOF'
i18n(webapp): add session reward popup and grant chip strings

IT + EN keys for the new GM-grant flow: reward popup title/CTAs, feed
chip and missing-item toast.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Frontend — `SessionFeed` clickable grant + enqueue

Tre cambiamenti in `SessionFeed.tsx`:
1. Accetta nuova prop `myCharId` (necessaria per `navigate` e per filtrare l'enqueue ai casi reali in cui il caller è un player con char).
2. Su `mergeIncoming` enqueue dei messaggi nuovi che soddisfano `item_id != null && recipient_user_id === myUserId`. **Solo** dai poll incrementali, **non** dal fetch iniziale (altrimenti si re-popperebbe ogni reload).
3. Whisper bubble con `item_id != null` diventa cliccabile: lookup item nella character query, se assente toast, altrimenti `navigate('/char/:charId/inventory', { state: { highlightItemId } })`.

**Files:**
- Modify: `webapp/src/pages/session/SessionFeed.tsx`

- [ ] **Step 1: Aggiorna la `Props` interface**

In `webapp/src/pages/session/SessionFeed.tsx`, sostituisci l'interface `Props` (righe 25-33):

```ts
interface Props {
  code: string
  sessionId: number
  gmUserId: number | null
  myUserId: number
  myCharId: number | null
  participants: SessionParticipant[]
  whisperTarget: SessionParticipant | null
  onClearWhisperTarget: () => void
}
```

E aggiungi `myCharId` ai parametri destrutturati nella firma del componente (riga 46-54):

```tsx
export default function SessionFeed({
  code,
  sessionId,
  gmUserId,
  myUserId,
  myCharId,
  participants,
  whisperTarget,
  onClearWhisperTarget,
}: Props) {
```

- [ ] **Step 2: Import dei nuovi simboli**

In cima al file aggiungi (vicino agli altri import):

```ts
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Gift } from 'lucide-react'
import { enqueue, type Reward } from '@/lib/rewardQueue'
import type { CharacterFull } from '@/types'
```

`useQueryClient` è già importato in alto — verifica e non duplicare. `Lock` e `User as UserIcon` ci sono già.

- [ ] **Step 3: Hook `navigate` e `qc` dentro il componente**

Subito sotto `const qc = useQueryClient()` (già esistente, riga ~56) aggiungi:

```ts
  const navigate = useNavigate()
```

(Se `qc` non c'è ancora — verifica — aggiungilo: `const qc = useQueryClient()`.)

- [ ] **Step 4: Modifica `mergeIncoming` per enqueue dei reward**

Sostituisci la funzione `mergeIncoming` (riga 73-86) con:

```ts
  const mergeIncoming = (incoming: SessionFeedItem[], opts: { skipReward?: boolean } = {}) => {
    if (incoming.length === 0) return
    setItems((prev) => {
      const seen = new Set<string>(prev.map(itemKey))
      const fresh = incoming.filter((it) => !seen.has(itemKey(it)))
      if (fresh.length === 0) return prev

      if (!opts.skipReward && myCharId !== null) {
        for (const it of fresh) {
          if (
            it.type === 'message' &&
            it.message_id != null &&
            it.item_id != null &&
            it.item_name &&
            it.recipient_user_id === myUserId
          ) {
            const r: Reward = {
              message_id: it.message_id,
              item_id: it.item_id,
              item_name: it.item_name,
              item_quantity: it.item_quantity ?? 1,
              char_id: myCharId,
              granted_at: it.timestamp,
            }
            enqueue(r)
          }
        }
      }

      const next = [...prev, ...fresh]
      latestTsRef.current = next[next.length - 1].timestamp
      requestAnimationFrame(() => {
        scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: 'smooth' })
      })
      return next
    })
  }
```

- [ ] **Step 5: Passa `skipReward: true` al fetch iniziale**

In `useEffect(... [code])` (riga 89) trova la funzione `initial()` (riga 92). Sostituiscila con:

```ts
    async function initial() {
      try {
        const res = await api.sessions.getFeed(code, { limit: 100 })
        if (cancelled) return
        setItems(res.items)
        setHasMoreBefore(res.has_more)
        initialisedRef.current = true
        if (res.items.length > 0) {
          latestTsRef.current = res.items[res.items.length - 1].timestamp
        }
        requestAnimationFrame(() => {
          scrollerRef.current?.scrollTo({ top: scrollerRef.current?.scrollHeight ?? 0 })
        })
      } catch {
        /* empty state acceptable */
      }
    }
```

(Nessuna chiamata a `mergeIncoming` qui — il setItems diretto evita l'enqueue dei reward storici. Conferma riga per riga che non viene chiamato `mergeIncoming` in `initial()`.)

- [ ] **Step 6: Aggiungi handler click sul whisper di grant**

Subito sopra il `return` finale (in particolare prima della costante `chatBody = (...)` definita a riga ~238), aggiungi:

```ts
  const handleGrantClick = (it: SessionFeedItem) => {
    if (myCharId === null || it.item_id == null) return
    const cached = qc.getQueryData<CharacterFull>(['character', myCharId])
    const stillThere = cached?.items?.some((x) => x.id === it.item_id)
    if (!stillThere) {
      toast.warning(t('session.reward.item_not_found_toast'))
      haptic.error()
      return
    }
    navigate(`/char/${myCharId}/inventory`, { state: { highlightItemId: it.item_id } })
  }
```

`toast` è già importato da `sonner` in alto. `haptic` e `t` anche.

- [ ] **Step 7: Rendi cliccabile il whisper di grant**

Trova il render del bubble whisper (intorno a riga 296-322) — il blocco `return ( <div key={itemKey(it)} ... > ... </div> )` per il caso messaggio. Sostituisci l'intero `return` di quel ramo con:

```tsx
            const mine = it.user_id === myUserId
            const isWhisper = !!it.recipient_user_id
            const recName = isWhisper ? recipientName(it.recipient_user_id ?? null) : null
            const isGrantToMe =
              !!it.item_id && it.recipient_user_id === myUserId && myCharId !== null
            const Bubble = isGrantToMe ? 'button' : 'div'
            return (
              <Bubble
                key={itemKey(it)}
                {...(isGrantToMe
                  ? {
                      type: 'button' as const,
                      onClick: () => handleGrantClick(it),
                    }
                  : {})}
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm font-body text-left
                  ${isWhisper
                    ? 'bg-[var(--dnd-amber)]/15 border border-[var(--dnd-amber)]/40 italic'
                    : mine
                      ? 'ml-auto bg-gradient-gold text-dnd-ink'
                      : 'bg-dnd-surface border border-dnd-border text-dnd-text'}
                  ${mine && isWhisper ? 'ml-auto' : ''}
                  ${isGrantToMe ? 'cursor-pointer hover:bg-[var(--dnd-amber)]/25 transition-colors' : ''}`}
              >
                {(!mine || isWhisper) && (
                  <p className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5 font-cinzel flex items-center gap-1">
                    {isWhisper && <Lock size={10} />}
                    {it.role === 'game_master' && !isWhisper && <Crown size={10} />}
                    {it.role === 'player' && !isWhisper && <UserIcon size={10} />}
                    {mine ? t('session.you') : senderLabel(it)}
                    {isWhisper && recName && (
                      <span className="text-[var(--dnd-amber)]">
                        {' '}{t('session.whisper.recipient_prefix', { name: recName })}
                      </span>
                    )}
                  </p>
                )}
                <p className="whitespace-pre-wrap break-words">
                  {isGrantToMe && <Gift size={12} className="inline -mt-0.5 mr-1 text-dnd-gold-bright" />}
                  {it.body}
                </p>
                {isGrantToMe && (
                  <p className="text-[10px] uppercase tracking-wider mt-1 text-[var(--dnd-amber)]/80 font-cinzel">
                    {t('session.feed.grant_chip')}
                  </p>
                )}
              </Bubble>
            )
```

- [ ] **Step 8: Mantieni `mt-4` su input row (Task 5)**

Verifica che la riga `<div className="mt-4 flex items-center gap-2">` sia ancora presente (Task 5 l'ha già aggiunta). Se per qualche ragione il file ha avuto un revert, rimettila.

- [ ] **Step 9: Typecheck**

```bash
cd webapp && npx tsc --noEmit
```

Atteso: zero errori. Se TS reclama su `Bubble` come union string/component, conferma sintassi `const Bubble = isGrantToMe ? 'button' : 'div'` (entrambi sono nodi nativi, JSX li accetta come stringa).

In caso di errore TS sull'union dei tipi di onClick/type passati come prop, semplifica con un `if/else` esplicito invece dell'union dinamica:

```tsx
            if (isGrantToMe) {
              return (
                <button
                  key={itemKey(it)}
                  type="button"
                  onClick={() => handleGrantClick(it)}
                  className={...}
                >
                  ...
                </button>
              )
            }
            return (
              <div key={itemKey(it)} className={...}>
                ...
              </div>
            )
```

(Duplicazione mirata: solo se Step 7 dà errori TS. La form `Bubble` è preferita per DRY.)

- [ ] **Step 10: Commit**

```bash
git add webapp/src/pages/session/SessionFeed.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): clickable grant whisper + reward enqueue

SessionFeed now (1) accepts myCharId, (2) on each incremental poll
enqueues GM-grant whispers addressed to me into the reward queue, and
(3) renders the grant whisper as a button that navigates to the
player's inventory with highlightItemId state. The initial fetch is
intentionally excluded so historical grants don't re-pop on reload.
Falls back to a "no longer in inventory" toast when the item is gone.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Frontend — `SessionRoom` integra `RewardPopup`

`SessionRoom` deve:
1. Calcolare `myCharId` dai `live.participants` e passarlo a `SessionFeed`.
2. On mount: `pruneOlderThan(24h)`, `peek()`, e ciclare i popup tramite stato locale `currentReward`.
3. Su CTA "Vedi nell'inventario": `dequeue()`, `navigate('/char/:charId/inventory', { state: { highlightItemId } })`.

**Files:**
- Modify: `webapp/src/pages/SessionRoom.tsx`

- [ ] **Step 1: Import**

Aggiungi in cima al file:

```ts
import { dequeue, peek, pruneOlderThan, type Reward } from '@/lib/rewardQueue'
import RewardPopup from '@/components/session/RewardPopup'
```

- [ ] **Step 2: Stato `currentReward` + effetto di mount**

Subito dopo `const [showGrantItem, setShowGrantItem] = useState(false)` (riga 193), aggiungi:

```ts
  const [currentReward, setCurrentReward] = useState<Reward | null>(null)

  useEffect(() => {
    pruneOlderThan(24 * 60 * 60 * 1000)
    setCurrentReward(peek())
  }, [])
```

`useState` e `useEffect` sono già importati in alto (`import { useMemo, useState }`); aggiungi `useEffect` all'import:

```ts
import { useEffect, useMemo, useState } from 'react'
```

- [ ] **Step 3: Calcola `myCharId`**

Dopo la dichiarazione di `gmUserId` (riga 246), aggiungi:

```ts
  const myParticipant = live?.participants.find((p) => p.user_id === myUserId) ?? null
  const myCharId = myParticipant?.character_id ?? null
```

- [ ] **Step 4: Passa `myCharId` a `SessionFeed`**

Trova il `<SessionFeed ... />` (riga 370-378) e aggiungi `myCharId={myCharId}` ai prop. Il blocco diventa:

```tsx
      <SessionFeed
        code={live.code}
        sessionId={live.id}
        gmUserId={gmUserId}
        myUserId={myUserId}
        myCharId={myCharId}
        participants={live.participants}
        whisperTarget={whisperTarget}
        onClearWhisperTarget={() => setWhisperTarget(null)}
      />
```

- [ ] **Step 5: Render `RewardPopup` quando presente**

Subito dopo il blocco `{showGrantItem && amGm && (...)}` (riga 403-410), aggiungi:

```tsx
      {currentReward && (
        <RewardPopup
          reward={currentReward}
          description={null}
          onDismiss={() => {
            dequeue()
            setCurrentReward(peek())
          }}
          onGoToInventory={() => {
            const r = currentReward
            dequeue()
            setCurrentReward(peek())
            navigate(`/char/${r.char_id}/inventory`, {
              state: { highlightItemId: r.item_id },
            })
          }}
        />
      )}
```

(`description=null` è esplicito: lo schema `SessionMessage` non porta `item_description`. Se in futuro vorrai la descrizione, andrà aggiunta sia al backend sia al `Reward` type.)

- [ ] **Step 6: Typecheck**

```bash
cd webapp && npx tsc --noEmit
```

Atteso: zero errori.

- [ ] **Step 7: Verifica manuale (entrambi i lati)**

Avvia dev stack. Apri due browser diversi (o due profili) loggati come due utenti. Crea una sessione come GM, fai joinare l'altro come player con un character. Dal GM, "Consegna oggetto" → form → seleziona player → consegna.

Atteso (player):
- Polling fetch incrementa il feed.
- Subito dopo l'arrivo del messaggio, il `RewardPopup` appare al centro con nome item e qty.
- Tap su "Vedi nell'inventario" → naviga a `/char/:id/inventory`. (Highlight ancora non visibile — Task 12 lo aggiunge.)
- Tap "OK" → popup chiuso. Se ne consegni un secondo nel frattempo, popup appare di nuovo dopo dismiss del primo.

Atteso (GM):
- Niente popup (GM non è recipient).
- Vedendo i propri whisper grant: bubble grant è già un `button` con chip — vedi Task 12 per testare il click.

Atteso (multi-popup queue):
- Mentre il player è su altra pagina (es. inventario), il GM consegna 3 item in fila. Il player torna su SessionRoom: il primo popup appare; alla dismiss del primo, il secondo; etc.

- [ ] **Step 8: Commit**

```bash
git add webapp/src/pages/SessionRoom.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): wire reward popup queue into SessionRoom

On mount, prunes stale (>24h) reward entries and shows the next popup
from the sessionStorage queue. Cycles through queued grants on each
dismiss. CTA navigates to the recipient's inventory with
highlightItemId state. Also forwards myCharId to SessionFeed so the
chat can detect grants and emit clickable bubbles.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Frontend — `Inventory` highlight via `location.state`

`Inventory.tsx` legge `location.state.highlightItemId`, espande l'item, sblocca il gruppo collapsed se serve, scrolla nel viewport e applica `pulse-glow` per 3 s.

**Files:**
- Modify: `webapp/src/pages/Inventory.tsx`

- [ ] **Step 1: Import aggiuntivi**

Aggiungi all'import esistente:

```ts
import { useState, useCallback, useEffect, useRef } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
```

`useNavigate` e `useLocation` sono nuovi. `useEffect` e `useRef` da aggiungere se mancano.

- [ ] **Step 2: Leggi lo state della location**

Dentro `Inventory()`, dopo `const charId = Number(id)` (riga 25), aggiungi:

```ts
  const location = useLocation()
  const navigate = useNavigate()
  const initialHighlight =
    typeof (location.state as { highlightItemId?: unknown } | null)?.highlightItemId === 'number'
      ? ((location.state as { highlightItemId: number }).highlightItemId)
      : null
  const [highlightId, setHighlightId] = useState<number | null>(initialHighlight)
  const itemRefs = useRef<Record<number, HTMLDivElement | null>>({})
```

- [ ] **Step 3: Effetto per highlight**

Subito dopo gli state esistenti (sopra le mutazioni), aggiungi:

```ts
  useEffect(() => {
    if (highlightId === null) return
    if (!char) return // attendi che la character query carichi
    const target = char.items?.find((i) => i.id === highlightId)
    if (!target) {
      setHighlightId(null)
      navigate(location.pathname, { replace: true, state: null })
      return
    }

    // Espandi l'item
    setExpanded(highlightId)

    // Sblocca il tipo collassato (se serve)
    const TYPE_ORDER = ['weapon', 'armor', 'shield', 'consumable', 'tool', 'accessory', 'gear', 'potion', 'scroll', 'generic', 'other']
    const typeKey = TYPE_ORDER.includes(target.item_type) ? target.item_type : 'other'
    setCollapsedTypes((prev) => {
      if (!prev.has(typeKey)) return prev
      const next = new Set(prev)
      next.delete(typeKey)
      return next
    })

    // Scroll into view (dopo il prossimo frame, così il DOM ha avuto tempo di espandere)
    const rafId = requestAnimationFrame(() => {
      itemRefs.current[highlightId]?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })

    // Fade dopo 3s e clear della state
    const tid = window.setTimeout(() => {
      setHighlightId(null)
      navigate(location.pathname, { replace: true, state: null })
    }, 3000)

    return () => {
      cancelAnimationFrame(rafId)
      window.clearTimeout(tid)
    }
  }, [highlightId, char, navigate, location.pathname])
```

**Nota**: la dichiarazione `const items: Item[] = char.items ?? []` esistente alla riga ~140 (sotto `if (!char) return null`) rimane invariata e continua ad essere usata per il render. La nuova `useEffect` accede direttamente a `char.items` senza creare un secondo `items`.

- [ ] **Step 4: Attacca ref + classe sui wrapper degli item**

Trova il `<m.div key={item.id} layout transition={spring.drift}>` (riga ~232) e modificalo:

```tsx
                      {groupItems.map((item) => (
                        <m.div
                          key={item.id}
                          layout
                          transition={spring.drift}
                          ref={(el) => { itemRefs.current[item.id] = el }}
                          className={highlightId === item.id ? 'animate-pulse-glow' : undefined}
                        >
                          <InventoryItem
                            item={item}
                            ...
                          />
                        </m.div>
                      ))}
```

- [ ] **Step 5: Typecheck**

```bash
cd webapp && npx tsc --noEmit
```

Atteso: zero errori. Possibili attenzioni:
- `m.div` di framer-motion accetta `ref` (è un forwardRef internamente). OK.
- `cancelAnimationFrame` su `rafId` di tipo number (browser): OK.

- [ ] **Step 6: Verifica manuale**

Continuando dal Task 11:

1. Dal GM consegna un item al player.
2. Dal player apri il popup → "Vedi nell'inventario".
3. Atteso: pagina inventario, gruppo del tipo dell'item espanso (se era collapsed lo sblocca), item espanso, glow dorato pulsante per ~3 s, poi torna normale.
4. Torna indietro nel browser (back) → no re-trigger del highlight (state è stato `replace`d a null).
5. Test toast: dal player, mentre sei su SessionRoom con popup aperto, **non** chiudere il popup; in un'altra console rimuovi l'item via API (DELETE `/characters/:id/items/:itemId`). Tap "Vedi nell'inventario": pagina inventario, **niente** glow visibile (item non c'è più), state ripulito senza warning. Caso più realistico: tap sul **chat message** (Task 10) di un grant cui hai poi cancellato l'item: deve apparire il toast "Oggetto non più presente nel tuo inventario" senza navigare.

- [ ] **Step 7: Commit**

```bash
git add webapp/src/pages/Inventory.tsx
git commit -m "$(cat <<'EOF'
feat(webapp): highlight item in inventory after grant navigation

Reads location.state.highlightItemId, expands the matched item,
forces its type group open, scrolls it into the viewport and applies
the pulse-glow animation for 3s. Clears history state via replace so
browser back doesn't re-trigger the highlight. If the item is gone
between navigation and mount, silently no-ops and clears state.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Verifica end-to-end + build di produzione

Verifica integrata e build per Pages.

**Files:**
- (nessuno modificato — eventuale rebuild dei `docs/app/` segue la procedura `npm run build:prod`)

- [ ] **Step 1: Verifica end-to-end**

Avvia dev stack (API + webapp). Esegui in sequenza:

1. **Fix #1** — Apri character → Equipment screen. Tap ogni slot vuoto: il picker compare centrato a viewport. Tap su un item equipped: SlotActionSheet emerge dal basso, niente clipping. Cambia screen (swipe) e verifica che nessun modal sia visibile.

2. **Fix #2** — SessionRoom → manda 3 messaggi → l'input ha respiro visivo dall'ultimo bubble. Apri whisper → la chip ambra appare sopra l'input.

3. **Fix #3** — GM consegna item al player presente in SessionRoom. Player vede popup centrato col nome/qty, "Vedi nell'inventario", "OK". GM consegna 3 item mentre player è su `/char/:id`. Player torna a SessionRoom: 3 popup in sequenza.

4. **Fix #4** — Dal popup "Vedi nell'inventario" → highlight su item per ~3s. Dal chat message di un grant: tap → highlight (item presente). Cancella l'item, tap chat message → toast "non più presente".

5. **Migration idempotenza** — Stop/start dell'API più volte: nessun errore "duplicate column" sui log.

6. **Reload sessionStorage** — Player riceve grant, popup aperto, ricarica la pagina (F5): popup ricompare al rientro su SessionRoom. Dismiss tutti i popup → reload → niente popup (queue vuota).

- [ ] **Step 2: Build di produzione (per merge a main)**

Quando tutti i fix sono validati e il PR è pronto al merge:

```bash
cd webapp && npm run build:prod
# Lo script: switcha .env.local a https://api.cischi.dev, fa tsc + vite build,
# ripristina .env.local a http://localhost:8000, e fa git add docs/app/.
```

**Quirk noto** (vedi CLAUDE.md): dopo `build:prod` il `.env.local` torna a `http://localhost:8000`, ma il dev locale usa `127.0.0.1:8000`. Riscrivi:

```bash
printf 'VITE_API_BASE_URL=http://127.0.0.1:8000\n' > webapp/.env.local
```

- [ ] **Step 3: Commit del build (se necessario)**

Se `npm run build:prod` ha staged file in `docs/app/`:

```bash
git status
git commit -m "$(cat <<'EOF'
chore(webapp): rebuild for session grants and equipment modal fixes

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Apri PR**

```bash
git push -u origin <branch>
gh pr create --title "Session grants UX + equipment modal portal fixes" --body "$(cat <<'EOF'
## Summary
- portal `SlotActionSheet` and `EquipItemPicker` to body to escape `CharacterSwiper` transform clipping
- adds `mt-4` between session chat last message and input
- new GM-grant flow: backend stores `item_id`/`item_name`/`item_quantity` on the recipient whisper; frontend enqueues a reward popup on poll, queue persists in `sessionStorage`, sequential popups on return; CTA + chat message both navigate to inventory with `highlightItemId` state and a 3s gold pulse-glow

## Test plan
- [ ] Equipment screen modals stay centered on all 3 swiper screens (Hero/Equipment/Menu)
- [ ] Session chat shows breathing room above input
- [ ] GM grant → recipient sees centered RewardPopup
- [ ] Multi-grant while away → sequential popups on return to SessionRoom
- [ ] CTA "Vedi nell'inventario" navigates + glows for ~3s
- [ ] Tap grant chat bubble → same flow
- [ ] Tap grant chat bubble after deleting the item → "non più presente" toast
- [ ] Migration idempotent over restarts
EOF
)"
```

---

## Self-review — copertura della spec

| Spec section | Task |
|---|---|
| Backend — modello + migration | 1 |
| Backend — gm_grant_item populate + feed mapping + schema | 2 |
| Frontend types | 3 |
| `SlotActionSheet` + `EquipItemPicker` portal (#1) | 4 |
| Spacing input chat (#2) | 5 |
| `rewardQueue.ts` | 6 |
| `pulse-glow` CSS | 7 |
| `RewardPopup.tsx` | 8 |
| i18n keys | 9 |
| `SessionFeed` enqueue + click + `myCharId` prop | 10 |
| `SessionRoom` integration + queue cycle + 24h prune | 11 |
| `Inventory` highlight + `location.state` + 3s fade + replace state | 12 |
| End-to-end verification + production build | 13 |

Tutte le sezioni della spec sono coperte. Edge cases (item assente, queue stale, sessionStorage disabilitato, migration idempotente, popup multipli sequenziali) hanno step di verifica espliciti nei Task 11–13.
