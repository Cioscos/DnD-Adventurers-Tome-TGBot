# Coverage map — inventario e Coverage Ledger

Questo file serve al **Passo 1**: derivare l'inventario completo dalla sorgente e costruire il *Coverage
Ledger*, l'artefatto che garantisce che nessuna interfaccia o endpoint venga dimenticato.

## Perché derivare dalla sorgente (e non fidarsi del seed)

Le liste statiche invecchiano. CLAUDE.md dichiara "No test suite is configured" mentre nel repo esistono
`tests/` (pytest) e `webapp/tests/e2e-playwright/homebrew/`: drift reale. Per questo l'inventario va
**ricavato ogni volta dal codice**; il seed qui sotto è solo un riferimento per rilevare il drift, non la
verità.

## Procedura di derivazione

1. **Route FE** — estrai ogni route da `webapp/src/App.tsx`:
   ```bash
   grep -nE 'path="' webapp/src/App.tsx
   ```
   Includi le sottorotte (`/char/:id/homebrew/new`, `/:ruleId`) e `/session/*`. Ignora la catch-all `*`.
2. **Superficie API** — estrai ogni namespace e metodo da `webapp/src/api/client.ts`:
   ```bash
   grep -nE '^  [a-zA-Z]+: \{' webapp/src/api/client.ts          # namespace
   # poi, dentro ogni namespace, le funzioni: async name(...) / name(...)
   ```
3. **Cross-check documentazione** — confronta con le 23 aree di `docs/webapp-audit/00-index.md`.
4. **Rileva drift** rispetto al seed sotto: voci nuove nel codice → aggiungi al ledger + segnala; voci nel
   seed assenti dal codice → segnala rimozione.

## Seed — Route (26, da App.tsx)

| Route | Componente | Area ledger |
|-------|-----------|-------------|
| `/` | `CharacterSelect` | character-list |
| `/char/:id` | `CharacterMain` | character-main (carousel: HeroScreen / EquipmentScreen / MenuScreen) |
| `/char/:id/hp` | `HP` | hp |
| `/char/:id/ac` | `ArmorClass` | ac |
| `/char/:id/stats` | `AbilityScores` | stats |
| `/char/:id/skills` | `Skills` | skills |
| `/char/:id/saves` | `SavingThrows` | saves |
| `/char/:id/spells` | `Spells` | spells |
| `/char/:id/slots` | `SpellSlots` | slots |
| `/char/:id/inventory` | `Inventory` | inventory |
| `/char/:id/currency` | `Currency` | currency |
| `/char/:id/abilities` | `Abilities` | abilities |
| `/char/:id/class` | `Multiclass` | class |
| `/char/:id/xp` | `Experience` | xp |
| `/char/:id/conditions` | `Conditions` | conditions |
| `/char/:id/history` | `History` | history |
| `/char/:id/notes` | `Notes` | notes |
| `/char/:id/maps` | `Maps` | maps |
| `/char/:id/dice` | `Dice` | dice |
| `/char/:id/identity` | `Identity` | identity |
| `/char/:id/settings` | `Settings` | settings |
| `/char/:id/homebrew` | `Homebrew` | homebrew |
| `/char/:id/homebrew/new` | `RuleEditor` | homebrew-editor |
| `/char/:id/homebrew/:ruleId` | `RuleEditor` | homebrew-editor |
| `/session` | `Session` | session |
| `/session/join` | `SessionJoin` | session |
| `/session/:id` | `SessionRoom` | session |

> La route `character-create` non ha un path proprio: è un wizard inline in `CharacterSelect`. Trattala
> come area a sé nel ledger (è la fixture: va testata per prima quando lo scope è completo).

## Seed — Superficie API (14 namespace, da client.ts)

Ogni metodo è una riga del ledger. Elenco non esaustivo dei metodi principali — **ri-deriva** la lista
esatta da `client.ts` (i metodi possono essere aggiunti/rimossi):

| Namespace | Metodi (verifica in client.ts) | Area/e collegata/e |
|-----------|-------------------------------|--------------------|
| `characters` | list, get, create, update, delete, updateHp, rest, updateDeathSaves, rollDeathSave, spendHitDice, updateAbilityScore, updateAC, resetACOverride, updateSkills, updateSavingThrows, updateConditions, updateInspiration, updateXP, rollSkill, rollSavingThrow, recalcHp | character-list, character-create, hp, ac, stats, skills, saves, conditions, xp |
| `classes` | add, update, remove, distribute, addResource, updateResource, deleteResource | class |
| `spells` | list, add, update, remove, use, updateConcentration, concentrationSave, rollDamage | spells |
| `spellSlots` | add, update, remove, resetAll | slots |
| `items` | list, add, update, remove, attack | inventory |
| `currency` | get, update, convert | currency |
| `abilities` | list, add, update, remove | abilities |
| `homebrew` | listRules, getRule, createRule, updateRule, deleteRule, toggleEnabled, listTemplates, getTemplate, installTemplate, listResources, patchResource, turnStart, manualTrigger | homebrew, homebrew-editor |
| `notes` | list, add, update, remove, uploadVoice, voiceUrl | notes |
| `maps` | list, fileUrl, remove, removeZone, upload, uploadWithProgress, reorder | maps |
| `dice` | result, history, clearHistory, postToChat | dice |
| `history` | get, clear, retentionPreview | history |
| `sessions` | me, create, join, get, live, leave, close, messages, sendMessage, getParticipantIdentity, getFeed, grantItem | session |

> **Endpoint orfani**: se in `client.ts` esiste un metodo che nessuna pagina chiama, segnalalo (potrebbe
> essere superficie morta o una funzionalità senza UI). Viceversa, se una pagina chiama un endpoint non
> presente nel seed, aggiorna il seed e segnala il drift.

## Template del Coverage Ledger (`coverage.md`)

Scrivi questo file nella cartella di sessione. Riempilo al Passo 1 (tutto `pending`) e aggiornalo durante
il Passo 4. A fine run **non deve restare alcuna riga `pending`**.

```markdown
# Coverage Ledger — <scope> — <YYYY-MM-DD HH:MM>

Stati: `pending` (da fare) · `tested` (verificato funzionalmente) ·
`excluded-by-scope` (fuori scope, con motivo) · `blocked` (impossibile testare, con motivo).

## Route
| Route | Area | Stato | Note |
|-------|------|-------|------|
| `/char/:id/hp` | hp | tested | death saves, rest, hit dice, concentrazione |
| `/session/:id` | session | excluded-by-scope | richiede 2 utenti; escluso dall'utente |
| ... | ... | pending | |

## Endpoint API
| Namespace.metodo | Metodo+path | Area | Stato | Note |
|------------------|-------------|------|-------|------|
| characters.rollDeathSave | POST /characters/{id}/death_saves/roll | hp | tested | nat20/nat1/10+ coperti |
| ... | ... | ... | pending | |

## Riepilogo
- Route: tested N / pending N / excluded N / blocked N
- Endpoint: tested N / pending N / excluded N / blocked N
```

Il ledger è la **prova anti-skip**: il riepilogo del report cita questi conteggi. Se a fine run resta
qualcosa `pending`, la skill non è conclusa — torna al Passo 4 oppure spiega nel report perché è `blocked`.
