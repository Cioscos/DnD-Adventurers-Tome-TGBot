# Homebrew Engine Audit Suite

Questa directory contiene l'output auto-generato della suite di audit Playwright per il motore homebrew (in formato `/audit-loop`-compatible). Gli audit vengono eseguiti in CI e localmente per verificare la copertura e la correttezza del DSL e del motore di regole.

## Come rigenerare

Assicurati che l'API sia in esecuzione (di default su `http://127.0.0.1:8000`), quindi da `webapp/`:

```bash
npm run test:homebrew:audit
```

Per usare un URL API diverso, imposta la variabile d'ambiente:

```bash
HB_API_URL=http://127.0.0.1:8001 npm run test:homebrew:audit
```

## Report per area

| Report | Descrizione |
|--------|-------------|
| `known-issues.md` | Roll-up 🔴/🟠 (input per `/audit-loop`); generato a ogni run con il conteggio totale di severity |
| `01-event-coverage.md` | Copertura dei 15 eventi del motore homebrew (trigger di regole) |
| `02-action-coverage.md` | Copertura dei 16 operatori del DSL homebrew (assegnamenti di azioni) |
| `03-templates.md` | Copertura dei 4 template predefiniti (Qualità & Usura, Sanguinamento, Arma incantata, Punti Fortuna) |
| `04-passive-modifiers.md` | Modificatori passivi per AC, HP max, Speed, Skill bonus, Save bonus |
| `05-filters.md` | Copertura degli 8 operatori filtro (eq, gt, gte, lt, lte, contains, startsWith, exists) |
| `06-error-cases.md` | Casi d'errore e edge case (DSL malformato, regola disabilitata, no-match, cycle detection, 404) |
| `07-state-transitions.md` | Transizioni di stato corrette (Q&U damage_state, capping HP in Sanguinamento, ecc.) |

## Severità

- **🔴 BUG FUNZIONALI** — difetto che viola la semantica del motore; blocca il merge
- **🟠 REGRESSIONI VISIVE** — problema di display o UX; blocca il merge
- **🟡 NIT/UX** — suggerimento di miglioramento; non blocca
- **🟢 PASS** — test passato; non registrato in known-issues.md

Lo stato goal è **0 findings critici** (🔴 + 🟠 = 0). L'exit gate della suite di test blocca il merge se `getCriticalCount() > 0`.
