import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LazyMotion, domMax } from 'framer-motion'
import Sheet from '@/components/ui/Sheet'

// Telegram Android: la tastiera rimpicciolisce la WebView ma `vh` non cala e il browser non porta
// in vista il campo attivo dentro lo scroll dello sheet → il campo restava sotto la tastiera (S22).
function renderSheet() {
  render(
    <LazyMotion features={domMax} strict>
      <Sheet open onClose={() => {}} title="Titolo">
        <input aria-label="importo" />
      </Sheet>
    </LazyMotion>,
  )
  return screen.getByLabelText('importo')
}

describe('Sheet — tastiera su mobile', () => {
  it('l\'altezza massima segue --tg-vh (che cala con la tastiera), non 85vh', () => {
    const input = renderSheet()
    const panel = input.closest('.surface-parchment') as HTMLElement
    expect(panel.className).toContain('max-h-[calc(var(--tg-vh,100vh)*0.85)]')
    expect(panel.className).not.toContain('max-h-[85vh]')
  })

  it('al resize della finestra porta in vista il campo attivo dello sheet', async () => {
    const input = renderSheet()
    const scroll = vi.fn()
    input.scrollIntoView = scroll
    input.focus()
    window.dispatchEvent(new Event('resize'))
    await new Promise((r) => requestAnimationFrame(() => r(null)))
    expect(scroll).toHaveBeenCalledWith({ block: 'center' })
  })

  it('non tocca lo scroll se il campo attivo è fuori dallo sheet', async () => {
    renderSheet()
    const outside = document.createElement('input')
    document.body.appendChild(outside)
    const scroll = vi.fn()
    outside.scrollIntoView = scroll
    outside.focus()
    window.dispatchEvent(new Event('resize'))
    await new Promise((r) => requestAnimationFrame(() => r(null)))
    expect(scroll).not.toHaveBeenCalled()
    outside.remove()
  })
})
