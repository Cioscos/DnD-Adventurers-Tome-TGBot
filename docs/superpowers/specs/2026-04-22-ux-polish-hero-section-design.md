# UX Polish — Hero Section & Pagine Correlate

**Data:** 2026-04-22
**Branch:** `feat/ux-polish-hero-section`
**Fonte:** `istruzioni.md` — §5 integrale + §1.1 (solo XP bar)
**Gruppo:** A (della decomposizione di `istruzioni.md` in 8 sottoprogetti)

## Obiettivo

Rifinire l'hero section del character sheet e due pagine figlie (`/conditions`, `/ac`) per:
1. Ridurre la densità testuale dei chip (condizioni → icon-only; velocità → icon-only con reveal al tap).
2. Trasformare l'XP da pill numerica a barra progressiva con level-up button inline quando disponibile.
3. Rendere cliccabili le celle caratteristiche nell'hero (scorciatoia verso `/stats`) e la navigazione breadcrumb nell'header delle pagine figlie.
4. Mostrare tutte e 6 le descrizioni dei livelli di spossatezza inline in `/conditions`, con la corrente evidenziata.
5. Ridisegnare il layout della pagina `/ac`: Base full-width + Scudo/Magia affiancati in due colonne.

Non introduce nuove feature di gameplay. Nessun cambio a backend, API o DB. È puramente UX/visual polish del webapp.

## Scope

### In scope

- `webapp/src/components/ui/StatPill.tsx` — estensione con prop `iconOnly` e `revealOnTap`.
- `webapp/src/components/ui/HeroXPBar.tsx` (nuovo) — barra progressiva con level-up button inline.
- `webapp/src/pages/abilities/PassiveAbilityDetailModal.tsx` (nuovo) — modale descrizione abilità passiva.
- `webapp/src/lib/xpThresholds.ts` (nuovo) — estrazione di `XP_THRESHOLDS` da `Experience.tsx` per riuso.
- `webapp/src/lib/conditions.ts` — aggiunta mappa `CONDITION_ICONS` (estratta da `Conditions.tsx`), condivisa fra hero e `/conditions`.
- `webapp/src/pages/CharacterMain.tsx` — riorganizzazione hero card (XP bar, velocità bottom-right, condizioni icon-only, abilità passive cliccabili, celle caratteristiche cliccabili).
- `webapp/src/components/Layout.tsx` — prev/next della breadcrumb row diventano `<button>` cliccabili.
- `webapp/src/pages/Conditions.tsx` — descrizioni dei 6 livelli di spossatezza renderizzate inline sotto il selettore.
- `webapp/src/pages/ArmorClass.tsx` — nuovo layout degli editor: Base full-width, Scudo+Magia affiancati.
- `webapp/src/locales/it.json` e `en.json` — chiavi nuove per XP bar, modale abilità, navigazione layout.

### Out of scope

- Flow di level-up vero e proprio (cosa succede quando clicchi LEVEL UP oltre la semplice navigazione a `/xp`): §1.8 / Gruppo F.
- Calcolo automatico HP al creation/level-up, modificatori absolute/relative in inventario, dadi danno incantesimi, fix click spell slot: §1.1/§1.2 / Gruppo B.
- Rework concentrazione: §1.4/§1.5 / Gruppo C.
- Widget dadi overlay: §1.3 / Gruppo D.
- Privacy identità: §1.7/§4 / Gruppo E.
- Multiclasse: §2 / Gruppo G.
- Chat/cronologia integrata: §3 / Gruppo H.
- Nessun cambio al `ShieldEmblem` CA dell'hero (resta numero singolo dentro lo scudo dorato).
- Nessun cambio al banner di concentrazione.
- Nessun nuovo endpoint API, nessuna migrazione DB.

## Design

### 1. Componenti

#### 1.1 `StatPill` — estensione

File: `webapp/src/components/ui/StatPill.tsx`.

Nuovi prop:
- `iconOnly?: boolean` — quando `true`, nasconde `label` e `value`, mostra solo `icon` dentro il chip.
- `revealOnTap?: boolean` — quando `true` insieme a `iconOnly`, il tap mostra `value` inline per ~2000ms tramite `useState` + `setTimeout`; dopo torna allo stato icon-only. Se tappato mentre è già revealed, il timer si resetta.

Comportamento `onClick` esistente invariato. `revealOnTap` e `onClick` sono ortogonali: se passati entrambi, al tap si rivela il value E si invoca `onClick`. Nel Gruppo A sono sempre esclusivi, quindi il caso combinato non è usato.

A11y: quando `iconOnly`, il componente renderizza come `<button>` (anche senza `onClick`) con `aria-label={String(value)}` così gli screen reader annunciano il nome della risorsa. Se `value` non è stringa e non è stato passato un label esplicito, va passata una stringa esplicita tramite prop `aria-label` (da aggiungere).

Il reveal usa la transizione di framer-motion esistente; width animato, niente portal, niente overlay.

#### 1.2 `HeroXPBar` (nuovo)

File: `webapp/src/components/ui/HeroXPBar.tsx`.

Props: `{ currentXP: number, level: number, nextLevelThreshold: number | null, onLevelUpReady: () => void, className?: string }`.

Render:
- Riga label superiore:
  - Sinistra: `★ LIV {level}` in oro (usa `t('character.xp.bar.level_label', { level })`).
  - Destra: se `nextLevelThreshold !== null && currentXP >= nextLevelThreshold` → `<button>` con testo `t('character.xp.bar.level_up')` (shimmer animation via classe Tailwind esistente `animate-shimmer`, gradiente oro chiaro, corner rounding `md`). `onClick={onLevelUpReady}` + `haptic.medium()`. Altrimenti: `<span>` mono con `t('character.xp.bar.progress', { current: currentXP, threshold: nextLevelThreshold })` (usando `.toLocaleString()` lato formatter).
  - Se `nextLevelThreshold === null` (liv 20): mostra `MAX` in grigio.
- Barra progresso:
  - `height: 6px`, background `#2a2a2a` (usa var CSS esistente), rounded-full.
  - Foreground: gradiente `from-dnd-gold-deep to-dnd-gold-bright`, width `min(100, (currentXP / nextLevelThreshold) * 100)%`. Se `threshold === null`: width 100% stile "MAX".
  - Stato level-up-ready: width 100%, glow intensificato (`box-shadow: 0 0 8px var(--dnd-gold-glow)`).
- A11y: wrapper con `role="progressbar"`, `aria-valuemin={0}`, `aria-valuemax={nextLevelThreshold ?? currentXP}`, `aria-valuenow={currentXP}`, `aria-label`.

#### 1.3 `PassiveAbilityDetailModal` (nuovo)

File: `webapp/src/pages/abilities/PassiveAbilityDetailModal.tsx`.

Props: `{ ability: Ability, onClose: () => void }`.

Ricalca il pattern di `ConditionDetailModal.tsx`: stesso `ModalProvider`, stesso overlay, stessa animazione enter/exit. Corpo:
- Titolo: `ability.name` (font-display, oro).
- Corpo: `ability.description` se presente, altrimenti `<p className="italic text-dnd-text-faint">{t('character.abilities.detail.no_description')}</p>`.
- Nessun campo editabile. Solo visualizzazione.

Tipo `Ability` importato dai type esistenti del client.

#### 1.4 `xpThresholds.ts` (nuovo)

File: `webapp/src/lib/xpThresholds.ts`.

Esporta:
- `XP_THRESHOLDS: readonly number[]` — array di 21 elementi (indice 0 non usato, 1-20 soglie D&D 5e come attualmente in `Experience.tsx`).
- `getXPThresholdForLevel(level: number): number | null` — ritorna `XP_THRESHOLDS[level]` se level 1-19, `null` per level >= 20.
- `getNextLevelThreshold(currentLevel: number): number | null` — wrapper di comodo.

`Experience.tsx` viene aggiornato per importare da qui invece di avere l'array hardcoded locale.

#### 1.5 `lib/conditions.ts` — estensione

File: `webapp/src/lib/conditions.ts` (già esistente, contiene `formatCondition`).

Aggiunta di `CONDITION_ICONS: Record<string, LucideIcon>` con le 14 coppie chiave→icona attualmente dichiarate in `Conditions.tsx`. `Conditions.tsx` viene refactorato per importare da qui. `CharacterMain.tsx` importa la stessa mappa per renderizzare i chip condizione icon-only.

### 2. Hero Section — `CharacterMain.tsx`

Riorganizzazione del `Surface variant="tome"` (righe ~220-327 dell'attuale file).

Ordine finale degli elementi nell'hero card:

1. **Header** (invariato): nome + class_summary + race (colonna sinistra) / `ShieldEmblem` CA (top-right, `absolute`).
2. **HP row** (invariato): `Heart` icon + `current/max` + tempHP, `HPGauge` sotto.
3. **HeroXPBar** (nuovo): sostituisce la meta row XP pill. Level derivato da `char.level` (o equivalente — verificare in implementazione). `onLevelUpReady` → `navigate(\`/char/${charId}/xp\`)`.
4. **Concentration banner** (invariato, condizionale): quando `char.concentrating_spell_id` è set.
5. **Abilità passive chips** (comportamento invariato visivamente, aggiunto onClick): `<StatPill icon={<Zap/>} value={a.name} tone="gold" size="sm" onClick={() => setDetailAbility(a)} />`. Stato locale `useState<Ability|null>(detailAbility)`. Modale `PassiveAbilityDetailModal` renderizzato in coda condizionale.
6. **Condizioni chip icon-only** (riscritte): `<StatPill icon={<ConditionIcon/>} value={formatCondition(key, val, t)} tone="crimson" size="sm" iconOnly onClick={() => setDetailCondKey(key)} />`. Icona da `CONDITION_ICONS[key]`. Stato locale `useState<string|null>(detailCondKey)`. Modale `ConditionDetailModal` (esistente) renderizzato in coda condizionale.
7. **Velocità chip icon-only** (nuovo, floating): `<StatPill icon={<Footprints/>} value={\`${char.speed} ft\`} tone="emerald" size="sm" iconOnly revealOnTap className="absolute bottom-3 right-3" />`. `Surface` ha `position: relative` (confermare in implementazione, l'attuale shield CA è già `absolute right-3 top-3` quindi la Surface ha già `relative`).

**Meta row XP+Speed attuale** (righe 271-285): rimossa completamente.

**Ability scores grid** (righe 329-363): il wrapper `<m.div>` di ogni score diventa `<m.button onClick={() => { haptic.light(); navigate(\`/char/${charId}/stats\`) }}>`. Aggiungo `cursor-pointer` e sottile hover state (border-color gold al hover, lo stile esistente già usa `border bg-gradient-to-b`). `aria-label` costruito da `score.name + value + modifier`.

### 3. Layout — Breadcrumb cliccabile

File: `webapp/src/components/Layout.tsx`.

Nel blocco condizionale `{info && (() => { ... })()}` (righe ~55-84):

- Il `<span>` del **prev** diventa `<m.button onClick={goToPrev} aria-label={t('layout.nav.go_to', { page: t(\`character.menu.${prevKey}\`) })} whileTap={{ scale: 0.95 }}>`. Stile mantiene il `filter: blur(0.5px)` di base, ma al hover `hover:filter-none hover:text-dnd-gold-bright/80` per feedback visivo. `padding` leggermente aumentato per tap target comodo su mobile.
- Il `<span>` del **next** simmetrico a `goToNext`.
- Il `<span>` del **current** resta `<span>` non cliccabile (nessuna azione sensata — siamo già lì).

Handler:
```ts
const goToPrev = () => {
  if (info.index > 0) {
    haptic.light()
    navigate(`/char/${id}/${info.pages[info.index - 1]}`, { replace: true })
  }
}
const goToNext = () => {
  if (info.index < info.total - 1) {
    haptic.light()
    navigate(`/char/${id}/${info.pages[info.index + 1]}`, { replace: true })
  }
}
```

`id` proviene da `useParams<{ id: string }>()` — va aggiunto all'import (Layout.tsx attualmente non usa `useParams`). `navigate` già presente.

Nessuna modifica a `useSwipeNavigation`: lo swipe continua a funzionare parallelamente ai click.

### 4. `Conditions.tsx` — Spossatezza con descrizioni inline

Modifica alla `Surface` exhaustion tracker (righe ~98-141).

Dopo il `<div className="flex gap-1.5">` che rende i 7 bottoni 0-6, aggiungo un nuovo blocco:

```tsx
{(() => {
  const levels = t('character.conditions.desc.exhaustion_levels', { returnObjects: true }) as string[]
  return (
    <div className="mt-4 space-y-1 text-sm">
      {levels.map((desc, idx) => {
        const lvl = idx + 1
        const isCurrent = lvl === currentExhaustion
        return (
          <div
            key={lvl}
            className={
              isCurrent
                ? 'px-3 py-2 rounded-md border-l-2 border-dnd-gold bg-dnd-gold/10 text-dnd-gold-bright'
                : 'px-3 py-1.5 text-dnd-text-faint opacity-60'
            }
          >
            {desc}
          </div>
        )
      })}
    </div>
  )
})()}
```

I testi già includono il prefisso "Livello X:" / "Level X:" (confermato da verifica locale). Li riuso così come sono — niente stripping né aggiunta di label separato.

Comportamento quando `currentExhaustion === 0`: nessun livello evidenziato, tutti e 6 appaiono grigi. Stato chiaro.

### 5. `ArmorClass.tsx` — Nuovo layout editor

Modifica al blocco "Component editors" (righe ~100-125), il `fields.map()` attuale viene sostituito con render esplicito:

```tsx
{/* Base full-width */}
<m.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring.drift, delay: 0.10 }}>
  <Surface variant="elevated">
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">{t('character.ac.base')}</p>
        <p className="text-4xl font-display font-black text-dnd-gold-bright mt-0.5">{char.base_armor_class}</p>
      </div>
      <Input type="number" min={0} value={base} onChange={setBase}
             placeholder={String(char.base_armor_class)} inputMode="numeric"
             className="w-32 [&_input]:text-xl [&_input]:font-display [&_input]:font-bold [&_input]:text-center" />
    </div>
  </Surface>
</m.div>

{/* Scudo + Magia affiancati */}
<m.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
       transition={{ ...spring.drift, delay: 0.15 }}
       className="grid grid-cols-2 gap-2">
  <Surface variant="elevated">
    <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">{t('character.ac.shield')}</p>
    <p className="text-2xl font-display font-black text-dnd-gold-bright mt-0.5">{char.shield_armor_class}</p>
    <Input type="number" min={0} value={shield} onChange={setShield}
           placeholder={String(char.shield_armor_class)} inputMode="numeric"
           className="mt-2 w-full [&_input]:text-base [&_input]:font-display [&_input]:font-bold [&_input]:text-center" />
  </Surface>
  <Surface variant="elevated">
    <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">{t('character.ac.magic')}</p>
    <p className="text-2xl font-display font-black text-dnd-gold-bright mt-0.5">{char.magic_armor}</p>
    <Input type="number" min={0} value={magic} onChange={setMagic}
           placeholder={String(char.magic_armor)} inputMode="numeric"
           className="mt-2 w-full [&_input]:text-base [&_input]:font-display [&_input]:font-bold [&_input]:text-center" />
  </Surface>
</m.div>
```

Il `fields` array va eliminato. `Button Salva` + `mutation` restano identici. L'hero AC (`Surface` con `ShieldEmblem` grande + "base · shield · magic" sotto) resta invariato.

### 6. i18n

Nuove chiavi in `webapp/src/locales/it.json`:

```json
"character": {
  "xp": {
    "bar": {
      "level_label": "LIV {{level}}",
      "progress": "{{current}} / {{threshold}}",
      "level_up": "LEVEL UP",
      "max": "MAX"
    }
  },
  "abilities": {
    "detail": {
      "no_description": "Nessuna descrizione disponibile"
    }
  }
},
"layout": {
  "nav": {
    "go_to": "Vai a {{page}}"
  }
}
```

Chiavi equivalenti in `en.json`:

```json
"character": {
  "xp": {
    "bar": {
      "level_label": "LVL {{level}}",
      "progress": "{{current}} / {{threshold}}",
      "level_up": "LEVEL UP",
      "max": "MAX"
    }
  },
  "abilities": {
    "detail": {
      "no_description": "No description available"
    }
  }
},
"layout": {
  "nav": {
    "go_to": "Go to {{page}}"
  }
}
```

Nessuna chiave nuova per spossatezza (riuso `character.conditions.desc.exhaustion_levels[]`).

### 7. Accessibilità

- `StatPill` con `iconOnly`: render come `<button>`, `aria-label={String(value)}`.
- Breadcrumb prev/next: `aria-label={t('layout.nav.go_to', { page: ... })}`.
- `HeroXPBar`: wrapper `role="progressbar"`, `aria-valuemin/max/now`, `aria-label`.
- Ability score cells: `<button aria-label={\`${score.name}: ${score.value}, mod ${mod >= 0 ? '+' : ''}${mod}\`}>`.
- Tutte le modali nuove: `role="dialog"`, `aria-modal="true"` (pattern esistente in `ConditionDetailModal`).

### 8. Edge cases

- **Level 20**: `nextLevelThreshold = null` → `HeroXPBar` mostra `MAX` invece di numeri, niente pulsante LEVEL UP, barra al 100% statica.
- **XP oltre più soglie**: pulsante LEVEL UP appare lo stesso; il flow vero di level-up (Gruppo F/G) gestirà il multi-level.
- **Velocità 0** (paralizzato / spossatezza liv 5): reveal mostra `0 ft`. Nessun visual cue speciale (fuori scope).
- **Abilità senza description**: modale mostra nome + "Nessuna descrizione disponibile".
- **Conditions array vuoto**: riga non renderizza (invariato).
- **Exhaustion a 0**: tutti i 6 livelli grigi, nessuno evidenziato.
- **Breadcrumb in gruppo di 1 pagina** (`info.total === 1`): `prevKey` e `nextKey` entrambi null → blocco non renderizza (già gestito).
- **Tap reveal sullo stesso chip mentre già revealed**: resetta il timer a 2s.
- **Concentration banner + condizioni attive + abilità passive + velocità**: tutti visibili simultaneamente. L'hero card scrolla se necessario; velocità resta `absolute` in basso a destra.

## Dipendenze con altri gruppi

- Il **pulsante LEVEL UP** in `HeroXPBar` è pronto per essere "potenziato" dal Gruppo F (§1.8): quando Gruppo F definirà il flow vero di level-up, `onLevelUpReady` potrà invocare direttamente una modale o azione invece di navigare a `/xp`. Il design attuale (navigate) è il minimo sensato nel frattempo.
- Il Gruppo G (§2 multiclasse) estenderà ulteriormente il level-up con scelta della classe. Anche in quel caso il punto d'ingresso sarà `onLevelUpReady`.
- `CONDITION_ICONS` estratto in `lib/conditions.ts` sarà riusato anche dal Gruppo H (chat integrata in sessione) se la cronologia deve renderizzare icone per eventi di condizione.

Non introduce dipendenze bloccanti su altri gruppi — si può mergare standalone.

## Implementazione — note operative

- **Build**: ogni modifica al webapp richiede `cd webapp && npm run build:prod` prima del commit finale (rebuilda `docs/app/` per GitHub Pages). Il PR per il merge dovrà contenere sia `webapp/src/**` che `docs/app/**`.
- **Branch**: `feat/ux-polish-hero-section` (già creata).
- **Testing**: nessun test suite. Verifica manuale via `npm run dev` (webapp) + `uv run uvicorn api.main:app --reload` (API), aprendo `http://localhost:5173/` e navigando su un character con HP/XP/condizioni/abilità passive attive. Testare su due character: uno basic (no condizioni, no abilità passive) e uno complesso (concentrazione + condizioni + exhaustion > 0 + vicino a level-up).
- **Regressioni da verificare**: swipe navigation fra sibling pages (Layout), apertura `ConditionDetailModal` dalla pagina `/conditions` (non deve essere rotta dall'estrazione di `CONDITION_ICONS`), build TypeScript (nessun errore di tipo).
- **Commit granularity suggerita** (per facilitare review): un commit per ciascuna sezione del design (componenti nuovi, hero section, breadcrumb, pagine figlie, i18n, rebuild). Dettagli nel piano di implementazione.

## Criteri di successo

- [ ] Hero section rende: HP bar, XP bar sotto HP, concentration banner (condizionale), abilità passive chip (icon+nome), condizioni chip (solo icon), velocità icon floating bottom-right.
- [ ] Tap sulla velocità icon rivela "30 ft" per 2s poi nasconde.
- [ ] Tap su un chip condizione apre `ConditionDetailModal` con la condizione corretta.
- [ ] Tap su un chip abilità passiva apre il nuovo modale con nome e descrizione (o fallback "nessuna descrizione").
- [ ] Tap su una cella caratteristica naviga a `/stats`.
- [ ] `HeroXPBar` mostra barra + LIV + numeri `current/threshold`, sostituito da pulsante LEVEL UP quando XP ≥ soglia.
- [ ] Click sul pulsante LEVEL UP naviga a `/xp`.
- [ ] Breadcrumb prev/next nelle pagine figlie cliccabili, ciascuno naviga alla sibling corrispondente, feedback haptic al tap.
- [ ] `/conditions`: selettore 0-6 invariato, sotto 6 descrizioni inline, corrente evidenziata con bordo/sfondo oro, altre grigio.
- [ ] `/ac`: Base full-width in testa, Scudo + Magia in grid 2 colonne sotto.
- [ ] Tutti i testi via i18n (it + en), nessun hardcoded.
- [ ] Build `npm run build:prod` completa senza errori TypeScript.
- [ ] Swipe navigation + modali esistenti non regrediti.
