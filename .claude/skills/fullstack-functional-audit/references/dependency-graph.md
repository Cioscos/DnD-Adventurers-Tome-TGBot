# Grafo vivo delle dipendenze funzionali

Serve al **Passo 5/6**. Il grafo è un artefatto **persistente e committato** che cresce a ogni run:
mappa quali azioni su una pagina influenzano i dati letti da un'altra. Serve a due cose:

1. **Guidare i test di regressione cross-page**: per ogni arco `A → B`, dopo aver agito su A vai su B e
   verifica che rifletta il cambio.
2. **Diventare una mappa di impatto riutilizzabile**: un agente che modifica la pagina A può consultare il
   grafo per sapere cosa rischia di rompere.

## Dove vive

- `docs/webapp-audit/dependency-graph.json` — sorgente di verità (machine-readable).
- `docs/webapp-audit/dependency-graph.md` — vista umana, rigenerata dal JSON, con diagramma Mermaid.

Se non esistono, creali dalla **matrice seed** qui sotto al primo run.

## Schema JSON

```json
{
  "generated": "<YYYY-MM-DD>",
  "nodes": [
    { "id": "stats", "route": "/char/:id/stats", "page": "webapp/src/pages/AbilityScores.tsx" }
  ],
  "edges": [
    {
      "from": "stats",
      "to": "hp",
      "trigger": "PATCH /characters/{id}/ability_scores/constitution",
      "field": "hit_points",
      "rule": "delta_con_mod * total_level (stats.py:99)",
      "evidence": "CON 14->16 => HP max 18->20 confermato 2026-05-30",
      "status": "verified"
    }
  ]
}
```

Campi arco: `from`/`to` (id nodo), `trigger` (azione/endpoint che innesca), `field` (campo mutato che il
nodo `to` legge), `rule` (oracolo con `file:riga`), `evidence` (cosa hai osservato + data), `status`
(`verified` se hai confermato la propagazione in questo run, `suspected` se dedotto dal codice ma non
ancora verificato a runtime).

## Regole di merge (idempotente)

A ogni run **non sovrascrivere** il grafo: fai merge.

1. Carica il JSON esistente (se c'è).
2. Per ogni arco scoperto: chiave = `(from, to, field)`. Se esiste → arricchisci `evidence`/`status` e
   aggiorna `rule` se è cambiata; **non duplicare**. Se non esiste → aggiungi.
3. Aggiungi i nodi mancanti.
4. Aggiorna `generated`.
5. Rigenera il `.md` dal JSON (sezione testuale + blocco ```mermaid``` con `graph LR; stats --> hp` ecc.).

Un arco `suspected` (dedotto leggendo il BE) va promosso a `verified` solo dopo aver osservato a runtime
la propagazione sulla pagina `to`.

## Matrice seed — archi noti

Dipendenze già emerse dall'esplorazione del codice. Usa questa matrice sia per seedare il grafo sia per
sapere **quali check cross-page programmare** al Passo 4.5. Tutte partono `suspected` finché non le
verifichi a runtime.

| from | to | trigger | field mutato | oracolo (file:riga) |
|------|----|---------|--------------|--------------------|
| stats | hp | PATCH ability_scores/constitution | hit_points, current_hit_points | stats.py:95-103 |
| inventory | ac | PATCH items/{id} equip armor/shield | base_armor_class, shield_armor_class | items.py:197-208 |
| inventory | hp | PATCH items/{id} equip item CON-modifying | hit_points | items.py + _helpers.py:82 |
| hp(rest long) | slots | POST rest {long} | spell_slots.used → 0 | hp.py:222-246 |
| hp(rest long) | hp | POST rest {long} | current_hit_points, temp_hp, death_saves | hp.py:222-246 |
| hp(rest long) | abilities | POST rest {long} | ability.uses ripristinati (long+short) | hp.py:232-240 |
| hp(rest long) | spells | POST rest {long} | concentrating_spell_id → null | hp.py:228 |
| hp(rest short) | slots | POST rest {short} | pact slots ripristinati | hp.py:248-275 |
| hp(rest short) | abilities | POST rest {short} | ability.uses (short_rest) | hp.py:262-270 |
| hp(damage) | spells | PATCH hp DAMAGE mentre concentra | concentrating_spell_id (su fail) | hp.py:126-131, _helpers.py:146-155 |
| spells(cast) | slots | POST spells/{id}/use | spell_slot.used += 1 | spells.py:149-180 |
| spells(cast) | spells | POST spells/{id}/use (concentration) | concentrating_spell_id | spells.py:178 |
| xp | hp | PATCH xp (level-up mono-classe) | hit_points | characters.py:405-446 |
| xp | slots | PATCH xp (level-up) | spell_slots (recalc auto) | characters.py + spell_slots service |
| xp | class | PATCH xp (level-up) | class.level, resources | characters.py:405-446 |
| class | hp | POST classes (multiclass) | hit_points bootstrap | classes.py |
| class | slots | POST/PATCH classes | spell_slots (recalc) | classes.py + spell_slots service |
| character-create | hp | POST characters {initial_class} | hit_points L1 | characters.py:184-217 |
| character-create | slots | POST characters {initial_class} | spell_slots seed | characters.py:184-217 |
| stats(CON) | abilities | (indiretto) | hit dice / risorse derivate da livello | — verifica se applicabile |
| settings(recalc) | hp | POST hp/recalc | hit_points | hp.py:446 |

> Questa matrice è un punto di partenza, non un tetto. Ogni volta che leggendo un handler BE scopri che
> muta un campo letto altrove, **aggiungi l'arco** — è il modo in cui il grafo diventa davvero completo.
