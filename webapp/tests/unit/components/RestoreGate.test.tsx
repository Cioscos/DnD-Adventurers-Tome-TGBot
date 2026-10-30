import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { IsRestoringProvider } from '@tanstack/react-query'
import RestoreGate from '@/components/RestoreGate'

describe('RestoreGate', () => {
  it('renders nothing while the cache is being restored', () => {
    render(<IsRestoringProvider value={true}><RestoreGate><p>app</p></RestoreGate></IsRestoringProvider>)
    expect(screen.queryByText('app')).not.toBeInTheDocument()
  })

  it('renders the app once restored', () => {
    render(<IsRestoringProvider value={false}><RestoreGate><p>app</p></RestoreGate></IsRestoringProvider>)
    expect(screen.getByText('app')).toBeInTheDocument()
  })
})
