import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { renderInlineMarkdown } from '@/lib/inlineMarkdown'

describe('renderInlineMarkdown', () => {
  it('renders bold / italic / code as semantic elements', () => {
    render(<div>{renderInlineMarkdown('a **grassetto** b *corsivo* c `codice`')}</div>)
    expect(screen.getByText('grassetto').tagName).toBe('STRONG')
    expect(screen.getByText('corsivo').tagName).toBe('EM')
    expect(screen.getByText('codice').tagName).toBe('CODE')
  })

  it('returns the input untouched when empty', () => {
    expect(renderInlineMarkdown('')).toBe('')
  })

  it('passes plain text through unchanged', () => {
    render(<div data-testid="out">{renderInlineMarkdown('solo testo semplice')}</div>)
    expect(screen.getByTestId('out')).toHaveTextContent('solo testo semplice')
  })
})
