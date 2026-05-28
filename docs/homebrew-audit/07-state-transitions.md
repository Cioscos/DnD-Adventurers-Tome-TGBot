# Audit Homebrew Engine — 07-state-transitions
Generato: 2026-05-28

## 🟢

### #1 — D-branch: integra weapon transitions to danneggiata
**Area:** `07-state-transitions.md`  
**Evento:** damage_state integra→danneggiata (D-branch else)  
**Sintomo:** OK  

### #2 — D-branch: danneggiata weapon transitions to distrutta and is unequipped
**Area:** `07-state-transitions.md`  
**Evento:** damage_state danneggiata→distrutta (D-branch then)  
**Sintomo:** OK  

### #3 — X-branch: integra weapon is immediately destroyed and unequipped
**Area:** `07-state-transitions.md`  
**Evento:** damage_state integra→distrutta (X-branch unconditional)  
**Sintomo:** OK  

### #4 — X-branch: distrutta weapon remains distrutta (terminal state is idempotent)
**Area:** `07-state-transitions.md`  
**Evento:** damage_state distrutta→distrutta (terminal idempotent)  
**Sintomo:** OK  

### #5 — bleeding: HP is floored at 0, never goes negative
**Area:** `07-state-transitions.md`  
**Evento:** bleeding HP cap at 0 (no negative HP)  
**Sintomo:** OK  
