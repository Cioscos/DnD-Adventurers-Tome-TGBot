# Audit Homebrew Engine — 02-action-coverage
Generato: 2026-05-28

## 🟢

### #1 — notify emits a notification with the configured message
**Area:** `02-action-coverage.md`  
**Evento:** notify  
**Sintomo:** OK  

### #2 — add_history writes a homebrew history entry
**Area:** `02-action-coverage.md`  
**Evento:** add_history  
**Sintomo:** OK  

### #3 — roll_dice stores the roll result in a variable accessible to notify
**Area:** `02-action-coverage.md`  
**Evento:** roll_dice  
**Sintomo:** OK  

### #4 — lookup_table resolves a cell value from a DSL table and stores it
**Area:** `02-action-coverage.md`  
**Evento:** lookup_table  
**Sintomo:** OK  

### #5 — match branches into the matching case and executes its effects
**Area:** `02-action-coverage.md`  
**Evento:** match  
**Sintomo:** OK  

### #6 — if evaluates a condition and executes the then branch when true
**Area:** `02-action-coverage.md`  
**Evento:** if  
**Sintomo:** OK  

### #7 — set_property writes hb_<key> into item_metadata on the subject item
**Area:** `02-action-coverage.md`  
**Evento:** set_property  
**Sintomo:** OK  

### #8 — inc_property increments hb_<key> on the subject item by the specified delta
**Area:** `02-action-coverage.md`  
**Evento:** inc_property  
**Sintomo:** OK  

### #9 — unequip clears is_equipped and equipment_slot on the subject item
**Area:** `02-action-coverage.md`  
**Evento:** unequip  
**Sintomo:** OK  

### #10 — damage_character reduces current_hit_points by the specified amount
**Area:** `02-action-coverage.md`  
**Evento:** damage_character  
**Sintomo:** OK  

### #11 — heal_character increases current_hit_points by the specified amount
**Area:** `02-action-coverage.md`  
**Evento:** heal_character  
**Sintomo:** OK  

### #12 — change_resource adjusts the current value of a homebrew resource by delta
**Area:** `02-action-coverage.md`  
**Evento:** change_resource  
**Sintomo:** OK  

### #13 — restore_resource refills the resource to max when amount is 'max'
**Area:** `02-action-coverage.md`  
**Evento:** restore_resource  
**Sintomo:** OK  

### #14 — apply_condition inserts the key into the character conditions dict
**Area:** `02-action-coverage.md`  
**Evento:** apply_condition  
**Sintomo:** OK  

### #15 — remove_condition deletes a previously applied condition key from the character
**Area:** `02-action-coverage.md`  
**Evento:** remove_condition  
**Sintomo:** OK  

### #16 — apply_modifier_once permanently increases hit_points max by the delta
**Area:** `02-action-coverage.md`  
**Evento:** apply_modifier_once  
**Sintomo:** OK  
