# Character Sheet — Condition Polish — Design

**Date:** 2026-04-22
**Scope:** Telegram Mini App — character sheet conditions page + main hero card
**Status:** Approved, ready for implementation plan

## Goals

Two improvements to the character sheet's condition handling:

1. **Condition detail modal** — tapping an info icon on any condition opens a modal with the SRD 5.1 description (localized).
2. **Exhaustion label format** — use the existing interpolated locale `"Spossatezza (livello {{level}})"` in both the CharacterMain hero pill and the SessionRoom participant row.

---

## Non-goals

- No new API endpoints.
- No changes to the condition-toggling behavior.
- No dynamic fetch of condition descriptions (hardcoded in locale files, bilingual).

---

## Schema changes

None.

---

## API changes

None.

---

## Frontend — condition detail modal

### `webapp/src/pages/Conditions.tsx`

Each condition button gets a corner ⓘ info icon. Layout:

```tsx
<m.button onClick={() => toggle(cond.key)} ...>
  <Icon ... />
  <span>{t(`character.conditions.${cond.key}`)}</span>
  <button
    type="button"
    aria-label={t('character.conditions.detail_aria')}
    onClick={(e) => { e.stopPropagation(); setDetailKey(cond.key) }}
    className="ml-auto p-1 text-dnd-text-muted hover:text-dnd-gold-bright"
  >
    <Info size={14} />
  </button>
</m.button>
```

Local state: `const [detailKey, setDetailKey] = useState<string | null>(null)`. When non-null, render `<ConditionDetailModal condKey={detailKey} onClose={() => setDetailKey(null)} />`.

For the exhaustion block (which has its own separate UI, not in the grid), add an ⓘ icon next to its title. Tap opens the same modal with `condKey="exhaustion"`.

Critical: `e.stopPropagation()` on info button prevents the outer toggle from firing.

### New component: `webapp/src/pages/conditions/ConditionDetailModal.tsx`

Full-screen modal matching the pattern of `webapp/src/pages/spells/CastSpellModal.tsx`:

```tsx
interface Props { condKey: string; onClose: () => void }

export default function ConditionDetailModal({ condKey, onClose }: Props) {
  const { t } = useTranslation()
  const isExhaustion = condKey === 'exhaustion'

  return (
    <Modal onClose={onClose}>
      <h2>{t(`character.conditions.${condKey}`, { level: 0 })}</h2>
      <p>{t(`character.conditions.desc.${condKey}`)}</p>

      {isExhaustion && (
        <ol>
          {(t('character.conditions.desc.exhaustion_levels', { returnObjects: true }) as string[])
            .map((line, i) => <li key={i}>{line}</li>)}
        </ol>
      )}

      <Button onClick={onClose}>{t('common.close')}</Button>
    </Modal>
  )
}
```

Uses i18next's `returnObjects: true` option for the exhaustion levels array.

### `webapp/src/pages/CharacterMain.tsx:319`

Currently:

```tsx
value={`${t(`character.conditions.${key}`)}${typeof val === 'number' && val > 1 ? ` (${val})` : ''}`}
```

Replaced with the shared helper (also used by Spec A in SessionRoom):

```tsx
value={formatCondition(key, val, t)}
```

Where `formatCondition` is imported from `webapp/src/lib/conditions.ts` (the new helper defined in Spec A — adding it as a single shared module avoids duplication).

---

## i18n — SRD 5.1 descriptions

Under OGL — SRD 5.1 condition text is explicitly licensable. Italian translation by hand (adapted from the official Italian 5e reference where available, else translated from SRD).

Keys added to `webapp/src/locales/{it,en}.json` under `character.conditions`:

```jsonc
{
  "character": {
    "conditions": {
      // ... existing keys ...
      "detail_aria": "Mostra dettagli condizione" / "Show condition details",
      "desc": {
        "blinded": "...",
        "charmed": "...",
        "deafened": "...",
        "exhaustion": "L'affaticamento si misura in 6 livelli progressivi...",
        "exhaustion_levels": [
          "Livello 1: Svantaggio alle prove di caratteristica.",
          "Livello 2: Velocità dimezzata.",
          "Livello 3: Svantaggio ai tiri per colpire e ai tiri salvezza.",
          "Livello 4: Punti ferita massimi dimezzati.",
          "Livello 5: Velocità ridotta a 0.",
          "Livello 6: Morte."
        ],
        "frightened": "...",
        "grappled": "...",
        "incapacitated": "...",
        "invisible": "...",
        "paralyzed": "...",
        "petrified": "...",
        "poisoned": "...",
        "prone": "...",
        "restrained": "...",
        "stunned": "...",
        "unconscious": "..."
      }
    }
  }
}
```

All 14 base conditions + exhaustion general description + exhaustion_levels array. Text verbatim from SRD 5.1 English; Italian translated preserving mechanical terminology.

---

## Testing strategy (manual)

| # | Scenario | Pass criteria |
|---|---|---|
| 1 | Open condition page | Each toggle shows ⓘ icon next to label |
| 2 | Tap ⓘ on "Blinded" | Modal opens with "Accecato" title + SRD description in Italian |
| 3 | Tap condition body (not ⓘ) | Toggle flips, modal does NOT open |
| 4 | Switch locale to English | Modal text now in English |
| 5 | Tap ⓘ on exhaustion | Modal shows general description + 6-line level table |
| 6 | Set exhaustion to 3 | Hero section on CharacterMain shows `Spossatezza (livello 3)` pill |
| 7 | Join session | SessionRoom ParticipantRow for own character shows same exhaustion pill format |
| 8 | Verify modal closes | Tap close button + tap outside (if modal supports backdrop click) both close |

---

## Dependencies on Spec A

- The shared helper `webapp/src/lib/conditions.ts` is defined as part of Spec A (also consumed by SessionRoom there). Spec B consumes it in CharacterMain. The two specs can land in either order:
  - If Spec A lands first → Spec B just imports `formatCondition`.
  - If Spec B lands first → Spec B creates the helper; Spec A's ParticipantRow imports it.

Either implementation order is safe. Recommend landing Spec B first since it's smaller and validates the shared helper in isolation.
