# Gruppo F — XP + Level-up button (design)

**Gruppo roadmap:** F — `istruzioni.md` §1.8.
**Data:** 2026-04-23.
**Branch:** `feat/xp-level-up-gruppo-f`.
**Dipendenze:** Gruppo A (`lib/xpThresholds.ts`, `HeroXPBar`), Gruppo B (auto-HP al level-up, toast `hp_gained`).

---

## 1. Obiettivo

Completare la pagina `/xp` (`webapp/src/pages/Experience.tsx`) aggiungendo:

1. Un bottone **LEVEL UP** che porta il personaggio direttamente al livello successivo (set XP al threshold di `level + 1`).
2. Bottoni quick-XP **proporzionali** agli XP necessari per il prossimo livello, in sostituzione dei valori fissi attuali `[50, 100, 200, 500]`.

Fonte delle richieste: `istruzioni.md` §1.8 ("Aggiungere pulsante/funzione di level up nella schermata esperienza" + "I pulsanti per aggiungere quantità predefinite di XP devono scalare proporzionalmente agli XP necessari per il livello successivo").

## 2. Scope

**In-scope:**
- `webapp/src/pages/Experience.tsx` (modifiche UI).
- `webapp/src/lib/xpThresholds.ts` (nuovo helper `quickXpAmounts`).
- `webapp/src/locales/it.json` e `en.json` (nuove chiavi i18n).

**Fuori scope:**
- Modale scelta classe per level-up multiclass → **Gruppo G**.
- Modifiche backend — PATCH `/xp` già gestisce `{set}` e `{add}` con auto-level single-class + auto-HP (verificato in `api/routers/characters.py:318-365`).
- Modifiche a `HeroXPBar` o banner multiclass "livello disponibile" (già corretti dal Gruppo A/B).

## 3. Decisioni

### 3.1 LEVEL UP button

**Semantica:** shortcut "vai al prossimo livello". Click → set XP = `XP_THRESHOLDS[level]`.

**Visibilità:**
- Mostra se `level < 20`.
- Nascondi a `level === 20`.

**Click:** `mutation.mutate({ set: XP_THRESHOLDS[level] })`.

**Comportamento risultante:**
- **Single-class:** backend auto-bumpa class level, auto-HP, toast `+N HP` (già esistente).
- **Multiclass:** backend alza solo `experience_points`; banner "livello disponibile" (già esistente) appare; utente assegna livello classe da pagina `/classes` (Gruppo G aggiungerà modale).

**UI:**
- Posizionato in sezione dedicata sopra la griglia quick-XP.
- Bottone full-width, variant `primary`, gradient gold, icona `ChevronsUp` (lucide-react).
- Label: `t('character.xp.level_up_cta')` = "SALI DI LIVELLO" (IT) / "LEVEL UP" (EN).
- Haptic medium su click.
- `aria-label` usa `t('character.xp.level_up_to', { level: level + 1 })`.
- Disabled durante `mutation.isPending`.

### 3.2 Quick-XP buttons proporzionali

**Formula (`PCTS = [0.02, 0.07, 0.20, 0.50]`):**

```ts
const PCTS = [0.02, 0.07, 0.20, 0.50] as const
const MIN_AMOUNT = 5

export function quickXpAmounts(xpToNext: number): number[] {
  const raw = PCTS.map(p => Math.max(MIN_AMOUNT, Math.round(p * xpToNext / 10) * 10))
  return raw.filter((v, i) => i === 0 || v !== raw[i - 1])
}
```

**Regole:**
- Percentuali fisse di `xpToNext` = `XP_THRESHOLDS[level] - xp`.
- Arrotondamento a multipli di 10 (`Math.round(x/10)*10`).
- Floor minimo `MIN_AMOUNT = 5` XP per bottone (evita valori nulli a xpToNext piccoli).
- Dedupe adiacenti dopo rounding (se due percentuali collassano allo stesso valore dopo round/floor, ne resta uno solo).

**Esempi:**

| Liv | xpToNext | Raw (2/7/20/50%) | Output |
|-----|----------|------------------|--------|
| 1 | 300 | 6, 21, 60, 150 | `[10, 20, 60, 150]` |
| 3 | 2700 | 54, 189, 540, 1350 | `[50, 190, 540, 1350]` |
| 5 | 9000 (14000-5000) | 180, 630, 1800, 4500 | `[180, 630, 1800, 4500]` |
| 19 | 50 (355000-354950) | 1→5, 3.5→5, 10, 30 | `[5, 10, 30]` |

**Visibilità:** mostra se `level < 20`, nascondi a `level === 20`.

**Layout:** grid con `grid-cols-${amounts.length}` (4 → `grid-cols-4`, 3 → `grid-cols-3`, etc.). Styling bottoni invariato (`min-h-[48px]`, border gold, font-mono).

**Click:** `mutation.mutate({ add: n })` — invariato rispetto all'attuale comportamento.

### 3.3 Helper location

`quickXpAmounts` estratta in `webapp/src/lib/xpThresholds.ts` (già ospita le soglie + `levelFromXp`). Rende facile sostituire o testare la formula senza toccare la pagina.

### 3.4 Layout finale Experience.tsx

Ordine renderizzato:

```
1. Banner "livello disponibile"    (invariato, solo multiclass con level > totalClassLevel)
2. Testo "single_class_synced"     (invariato, solo single-class)
3. Surface hero: level N + XP + progress bar  (invariato)
4. Surface mode toggle add/set     (invariato)
5. Surface input numerico + ✓      (invariato)
6. Bottone LEVEL UP full-width     (NUOVO, solo level < 20)
7. Grid quick-XP buttons dinamici  (MODIFICATO, solo level < 20)
```

### 3.5 Edge cases

- **Mutation pending:** LEVEL UP + quick-XP buttons disabled per evitare double-submit.
- **XP già al threshold:** click LEVEL UP → set XP = threshold = no-op lato backend (SET con stesso valore). Accettabile; scenario raro.
- **`xpToNext` ≤ 0 (teorico):** `level` è già avanzato, `XP_THRESHOLDS[level]` punta al threshold successivo. Formula sicura.
- **Liv 20:** nascondi LEVEL UP + quick-XP. Banner "MAX" già presente nella progress bar della hero section (già gestito da codice esistente). Input manuale resta disponibile.
- **`hp_gained` toast:** già gestito dal mutation handler. Compare automaticamente dopo click LEVEL UP per single-class.

## 4. i18n keys

**`webapp/src/locales/it.json`** (sotto `character.xp`):
```json
"level_up_cta": "SALI DI LIVELLO",
"level_up_to": "Porta al livello {{level}}"
```

**`webapp/src/locales/en.json`:**
```json
"level_up_cta": "LEVEL UP",
"level_up_to": "Jump to level {{level}}"
```

## 5. Testing (verifica manuale)

Nessun test automatizzato nel progetto (CLAUDE.md: "No test suite or linter is configured"). Checklist:

1. Liv 1 (single-class), XP=0 → quick buttons `[10, 20, 60, 150]`, LEVEL UP visibile.
2. Click LEVEL UP da liv 1 single-class → XP=300, class level = 2, toast `+N HP`.
3. Click bottone `+540` a liv 3 (XP=0) → XP=540, liv ancora 3 (no level-up).
4. Liv 20 → LEVEL UP e quick-XP nascosti; banner "MAX" visibile nella hero.
5. Multiclass liv 3 (Chierico 2 / Guerriero 1, XP=0) → click LEVEL UP → XP=2700, banner "livello disponibile" appare, classi invariate.
6. Edge case liv 19 XP=354950 (xpToNext=50) → 3 bottoni `[5, 10, 30]`.

## 6. Dipendenze e impatti

- **Non rompe:** `HeroXPBar` continua a navigare a `/xp` quando `xpLevel > totalClassLevel` (solo multiclass — per single-class l'auto-sync impedisce lo stato).
- **Non duplica:** il bottone LEVEL UP nella hero bar (Gruppo A) rimane per scorciatoia da altre pagine; il nuovo bottone in `/xp` è la CTA primaria dentro la pagina XP.
- **Coerente con Gruppo B:** auto-HP toast già innescato da PATCH `/xp` su single-class level-up.

## 7. File toccati

| File | Cambio |
|------|--------|
| `webapp/src/pages/Experience.tsx` | Rimuovo `quickAmounts` fisso, aggiungo sezione LEVEL UP + grid dinamica. |
| `webapp/src/lib/xpThresholds.ts` | Aggiungo `quickXpAmounts(xpToNext)`. |
| `webapp/src/locales/it.json` | +2 chiavi sotto `character.xp`. |
| `webapp/src/locales/en.json` | +2 chiavi sotto `character.xp`. |
| `docs/app/` | Rebuild via `npm run build:prod` prima del commit finale. |

## 8. Roadmap update (post-merge)

- Gruppo F: ⬜ → ✅ (PR #TBD).
- Nessun impatto su C/D/E/H. Gruppo G estenderà il flow LEVEL UP con modale multiclass.
