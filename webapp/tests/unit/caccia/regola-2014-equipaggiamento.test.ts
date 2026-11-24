import it_ from '@/locales/it.json'
import { describe, expect, it } from 'vitest'
import { equipmentToForm, loadCatalog, type EquipmentEntry } from '@/lib/srd/catalog'

const etichette = { range: it_.character.inventory.range_label, thrown: it_.character.inventory.thrown_range_label }

describe('caccia: regola 2014 equipaggiamento', () => {
  // caccia: {"id": "CB-3166", "fonte": "2014 · Equipaggiamento · Armi (Cerbottana: 1 danno perforante, nessun dado) · pag. 149", "zona": "regola:2014/equipaggiamento", "voce": "regola", "copre": ["carta:2014/equipment.md#Armi / Weapons (pag. 149)", "route:/char/:id/inventory"]}
  it.fails('la cerbottana del catalogo infligge 1 danno fisso, che un critico non raddoppia', async () => {
    const cerbottana = (await loadCatalog('equipment')).find((e) => e.index === 'blowgun') as EquipmentEntry
    const form = equipmentToForm(cerbottana, 'it', 'metric', etichette)
    // «1d1» è un dado: al critico si tira due volte e il danno diventa 2; il server accetta già il fisso «1»
    expect(form.damage_dice).toBe('1')
  })
})
