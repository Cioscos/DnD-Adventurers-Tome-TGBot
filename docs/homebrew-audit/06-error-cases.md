# Audit Homebrew Engine — 06-error-cases
Generato: 2026-05-28

## 🟢

### #1 — malformed DSL (no triggers, no passive_modifiers) returns 422
**Area:** `06-error-cases.md`  
**Evento:** malformed-dsl-422  
**Sintomo:** OK  

### #2 — disabled rule does not fire on matching event
**Area:** `06-error-cases.md`  
**Evento:** disabled-rule-no-fire  
**Sintomo:** OK  

### #3 — rule on long_rest_taken does not fire on short rest
**Area:** `06-error-cases.md`  
**Evento:** wrong-event-no-fire  
**Sintomo:** OK  

### #4 — filter with no-match condition prevents rule from firing on manual trigger
**Area:** `06-error-cases.md`  
**Evento:** filter-no-match  
**Sintomo:** OK  

### #5 — cycle detection prevents a damage_taken rule from re-triggering itself indefinitely
**Area:** `06-error-cases.md`  
**Evento:** cycle-detection  
**Sintomo:** OK  

### #6 — item-subject rule with weapon filter does not fire when only a shield exists
**Area:** `06-error-cases.md`  
**Evento:** subject-filter-mismatch  
**Sintomo:** OK  

### #7 — item-subject rule fires gracefully with no notification when no items exist
**Area:** `06-error-cases.md`  
**Evento:** missing-subject-graceful-skip  
**Sintomo:** OK  

### #8 — two enabled rules on long_rest_taken both accumulate in homebrew_notifications
**Area:** `06-error-cases.md`  
**Evento:** multiple-rules-accumulate  
**Sintomo:** OK  

### #9 — PATCH homebrew resource with nonexistent id returns 404
**Area:** `06-error-cases.md`  
**Evento:** resource-not-found-404  
**Sintomo:** OK  
