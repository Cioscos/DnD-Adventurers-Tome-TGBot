# Design — Gruppo E: Privacy identità

**Data:** 2026-04-24
**Stato:** design validato, pronto per plan
**Branch:** `feat/privacy-identity-gruppo-e`
**Sezioni `istruzioni.md` coperte:** §1.7 (Identità) + §4 (parte "click altro player").

---

## 1. Scope

Separare i campi identità del personaggio in **pubblici** (sempre visibili agli altri player in sessione) e **privati** (visibili solo se il proprietario ha attivato l'opzione). Aggiungere:

1. Setting per-character `show_private_identity` (default `false`).
2. Riorganizzazione di `Identity.tsx` in blocchi Public / Private, con `background` spostato nel blocco Private.
3. Nuovo endpoint backend per view identity di un altro player in sessione, che rispetta il setting del target.
4. Sheet bottom-center in `SessionRoom.tsx` che mostra identity di un player cliccato.

### Out of scope

- La privacy già esistente (HP bucket, AC category, conditions redaction, whisper GM↔player) — non toccata.
- Nessuna migrazione DB; il flag usa la chiave JSON `settings` esistente (pattern già usato per `hp_auto_calc`, `spell_slots_mode`).
- Nessuna modifica a `CharacterLiveSnapshot` (evita over-fetch su polling live).

---

## 2. Decisioni chiave

| Tema | Scelta | Motivo |
|---|---|---|
| Default flag | `false` (private hidden) | Privacy-first |
| Accesso GM con flag OFF | GM escluso (niente eccezione) | Istruzioni §1.7 non citano GM-access per identity, scelta più stretta |
| UI view altro player | Bottom-sheet (`Sheet`) | Pattern esistente (Maps, Dice, ecc.), non interrompe flusso sessione |
| Endpoint backend | Dedicato `GET /sessions/{code}/participants/{user_id}/identity` | Separazione pulita da snapshot live, evita over-fetch |
| Owner view | Sempre tutto | Il proprietario non deve combattere con la propria UI |

### Riclassificazione campi identity

- **Public** (sempre visibili agli altri): `name`, `race`, `gender`, `alignment`, `speed`, `languages`, `general_proficiencies`.
- **Private** (visibili solo se `show_private_identity = True`): `background`, `personality.traits`, `personality.ideals`, `personality.bonds`, `personality.flaws`.

`background` semanticamente riclassificato come privato — solo UI/rendering cambia, DB invariato.

---

## 3. Architettura backend

### 3.1 Settings key

Il flag `show_private_identity: bool` entra nella colonna JSON `settings` del `Character`. Assenza → `false`. Nessuna migrazione DB.

### 3.2 Nuovo endpoint

```
GET /sessions/{code}/participants/{user_id}/identity
  Auth: X-Telegram-Init-Data (header) — standard
  Path params:
    code       : invite code della session (6 chars)
    user_id    : telegram user_id del target participant
  Response 200: IdentityView
  Errori:
    404 "Session not found"
    404 "Participant not found" (user_id non è in participants)
    404 "Participant has no character"
    403 non impiegato — basta essere partecipante della stessa session
```

**Logica:**
1. Risolvi `caller_user_id` via `get_current_user`.
2. Trova session attiva via `code`.
3. Verifica che `caller_user_id` sia nei participants.
4. Trova target participant via `user_id`.
5. Leggi target `Character` via `character_id`.
6. Costruisci `IdentityView`:
   - Public fields sempre popolati dal character.
   - Private fields: popolati se `target.settings.show_private_identity is True` **oppure** `caller_user_id == user_id`.
   - `show_private: bool` flag riflette se la response include private.

### 3.3 Schema `IdentityView`

```python
class IdentityView(BaseModel):
    user_id: int
    character_id: int
    # public
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    alignment: Optional[str] = None
    speed: Optional[int] = None
    languages: Optional[str] = None
    general_proficiencies: Optional[str] = None
    # private (None if not shared)
    background: Optional[str] = None
    personality_traits: Optional[str] = None
    ideals: Optional[str] = None
    bonds: Optional[str] = None
    flaws: Optional[str] = None
    show_private: bool = False
```

`personality.*` vengono estratti dal JSON `char.personality` prima di serializzare.

---

## 4. Frontend — pagina Identity (owner-side)

### 4.1 Riorganizzazione

Layout attuale:
- Hero name
- Section Fisicità (race, gender, background, alignment, speed)
- Section Personalità (traits, ideals, bonds, flaws)
- Section Cultura (languages, proficiencies)

Layout nuovo:
- Hero name
- Section Fisicità — **PUBLIC** — race, gender, alignment, speed (background **rimosso da qui**)
- Section Cultura — **PUBLIC** — languages, proficiencies
- Section Personalità — **PRIVATE** — background + traits + ideals + bonds + flaws (con badge visuale "Private")

### 4.2 Badge "Private"

Sul `SectionDivider` del blocco Personalità, aggiungere un piccolo visual hint — icona `Lock` + label i18n `character.identity.private_badge`. Tipo:

```tsx
<SectionDivider
  icon={<Feather size={11} />}
  align="center"
  badge={<span className="flex items-center gap-1 text-dnd-gold-dim text-[10px]">
    <Lock size={10} /> {t('character.identity.private_badge')}
  </span>}
>
  {t('character.identity.personality')}
</SectionDivider>
```

(Se `SectionDivider` non supporta `badge` prop, aggiungere un piccolo helper span inline sotto il divider. L'implementer valuta — il pattern più semplice vince.)

### 4.3 Nessun toggle in-page

Owner vede sempre tutti i campi. Il setting controlla solo il comportamento lato session view.

---

## 5. Frontend — Settings.tsx

Nuova sub-section "Privacy" tra le esistenti (`Preferenze`, `Punti Ferita`):

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
      <p className="text-xs text-dnd-text-muted italic mt-0.5">
        {t('character.settings.privacy.show_private_hint')}
      </p>
    </div>
    <input
      type="checkbox"
      checked={(settings.show_private_identity as boolean | undefined) === true}
      onChange={(e) => updateMutation.mutate({
        ...settings,
        show_private_identity: e.target.checked,
      })}
      className="w-5 h-5"
    />
  </label>
</Surface>
```

Pattern copia del toggle `hp_auto_calc` già presente.

---

## 6. Frontend — SessionRoom + ParticipantIdentitySheet

### 6.1 Modifica `SessionRoom.tsx`

State nuovo:
```tsx
const [identityTarget, setIdentityTarget] = useState<SessionParticipant | null>(null)
```

`ParticipantRow` prop `onOwnClick` viene sostituito da un `onClick` generalizzato:
- Se `isOwn` → navigate a `/char/:id` (come oggi).
- Altrimenti, se `!isGm` → set `identityTarget = participant`.
- Se `isGm` → no-op (non interattivo).

La `Wrapper: any = isOwn ? 'button' : 'div'` diventa `isOwn || (!isGm) ? 'button' : 'div'`.

Monta `ParticipantIdentitySheet`:
```tsx
<ParticipantIdentitySheet
  code={live.code}
  target={identityTarget}
  onClose={() => setIdentityTarget(null)}
/>
```

### 6.2 `ParticipantIdentitySheet.tsx` (nuovo)

```
webapp/src/pages/session/ParticipantIdentitySheet.tsx
```

Firma:
```tsx
interface Props {
  code: string
  target: SessionParticipant | null
  onClose: () => void
}
```

Struttura:
- `Sheet` component, open = `target != null`.
- `useQuery` con key `['session-identity', code, target?.user_id]`, enabled `target != null`, chiamata `api.sessions.getParticipantIdentity(code, target.user_id)`.
- Loading state: skeleton.
- Error state: messaggio + tap-to-close.
- Content:
  - Title: `data.name` (+ eventuale class_summary da snapshot? no, non serve).
  - Section "Fisicità" (Public): race / gender / alignment / speed se valorizzati.
  - Section "Cultura" (Public): languages / general_proficiencies se valorizzati.
  - Section "Personalità" (Private):
    - Se `data.show_private`: background + traits + ideals + bonds + flaws (field per field, omettere se vuoti).
    - Altrimenti: messaggio "Info private nascoste" + icona `EyeOff`.

Tutto read-only — niente `Input`/form, solo `<p>` + `<Surface>`.

### 6.3 API client method

`webapp/src/api/client.ts`:
```ts
sessions: {
  // ...existing methods...
  getParticipantIdentity: (code: string, userId: number) =>
    request<ParticipantIdentity>(
      `/sessions/${encodeURIComponent(code)}/participants/${userId}/identity`
    ),
}
```

### 6.4 TS type

`webapp/src/types/index.ts`:
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

---

## 7. File impattati

### Nuovi
- `webapp/src/pages/session/ParticipantIdentitySheet.tsx` (~150 LOC).

### Modificati
- `api/schemas/session.py` — aggiungere `IdentityView` schema.
- `api/routers/sessions.py` — aggiungere endpoint `GET /sessions/{code}/participants/{user_id}/identity`.
- `webapp/src/pages/Identity.tsx` — riorganizza sezioni, sposta background, aggiungi badge Private.
- `webapp/src/pages/Settings.tsx` — nuova sub-section Privacy.
- `webapp/src/pages/SessionRoom.tsx` — click generalizzato su participant row, monta sheet.
- `webapp/src/api/client.ts` — nuovo method `sessions.getParticipantIdentity`.
- `webapp/src/types/index.ts` — interface `ParticipantIdentity`.
- `webapp/src/locales/it.json` + `en.json` — nuove chiavi (vedi sotto).

### Invariati
- `core/utils/session_view.py`, `CharacterLiveSnapshot`, altre snapshot live.
- DB schema (nessuna migration).
- Bot: il bot non legge identity direttamente.

---

## 8. i18n keys nuove

```json
// webapp/src/locales/it.json (EN mirror in en.json)

"character": {
  "identity": {
    "private_badge": "Info private",
    "private_section_title": "Personalità",
    ...
  },
  "settings": {
    "privacy": {
      "title": "Privacy",
      "show_private_label": "Mostra info private a GM e altri player",
      "show_private_hint": "Se attivo, personalità, ideali, legami, difetti e background saranno visibili durante la sessione di gioco."
    }
  }
}

"session": {
  "identity": {
    "title": "Identità",
    "public_section": "Pubblico",
    "private_section": "Personalità",
    "private_hidden": "Info private nascoste",
    "fisicita": "Fisicità",
    "cultura": "Cultura",
    ...
  }
}
```

---

## 9. Edge cases

1. **Target non in session**: endpoint 404. UI previene il tap per non-partecipanti.
2. **Target senza `character_id`**: endpoint 404 "Participant has no character".
3. **GM row cliccato**: no-op (UI rende `<div>`, non `<button>`).
4. **Own row**: comportamento esistente (navigate a `/char/:id`).
5. **Settings senza chiave** (char pre-feature): default `false`.
6. **Double-toggle**: ultimo write vince (pattern esistente).
7. **Identity fields vuoti**: render omette la riga (no placeholder "—").
8. **Session scaduta mentre sheet aperto**: fetch error → messaggio + tap close.
9. **Unmount durante fetch**: TanStack Query gestisce clean-up.
10. **Stale data**: sheet non fa polling. Re-fetch solo alla riapertura.

---

## 10. Acceptance criteria

- [ ] Setting `show_private_identity` toggleabile da `/char/:id/settings`; default OFF.
- [ ] Identity page ha sezione Personalità (private) con badge visivo; background è lì, non più in Fisicità.
- [ ] Endpoint `GET /sessions/{code}/participants/{user_id}/identity` ritorna public fields sempre; private solo se setting target = ON (o caller == target).
- [ ] SessionRoom: click su altro player non-GM apre bottom-sheet con identity.
- [ ] Sheet mostra "Info private nascoste" se target setting = OFF.
- [ ] Sheet mostra tutti i campi se target setting = ON.
- [ ] GM row non cliccabile.
- [ ] Own row naviga a `/char/:id` come prima.
- [ ] Nessuna regressione su HP/AC/conditions privacy esistenti.

---

## 11. Dipendenze / rischi

- **Nessuna dipendenza bloccante** verso altri gruppi.
- `Sheet` component esiste e supporta readonly content (verificato dal pattern `SpellDamageSheet`).
- `SectionDivider` — verificare support di `badge` prop in impl; fallback a inline span.
- Rischio basso: scope additive, no breaking change API esistente (nuovo endpoint indipendente).
