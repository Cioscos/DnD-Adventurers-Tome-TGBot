import { describe, it, expect } from 'vitest'
import i18n from '@/i18n'
import { classLabel, classSummary } from '@/lib/classLabel'

describe('classLabel', () => {
  it('traduce la chiave canonica e lascia stare i nomi liberi', () => {
    void i18n.changeLanguage('it')
    expect(classLabel(i18n.t, 'barbarian')).toBe('Barbaro')
    expect(classLabel(i18n.t, 'Mago Custom')).toBe('Mago Custom')
  })

  it('riconosce anche i nomi salvati in altra lingua o con la maiuscola', async () => {
    await i18n.changeLanguage('it')
    expect(classLabel(i18n.t, 'Wizard')).toBe('Mago')
    expect(classLabel(i18n.t, 'wizard')).toBe('Mago')
  })

  it('compone il riepilogo con i nomi tradotti', () => {
    void i18n.changeLanguage('it')
    expect(classSummary(i18n.t, [{ class_name: 'wizard', level: 5, subclass: 'Evocazione' }, { class_name: 'Fighter', level: 2 }]))
      .toBe('Mago 5 (Evocazione) / Guerriero 2')
    expect(classSummary(i18n.t, [])).toBe('Nessuna classe')
  })
})
