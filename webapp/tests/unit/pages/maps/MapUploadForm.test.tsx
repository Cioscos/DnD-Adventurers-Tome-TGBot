import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MapUploadForm from '@/pages/maps/MapUploadForm'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/api/client', () => ({ api: { maps: { uploadWithProgress: vi.fn() } } }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/Card', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/DndInput', async () => {
  const React = await import('react')
  return { default: (p: { label?: string; value: string; onChange: (v: string) => void }) => React.createElement('input', { 'aria-label': p.label, value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) }) }
})
vi.mock('@/components/DndButton', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children) }
})

const base = { charId: 7, onUploadComplete: () => {}, onCancel: () => {} }

describe('MapUploadForm', () => {
  it('keeps upload disabled until a zone and files are chosen', () => {
    render(<MapUploadForm {...base} existingZones={[]} />)
    expect(screen.getByRole('button', { name: 'character.maps.upload_btn' })).toBeDisabled()
  })

  it('selecting an existing zone chip fills the zone name', async () => {
    render(<MapUploadForm {...base} existingZones={['Foresta', 'Cripta']} />)
    await userEvent.click(screen.getByRole('button', { name: 'Cripta' }))
    expect(screen.getByLabelText('character.maps.zone_name')).toHaveValue('Cripta')
  })

  it('cancels', async () => {
    const onCancel = vi.fn()
    render(<MapUploadForm {...base} existingZones={[]} onCancel={onCancel} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
