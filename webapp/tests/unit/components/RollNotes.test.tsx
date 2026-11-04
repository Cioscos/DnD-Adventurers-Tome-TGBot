import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import RollNotes from '@/components/rules/RollNotes'
import type { OptionResult } from '@/api/client'

vi.mock('react-i18next', async (orig) => ({
  ...(await orig() as object),
  useTranslation: () => ({ t: (k: string, o?: { total?: number }) => (o?.total ? `${k}:${o.total}` : k), i18n: { language: 'en' } }),
}))
vi.mock('@/hooks/useRollNoteLabels', () => ({ useRollNoteLabels: () => (n: string[]) => n }))

const base: OptionResult = { keys: ['x'], extra_rolls: [], extra_total: 0, bonus: 0, multiplier: 1, spent: [] }

describe('RollNotes', () => {
  it('shows the effect of an option in the player language', () => {
    render(<RollNotes optionResult={{ ...base, effects: [{ it: 'CD 13 in italiano', en: 'DC 13 in english' }] }} />)
    expect(screen.getByText('DC 13 in english')).toBeInTheDocument()
  })

  it('shows the second attack roll next to its damage', () => {
    render(<RollNotes optionResult={{ ...base, second_die: 14, second_total: 19, separate_rolls: [7], separate_total: 7 }} />)
    expect(screen.getByText('character.roll_options.second_attack:19')).toBeInTheDocument()
  })
})
