import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import i18n from '@/i18n'
import CasterStats from '@/pages/spells/CasterStats'

describe('CasterStats', () => {
  it('renders nothing for no casters', () => {
    const { container } = render(<CasterStats casters={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders one row per caster with translated class and ability', async () => {
    await i18n.changeLanguage('it')
    render(
      <CasterStats
        casters={[
          { class_id: 1, class_name: 'wizard', ability: 'intelligence', save_dc: 15, attack_bonus: 7 },
          { class_id: 2, class_name: 'Chierico', ability: 'wisdom', save_dc: 12, attack_bonus: -1 },
        ]}
      />,
    )
    expect(screen.getByText('Mago · INT · CD 15 · +7')).toBeInTheDocument()
    expect(screen.getByText('Chierico · SAG · CD 12 · -1')).toBeInTheDocument()
  })
})
