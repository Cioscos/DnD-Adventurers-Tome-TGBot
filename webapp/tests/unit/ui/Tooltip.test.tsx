import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Tooltip from '@/components/ui/Tooltip'

describe('Tooltip', () => {
  it('renders its trigger child', () => {
    render(<Tooltip content="info"><button>trigger</button></Tooltip>)
    expect(screen.getByRole('button', { name: 'trigger' })).toBeInTheDocument()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('toggles the tooltip content on click', async () => {
    render(<Tooltip content={<span>spiegazione</span>}><button>trigger</button></Tooltip>)
    await userEvent.click(screen.getByRole('button', { name: 'trigger' }))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    expect(screen.getByText('spiegazione')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'trigger' }))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})
