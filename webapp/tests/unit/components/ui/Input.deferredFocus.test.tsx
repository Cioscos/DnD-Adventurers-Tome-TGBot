import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Input from '@/components/ui/Input'
import { SheetEnteredContext } from '@/components/ui/sheetContext'

// Perf (S22): l'autofocus all'apertura di uno sheet fa salire la tastiera mentre lo
// sheet anima; Android ridimensiona il WebView a ogni frame (≈31 → ≈11 scatti su 5
// aperture senza). Dentro uno sheet il focus aspetta la fine dell'ingresso.
describe('Input — autofocus rinviato dentro uno Sheet', () => {
  const field = () => screen.getByRole('textbox')

  it('fuori da uno sheet prende subito il focus', () => {
    render(<Input value="" onChange={() => {}} autoFocus />)
    expect(field()).toHaveFocus()
  })

  it('dentro uno sheet che sta ancora entrando non prende il focus', () => {
    render(
      <SheetEnteredContext.Provider value={false}>
        <Input value="" onChange={() => {}} autoFocus />
      </SheetEnteredContext.Provider>,
    )
    expect(field()).not.toHaveFocus()
  })

  it('prende il focus quando lo sheet ha finito di entrare', () => {
    const ui = (entered: boolean) => (
      <SheetEnteredContext.Provider value={entered}>
        <Input value="" onChange={() => {}} autoFocus />
      </SheetEnteredContext.Provider>
    )
    const { rerender } = render(ui(false))
    rerender(ui(true))
    expect(field()).toHaveFocus()
  })

  it('montato in uno sheet già entrato prende subito il focus', () => {
    render(
      <SheetEnteredContext.Provider value={true}>
        <Input value="" onChange={() => {}} autoFocus />
      </SheetEnteredContext.Provider>,
    )
    expect(field()).toHaveFocus()
  })
})
