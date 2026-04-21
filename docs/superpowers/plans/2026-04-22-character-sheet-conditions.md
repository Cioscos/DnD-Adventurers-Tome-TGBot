# Character Sheet — Condition Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tap-ⓘ detail modal showing SRD 5.1 text for each D&D 5e condition in the character sheet, plus use the interpolated exhaustion label (`Spossatezza (livello 3)`) in the CharacterMain hero pill.

**Architecture:** Pure frontend change. Creates a shared `formatCondition()` helper (reused by Spec A's SessionRoom work), a `ConditionDetailModal` component, and hardcoded SRD 5.1 text in both locale files. No API or schema changes.

**Tech Stack:** React 18, react-i18next, framer-motion, lucide-react, TypeScript. Built with Vite, deployed as a Telegram Mini App.

---

## Environment notes

- Work from the project's existing feature branch `docs/session-and-conditions-specs` (the specs have already been committed there). Create a fresh feature branch `feat/condition-detail-modal` off of it.
- No automated test suite is configured. Verification is `tsc --noEmit` for TypeScript, plus manual browser testing via the Vite dev server (`npm run dev`) on `http://localhost:5173/`.
- Before the final PR commit, run `cd webapp && npm run build:prod` to refresh `docs/app/` per `CLAUDE.md`.
- Python commands (`uv run …`) must run in the user's Windows PowerShell. If the agent is in WSL, **do not run `uv sync` / `uv run`** — ask the user. The changes here are frontend-only, so no Python commands are required.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `webapp/src/lib/conditions.ts` | Create | Shared `formatCondition(key, val, t)` helper used by both CharacterMain and (later) SessionRoom. |
| `webapp/src/pages/conditions/ConditionDetailModal.tsx` | Create | Full-screen modal rendering the condition name + SRD description (plus exhaustion level table when applicable). |
| `webapp/src/pages/Conditions.tsx` | Modify | Restructure each condition toggle into a flex row of (toggle-button, info-button); add modal state. |
| `webapp/src/pages/CharacterMain.tsx` | Modify | Replace the inline condition-label construction with a call to `formatCondition`. |
| `webapp/src/locales/it.json` | Modify | Add `character.conditions.detail_aria` + `character.conditions.desc.*` (14 conditions + exhaustion general + `exhaustion_levels` array). |
| `webapp/src/locales/en.json` | Modify | Same keys in English. |

---

## Task 1: Shared `formatCondition` helper

**Files:**
- Create: `webapp/src/lib/conditions.ts`

- [ ] **Step 1: Create the helper file with the exhaustion-aware formatter**

```ts
import type { TFunction } from 'i18next'

/**
 * Localise a condition label for display in a pill / list.
 *
 * Exhaustion renders with its level (e.g. "Spossatezza (livello 3)") when
 * val is a positive number; all other conditions render by slug.
 */
export function formatCondition(
  key: string,
  val: unknown,
  t: TFunction,
): string {
  if (key === 'exhaustion' && typeof val === 'number' && val > 0) {
    return t('character.conditions.exhaustion', { level: val })
  }
  return t(`character.conditions.${key}`)
}
```

- [ ] **Step 2: Type-check**

Run:
```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/lib/conditions.ts
git commit -m "feat(webapp): add shared formatCondition helper"
```

---

## Task 2: Add SRD description locale keys (Italian)

**Files:**
- Modify: `webapp/src/locales/it.json` (inside the existing `character.conditions` object, between `"unconscious"` and the closing brace)

- [ ] **Step 1: Insert `detail_aria` and `desc` block after `"unconscious": "Privo di Sensi"`**

In `webapp/src/locales/it.json`, replace the existing `"unconscious": "Privo di Sensi"` line and its trailing `}` with the block below. The trailing comma after `"Privo di Sensi"` is required.

```jsonc
      "unconscious": "Privo di Sensi",
      "detail_aria": "Mostra dettagli condizione",
      "desc": {
        "blinded": "Un personaggio cecato non può vedere e fallisce automaticamente ogni prova di caratteristica che richiede la vista. I tiri per colpire contro di lui hanno vantaggio, i suoi hanno svantaggio.",
        "charmed": "Un personaggio affascinato non può attaccare chi lo affascina né prenderlo come bersaglio di capacità dannose o effetti magici. Chi lo affascina ha vantaggio nelle prove di caratteristica sociali.",
        "deafened": "Un personaggio assordato non può sentire e fallisce automaticamente ogni prova di caratteristica che richiede l'udito.",
        "exhaustion": "L'affaticamento si misura in sei livelli progressivi. Ogni livello aggiunge un effetto cumulativo ai precedenti.",
        "exhaustion_levels": [
          "Livello 1: Svantaggio alle prove di caratteristica.",
          "Livello 2: Velocità dimezzata.",
          "Livello 3: Svantaggio ai tiri per colpire e ai tiri salvezza.",
          "Livello 4: Punti ferita massimi dimezzati.",
          "Livello 5: Velocità ridotta a 0.",
          "Livello 6: Morte."
        ],
        "frightened": "Un personaggio spaventato ha svantaggio alle prove di caratteristica e ai tiri per colpire finché la fonte della paura è entro linea di vista. Non può muoversi volontariamente più vicino alla fonte.",
        "grappled": "Un personaggio afferrato ha velocità ridotta a 0 e non può beneficiare di bonus alla velocità. La condizione termina se chi lo afferra viene incapacitato, o se un effetto lo rimuove dalla portata di chi lo afferra.",
        "incapacitated": "Un personaggio incapacitato non può eseguire azioni né reazioni.",
        "invisible": "Un personaggio invisibile non può essere visto senza l'aiuto di magia o sensi speciali. È considerato fortemente occultato. I tiri per colpire contro di lui hanno svantaggio, i suoi hanno vantaggio.",
        "paralyzed": "Un personaggio paralizzato è incapacitato e non può muoversi o parlare. Fallisce automaticamente i tiri salvezza di Forza e Destrezza. I tiri per colpire contro di lui hanno vantaggio; ogni colpo in mischia entro 1,5 metri è un critico.",
        "petrified": "Un personaggio pietrificato è trasformato, assieme a ciò che indossa o trasporta di non magico, in materia solida inanimata. È incapacitato e non può muoversi o parlare. Ha resistenza a tutti i danni e immunità a veleno e malattie. Il suo peso aumenta di dieci volte.",
        "poisoned": "Un personaggio avvelenato ha svantaggio ai tiri per colpire e alle prove di caratteristica.",
        "prone": "Un personaggio prono può muoversi solo strisciando, a meno che non si rialzi. Ha svantaggio ai tiri per colpire. I tiri per colpire contro di lui hanno vantaggio entro 1,5 metri, svantaggio oltre.",
        "restrained": "Un personaggio trattenuto ha velocità 0 e non può beneficiare di bonus alla velocità. I tiri per colpire contro di lui hanno vantaggio, i suoi hanno svantaggio. Ha svantaggio ai tiri salvezza di Destrezza.",
        "stunned": "Un personaggio stordito è incapacitato, non può muoversi e parla a malapena. Fallisce automaticamente i tiri salvezza di Forza e Destrezza. I tiri per colpire contro di lui hanno vantaggio.",
        "unconscious": "Un personaggio privo di sensi è incapacitato, non può muoversi né parlare, ignora l'ambiente. Lascia cadere ciò che tiene e cade prono. Fallisce automaticamente i tiri salvezza di Forza e Destrezza. I tiri per colpire contro di lui hanno vantaggio; ogni colpo in mischia entro 1,5 metri è un critico."
      }
    },
```

The outer `},` closes the `conditions` object — it was already present before this change (end of the original block). Keep it.

- [ ] **Step 2: Validate JSON**

Run:
```bash
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/it.json','utf8'))"
```

Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/locales/it.json
git commit -m "feat(webapp): add Italian SRD condition descriptions"
```

---

## Task 3: Add SRD description locale keys (English)

**Files:**
- Modify: `webapp/src/locales/en.json` (same structural location as Task 2)

- [ ] **Step 1: Insert `detail_aria` and `desc` block after `"unconscious": "Unconscious"`**

```jsonc
      "unconscious": "Unconscious",
      "detail_aria": "Show condition details",
      "desc": {
        "blinded": "A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage.",
        "charmed": "A charmed creature can't attack the charmer or target the charmer with harmful abilities or magical effects. The charmer has advantage on any ability check to interact socially with the creature.",
        "deafened": "A deafened creature can't hear and automatically fails any ability check that requires hearing.",
        "exhaustion": "Exhaustion is measured in six progressive levels. Each level adds a cumulative effect on top of the previous ones.",
        "exhaustion_levels": [
          "Level 1: Disadvantage on ability checks.",
          "Level 2: Speed halved.",
          "Level 3: Disadvantage on attack rolls and saving throws.",
          "Level 4: Hit point maximum halved.",
          "Level 5: Speed reduced to 0.",
          "Level 6: Death."
        ],
        "frightened": "A frightened creature has disadvantage on ability checks and attack rolls while the source of its fear is within line of sight. The creature can't willingly move closer to the source of its fear.",
        "grappled": "A grappled creature's speed becomes 0, and it can't benefit from any bonus to its speed. The condition ends if the grappler is incapacitated, or if an effect removes the grappled creature from the reach of the grappler.",
        "incapacitated": "An incapacitated creature can't take actions or reactions.",
        "invisible": "An invisible creature is impossible to see without the aid of magic or a special sense. It's considered heavily obscured. Attack rolls against the creature have disadvantage, and its attack rolls have advantage.",
        "paralyzed": "A paralyzed creature is incapacitated and can't move or speak. It automatically fails Strength and Dexterity saving throws. Attack rolls against it have advantage, and any attack that hits the creature is a critical hit if the attacker is within 5 feet.",
        "petrified": "A petrified creature is transformed, along with any nonmagical object it's wearing or carrying, into a solid inanimate substance. It's incapacitated and can't move or speak. It has resistance to all damage and immunity to poison and disease. Its weight increases by a factor of ten.",
        "poisoned": "A poisoned creature has disadvantage on attack rolls and ability checks.",
        "prone": "A prone creature's only movement option is to crawl, unless it stands up. It has disadvantage on attack rolls. An attack roll against the creature has advantage if the attacker is within 5 feet; otherwise, disadvantage.",
        "restrained": "A restrained creature's speed becomes 0, and it can't benefit from any bonus to its speed. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage. It has disadvantage on Dexterity saving throws.",
        "stunned": "A stunned creature is incapacitated, can't move, and can speak only falteringly. It automatically fails Strength and Dexterity saving throws. Attack rolls against it have advantage.",
        "unconscious": "An unconscious creature is incapacitated, can't move or speak, and is unaware of its surroundings. The creature drops whatever it's holding and falls prone. It automatically fails Strength and Dexterity saving throws. Attack rolls against it have advantage, and any attack that hits is a critical hit if the attacker is within 5 feet."
      }
    },
```

- [ ] **Step 2: Validate JSON**

```bash
node -e "JSON.parse(require('fs').readFileSync('webapp/src/locales/en.json','utf8'))"
```

Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/locales/en.json
git commit -m "feat(webapp): add English SRD condition descriptions"
```

---

## Task 4: Create `ConditionDetailModal` component

**Files:**
- Create: `webapp/src/pages/conditions/ConditionDetailModal.tsx`

- [ ] **Step 1: Create the modal**

```tsx
import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'

interface ConditionDetailModalProps {
  condKey: string
  exhaustionLevel?: number
  onClose: () => void
}

export default function ConditionDetailModal({
  condKey,
  exhaustionLevel = 0,
  onClose,
}: ConditionDetailModalProps) {
  const { t } = useTranslation()
  const isExhaustion = condKey === 'exhaustion'

  const title = isExhaustion
    ? (exhaustionLevel > 0
        ? t('character.conditions.exhaustion', { level: exhaustionLevel })
        : t('character.conditions.exhaustion_condition'))
    : t(`character.conditions.${condKey}`)

  const description = t(`character.conditions.desc.${condKey}`)

  const levels = isExhaustion
    ? (t('character.conditions.desc.exhaustion_levels', {
        returnObjects: true,
      }) as string[])
    : []

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold font-cinzel text-dnd-gold">{title}</h3>
          <button
            onClick={onClose}
            aria-label={t('common.close')}
            className="text-dnd-text-secondary text-sm p-1"
          >
            &#x2715;
          </button>
        </div>
        <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
          {description}
        </p>
        {isExhaustion && levels.length > 0 && (
          <ol className="space-y-1 text-sm font-body list-none pl-0">
            {levels.map((line, i) => (
              <li
                key={i}
                className="pl-2 border-l-2 border-dnd-gold/40 text-dnd-text-muted"
              >
                {line}
              </li>
            ))}
          </ol>
        )}
        <DndButton variant="secondary" onClick={onClose} className="w-full">
          {t('common.close')}
        </DndButton>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors. If the build complains about `DndButton` import path, verify with `ls webapp/src/components/DndButton*` — the path should match other modals (see `webapp/src/pages/spells/CastSpellModal.tsx` for the exact import style).

- [ ] **Step 3: Commit**

```bash
git add webapp/src/pages/conditions/ConditionDetailModal.tsx
git commit -m "feat(webapp): add ConditionDetailModal component"
```

---

## Task 5: Wire modal + ⓘ button into `Conditions.tsx`

**Files:**
- Modify: `webapp/src/pages/Conditions.tsx`

This task restructures each condition toggle into a flex row containing (a) the toggle button, (b) an info button next to it. Nesting a `<button>` inside another `<button>` is invalid HTML, so the card becomes a `div` wrapping two siblings.

- [ ] **Step 1: Update imports** — add `Info` from lucide-react and `useState` is already imported; add `ConditionDetailModal`:

In `webapp/src/pages/Conditions.tsx`, replace the existing lucide import block (lines 5-10) with:

```tsx
import {
  EyeOff, Heart, VolumeX, Ghost, Link2, Cloud, Eye, Zap, Mountain,
  FlaskConical, ArrowDown, Lock, Sparkle, Moon, Flame, Info,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
```

And add this import after the existing `@/styles/motion` import (around line 15):

```tsx
import ConditionDetailModal from '@/pages/conditions/ConditionDetailModal'
```

- [ ] **Step 2: Add modal state**

In the `Conditions()` component body, next to the existing `useState` calls, add:

```tsx
const [detailKey, setDetailKey] = useState<string | null>(null)
```

- [ ] **Step 3: Replace the condition grid card markup**

Find the block that currently reads (around lines 143–169):

```tsx
{CONDITIONS.map((cond) => {
  const Icon = cond.icon
  const active = !!conditions[cond.key]
  return (
    <m.button
      key={cond.key}
      onClick={() => toggle(cond.key)}
      variants={{
        initial: { opacity: 0, y: 8 },
        animate: { opacity: 1, y: 0 },
      }}
      className={`flex items-center gap-2 px-3 py-3 rounded-xl border text-left transition-colors
        ${active
          ? 'bg-gradient-to-br from-[var(--dnd-crimson-deep)]/40 to-[var(--dnd-crimson)]/20 border-dnd-crimson/60 shadow-halo-danger text-dnd-text'
          : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'}`}
      whileTap={{ scale: 0.95 }}
      animate={active ? { x: [-2, 2, -1, 1, 0] } : {}}
      transition={{ duration: 0.25 }}
    >
      <Icon size={18} className={active ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text-faint'} />
      <span className="text-sm font-body leading-tight">
        {t(`character.conditions.${cond.key}`)}
      </span>
    </m.button>
  )
})}
```

Replace with:

```tsx
{CONDITIONS.map((cond) => {
  const Icon = cond.icon
  const active = !!conditions[cond.key]
  return (
    <m.div
      key={cond.key}
      variants={{
        initial: { opacity: 0, y: 8 },
        animate: { opacity: 1, y: 0 },
      }}
      className={`flex items-center rounded-xl border transition-colors
        ${active
          ? 'bg-gradient-to-br from-[var(--dnd-crimson-deep)]/40 to-[var(--dnd-crimson)]/20 border-dnd-crimson/60 shadow-halo-danger text-dnd-text'
          : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'}`}
      animate={active ? { x: [-2, 2, -1, 1, 0] } : {}}
      transition={{ duration: 0.25 }}
    >
      <m.button
        type="button"
        onClick={() => toggle(cond.key)}
        whileTap={{ scale: 0.95 }}
        className="flex-1 flex items-center gap-2 px-3 py-3 text-left"
      >
        <Icon size={18} className={active ? 'text-[var(--dnd-crimson-bright)]' : 'text-dnd-text-faint'} />
        <span className="text-sm font-body leading-tight">
          {t(`character.conditions.${cond.key}`)}
        </span>
      </m.button>
      <button
        type="button"
        aria-label={t('character.conditions.detail_aria')}
        onClick={() => setDetailKey(cond.key)}
        className="shrink-0 p-3 text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
      >
        <Info size={16} />
      </button>
    </m.div>
  )
})}
```

- [ ] **Step 4: Add the same info button to the exhaustion tracker header**

Find the block starting at the `<Flame size={16} ...>` icon (around line 99) inside the exhaustion `Surface`. It currently reads:

```tsx
<div className="flex items-center justify-between mb-3">
  <div className="flex items-center gap-2">
    <Flame size={16} className="text-[var(--dnd-amber)]" />
    <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-dim">
      {t('character.conditions.exhaustion_condition')}
    </span>
  </div>
  <span className={`text-lg font-display font-black
    ${currentExhaustion > 0 ? 'text-[var(--dnd-amber)]' : 'text-dnd-text-faint'}`}>
    {currentExhaustion}<span className="text-sm text-dnd-text-muted">/6</span>
  </span>
</div>
```

Replace with:

```tsx
<div className="flex items-center justify-between mb-3">
  <div className="flex items-center gap-2">
    <Flame size={16} className="text-[var(--dnd-amber)]" />
    <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-dim">
      {t('character.conditions.exhaustion_condition')}
    </span>
    <button
      type="button"
      aria-label={t('character.conditions.detail_aria')}
      onClick={() => setDetailKey('exhaustion')}
      className="text-dnd-text-muted hover:text-dnd-gold-bright transition-colors"
    >
      <Info size={14} />
    </button>
  </div>
  <span className={`text-lg font-display font-black
    ${currentExhaustion > 0 ? 'text-[var(--dnd-amber)]' : 'text-dnd-text-faint'}`}>
    {currentExhaustion}<span className="text-sm text-dnd-text-muted">/6</span>
  </span>
</div>
```

- [ ] **Step 5: Render the modal at the end of `Conditions()` return**

Just before the closing `</Layout>` tag, add:

```tsx
{detailKey !== null && (
  <ConditionDetailModal
    condKey={detailKey}
    exhaustionLevel={currentExhaustion}
    onClose={() => setDetailKey(null)}
  />
)}
```

- [ ] **Step 6: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Manual verification** — start the dev stack and exercise the new UI:

Ask the user to ensure the Vite dev server is running:
```
cd webapp && npm run dev
```

Then:
1. Open http://localhost:5173/ in a browser.
2. Pick a character → go to Conditions page.
3. Verify every condition card now has an ⓘ icon on its right side.
4. Tap the ⓘ icon on "Accecato" — modal should open with "Accecato" title + Italian SRD description.
5. Close modal → tap the condition body — it should toggle on/off without reopening the modal.
6. Tap the ⓘ next to the Flame icon in the Exhaustion header — modal should show general text plus the 6-line level table.
7. Set exhaustion to 3, then open the modal again — title should read "Spossatezza (livello 3)".
8. Toggle the webapp language to English (Settings page) — modal text should change to English on reopen.

If any step fails, diagnose and fix inline (most likely issue: i18next returnObjects typing — if `t(...)` returns a string instead of array, cast via `as unknown as string[]`).

- [ ] **Step 8: Commit**

```bash
git add webapp/src/pages/Conditions.tsx
git commit -m "feat(webapp): add condition detail modal with SRD description"
```

---

## Task 6: Use `formatCondition` in `CharacterMain.tsx` hero pill

**Files:**
- Modify: `webapp/src/pages/CharacterMain.tsx` (around line 312-325)

- [ ] **Step 1: Add the import**

At the top of the file, add after the existing `@/styles/motion` import:

```tsx
import { formatCondition } from '@/lib/conditions'
```

- [ ] **Step 2: Replace the inline pill label construction**

Find the "Active conditions" block (around lines 312–325). It currently reads:

```tsx
{/* Active conditions */}
{activeConditions.length > 0 && (
  <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14">
    {activeConditions.map(([key, val]) => (
      <StatPill
        key={key}
        icon={<CircleDot size={10} />}
        value={`${t(`character.conditions.${key}`)}${typeof val === 'number' && val > 1 ? ` (${val})` : ''}`}
        tone="crimson"
        size="sm"
      />
    ))}
  </div>
)}
```

Replace the `value` prop:

```tsx
{/* Active conditions */}
{activeConditions.length > 0 && (
  <div className="flex flex-wrap gap-1.5 mt-2 overflow-x-auto scrollbar-hide max-h-14">
    {activeConditions.map(([key, val]) => (
      <StatPill
        key={key}
        icon={<CircleDot size={10} />}
        value={formatCondition(key, val, t)}
        tone="crimson"
        size="sm"
      />
    ))}
  </div>
)}
```

- [ ] **Step 3: Type-check**

```bash
cd webapp && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Manual verification**

Back in the browser (dev server still running):

1. Go to a character's Conditions page, set exhaustion level to 3.
2. Navigate back to the character main screen.
3. Verify the condition pill under the hero section reads `Spossatezza (livello 3)` (NOT the old `Spossatezza (3)` shorter form).
4. Activate another non-exhaustion condition (e.g. Poisoned) → pill reads `Avvelenato`.
5. Set exhaustion to 0 → pill disappears (unchanged behavior).

- [ ] **Step 5: Commit**

```bash
git add webapp/src/pages/CharacterMain.tsx
git commit -m "feat(webapp): use formatCondition for hero exhaustion label"
```

---

## Task 7: Final production build + commit

**Files:**
- Modify: `docs/app/` (generated build output — rebuilt by the script)

- [ ] **Step 1: Run production build**

```bash
cd webapp && npm run build:prod
```

Expected: build succeeds (TypeScript + Vite), `docs/app/` updated, `git add docs/app/` already staged by the script.

- [ ] **Step 2: Verify staged build output**

```bash
git status
```

Expected: `docs/app/` files staged, no untracked files in `webapp/src`.

- [ ] **Step 3: Commit production build**

```bash
git commit -m "chore(webapp): rebuild docs/app for condition detail modal"
```

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin feat/condition-detail-modal
gh pr create --title "feat(webapp): condition detail modal + interpolated exhaustion label" --body "$(cat <<'EOF'
## Summary
- Adds an ⓘ info button on each condition card opening a modal with SRD 5.1 description (IT + EN locales)
- Adds the same info button to the exhaustion tracker header, modal also shows the per-level effect table
- Replaces the inline pill label construction in CharacterMain with a shared `formatCondition` helper that uses the interpolated exhaustion label (`Spossatezza (livello N)`)

## Test plan
- [ ] Open Conditions page → each card shows ⓘ icon
- [ ] Tap ⓘ on Blinded → modal shows SRD description
- [ ] Tap condition body → toggles without opening modal
- [ ] Switch language to EN → modal content in English
- [ ] Tap ⓘ on exhaustion → modal shows 6-level table
- [ ] Set exhaustion to 3 → hero section pill reads "Spossatezza (livello 3)"

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review notes

**Coverage vs. spec:** every spec requirement (ⓘ icon per condition, same for exhaustion tracker, modal with description + optional level table, shared `formatCondition`, hero pill label swap, bilingual locale) is mapped to a task.

**No placeholders:** all JSON additions are fully written out, all code snippets are complete, all commands have exact expected output.

**Type consistency:** `formatCondition` signature `(key, val, t)` is identical between its definition (Task 1) and its consumer (Task 6). Shared module path `@/lib/conditions` matches existing `@/lib/*` alias convention used elsewhere (`@/components/ui`, `@/pages/...`, etc.). `ConditionDetailModal` prop names (`condKey`, `exhaustionLevel`, `onClose`) match its consumer in Task 5.

**Dependencies:** Spec A's plan (`2026-04-22-session-room-ux-privacy.md`) will import `formatCondition` from `@/lib/conditions`. Because this plan lands first and creates the helper, Spec A's plan can import it without any refactoring.
