import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import FilterRow from '@/components/ui/FilterRow'

describe('FilterRow', () => {
  it('renders the dimension label and its chip children', () => {
    render(
      <FilterRow label="Scuola">
        <button>evocazione</button>
        <button>abiurazione</button>
      </FilterRow>,
    )
    expect(screen.getByText('Scuola')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'evocazione' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'abiurazione' })).toBeInTheDocument()
  })
})
