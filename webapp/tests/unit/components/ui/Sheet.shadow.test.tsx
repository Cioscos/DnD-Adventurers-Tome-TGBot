import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LazyMotion, domMax } from 'framer-motion'
import Sheet from '@/components/ui/Sheet'

// Perf (S22): l'ombra shadow-5 sul pannello che scorre satura la GPU a ogni frame
// (≈45 scatti su 5 aperture → ≈7 senza). Su mobile non si vede (cade fuori schermo,
// sotto il velo scuro): resta solo sul dialog centrato da md in su.
describe('Sheet — ombra solo da desktop', () => {
  it('il pannello non ha l\'ombra pesante su mobile, solo con prefisso md:', () => {
    render(
      <LazyMotion features={domMax} strict>
        <Sheet open onClose={() => {}} title="Titolo">
          <p>contenuto</p>
        </Sheet>
      </LazyMotion>,
    )
    const classes = screen.getByText('contenuto').closest('.surface-parchment')!.className.split(/\s+/)
    expect(classes).not.toContain('shadow-parchment-2xl')
    expect(classes).toContain('md:shadow-parchment-2xl')
  })
})
