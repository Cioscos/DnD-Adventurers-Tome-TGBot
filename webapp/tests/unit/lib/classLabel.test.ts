import { describe, it, expect } from 'vitest'
import i18n from '@/i18n'
import { classLabel } from '@/lib/classLabel'

describe('classLabel', () => {
  it('traduce la chiave canonica e lascia stare i nomi liberi', () => {
    void i18n.changeLanguage('it')
    expect(classLabel(i18n.t, 'barbarian')).toBe('Barbaro')
    expect(classLabel(i18n.t, 'Mago Custom')).toBe('Mago Custom')
  })
})
