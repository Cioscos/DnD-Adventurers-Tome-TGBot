import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LazyMotion, domMax } from 'framer-motion'
import Sheet from '@/components/ui/Sheet'

// Telegram Android: la tastiera rimpicciolisce la WebView ma `vh` non cala e il browser non porta
// in vista il campo attivo dentro lo scroll dello sheet → il campo restava sotto la tastiera (S22).
function renderSheet() {
  render(
    <LazyMotion features={domMax} strict>
      <Sheet open onClose={() => {}} title="Titolo">
        <div data-testid="box" style={{ overflowY: 'auto' }}>
          <input aria-label="importo" />
        </div>
      </Sheet>
    </LazyMotion>,
  )
  const input = screen.getByLabelText('importo')
  const box = screen.getByTestId('box')
  // Campo a y=600 dentro un contenitore centrato a y=200: va scrollato di 400px.
  box.getBoundingClientRect = () => ({ top: 100, height: 200 }) as DOMRect
  input.getBoundingClientRect = () => ({ top: 590, height: 20 }) as DOMRect
  return { input, box }
}
const frame = () => new Promise((r) => requestAnimationFrame(() => r(null)))
const setHeight = (h: number) => Object.defineProperty(window, 'innerHeight', { value: h, configurable: true })

afterEach(() => {
  setHeight(780)
  delete (window as unknown as { Telegram?: unknown }).Telegram
})

describe('Sheet — tastiera su mobile', () => {
  it('l\'altezza massima segue --tg-vh (che cala con la tastiera), non 85vh', () => {
    const { input } = renderSheet()
    const panel = input.closest('.surface-parchment') as HTMLElement
    expect(panel.className).toContain('max-h-[calc(var(--tg-vh,100vh)*0.85)]')
    expect(panel.className).not.toContain('max-h-[85vh]')
  })

  it('quando l\'altezza cala centra il campo attivo scorrendo il suo contenitore', async () => {
    setHeight(780)
    const { input, box } = renderSheet()
    input.focus()
    setHeight(428)
    window.dispatchEvent(new Event('resize'))
    await frame()
    expect(box.scrollTop).toBe(400)
  })

  it('non scorre quando l\'altezza cresce (rotazione, finestra desktop)', async () => {
    setHeight(428)
    const { input, box } = renderSheet()
    input.focus()
    setHeight(780)
    window.dispatchEvent(new Event('resize'))
    await frame()
    expect(box.scrollTop).toBe(0)
  })

  it('riporta in vista il campo quando Telegram stabilizza l\'altezza (viewportChanged), non prima', async () => {
    const handlers: Array<(e?: { isStateStable?: boolean }) => void> = []
    const tg = { onEvent: vi.fn((_: string, cb: () => void) => handlers.push(cb)), offEvent: vi.fn() }
    ;(window as unknown as { Telegram: unknown }).Telegram = { WebApp: tg }
    const { input, box } = renderSheet()
    input.focus()
    handlers.forEach((h) => h({ isStateStable: false }))
    await frame()
    expect(box.scrollTop).toBe(0)
    handlers.forEach((h) => h({ isStateStable: true }))
    await frame()
    expect(box.scrollTop).toBe(400)
  })

  it('non tocca lo scroll se il campo attivo è fuori dallo sheet', async () => {
    setHeight(780)
    const { box } = renderSheet()
    const outside = document.createElement('input')
    document.body.appendChild(outside)
    outside.focus()
    setHeight(428)
    window.dispatchEvent(new Event('resize'))
    await frame()
    expect(box.scrollTop).toBe(0)
    outside.remove()
  })
})
