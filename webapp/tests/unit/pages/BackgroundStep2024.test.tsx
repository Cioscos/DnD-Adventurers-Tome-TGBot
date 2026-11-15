import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BackgroundStep2024 from '@/pages/creation/BackgroundStep2024'
import { background24Payload, background24Valid, type Background2024Choice } from '@/lib/species'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

let last: Background2024Choice | null = null
function Harness() {
  const [v, setV] = useState<Background2024Choice | null>(null)
  last = v
  return <BackgroundStep2024 value={v} onChange={setV} />
}

const user = userEvent.setup()
async function pick(name: string) {
  render(<Harness />)
  await user.click(screen.getByRole('button', { name: /character.create.background_pick/ }))
  await user.click(await screen.findByText(name))
}
const inc = (ability: string, label: string) =>
  user.click(within(screen.getByRole('group', { name: `common.abilities.${ability}` })).getByRole('button', { name: label }))

describe('BackgroundStep2024', () => {
  it('mostra talento d\'Origine e abilità; +1/+1/+1 di partenza è valido', async () => {
    await pick('Accolito')
    expect(screen.getByText('Iniziato alla magia')).toBeTruthy()
    expect(screen.getByText(/character.skills.insight/)).toBeTruthy()
    expect(background24Valid(last)).toBe(true)
    expect(background24Payload(last!)).toEqual({
      key: 'acolyte', increases: { intelligence: 1, wisdom: 1, charisma: 1 }, equipment: 'pack',
    })
  })

  it('+2 e +2 non sono accettati, +2/+1 sì', async () => {
    await pick('Accolito')
    await inc('intelligence', '+2')
    await inc('wisdom', '+2')
    expect(background24Valid(last)).toBe(false)
    expect(screen.getByText('character.create.bg_increases_invalid')).toBeTruthy()
    await inc('charisma', '0')
    await inc('wisdom', '+1')
    expect(background24Valid(last)).toBe(true)
    expect(background24Payload(last!).increases).toEqual({ intelligence: 2, wisdom: 1 })
  })

  it('strumento a scelta obbligatorio; 50 mo al posto del pacchetto', async () => {
    await pick('Artigiano')
    expect(background24Valid(last)).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Scorte da alchimista' }))
    await user.click(screen.getByRole('button', { name: 'character.create.bg_gold' }))
    expect(background24Valid(last)).toBe(true)
    expect(background24Payload(last!)).toMatchObject({ key: 'artisan', tool: 'alchemists_supplies', equipment: 'gold' })
  })
})
