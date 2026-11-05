import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DdbImportSheet from '@/components/character/DdbImportSheet'
import { renderWithProviders } from '../utils/renderWithProviders'

const { importDdb } = vi.hoisted(() => ({ importDdb: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { characters: { importDdb } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) {
      super(`API ${status}`)
    }
  },
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

const LINK = 'https://www.dndbeyond.com/characters/1'
const RESULT = { character: { id: 9 }, report: { imported: [], approximated: [], skipped: [] } }

async function conflict() {
  const { ApiError } = await import('@/api/client')
  return new ApiError(409, { code: 'edition_required' })
}

describe('DdbImportSheet: scelta dell\'edizione', () => {
  beforeEach(() => vi.clearAllMocks())

  it('un import normale non chiede nulla e non manda l\'edizione', async () => {
    importDdb.mockResolvedValue(RESULT)
    renderWithProviders(<DdbImportSheet open onClose={() => undefined} />)
    await userEvent.type(screen.getByRole('textbox'), LINK)
    await userEvent.click(screen.getByText('ddb_import.submit'))
    await waitFor(() => expect(importDdb).toHaveBeenCalledWith(LINK, undefined))
    expect(screen.queryByText('ddb_import.edition_2024')).toBeNull()
  })

  it('classi miste: chiede le regole e rilancia l\'import con quella scelta', async () => {
    importDdb.mockRejectedValueOnce(await conflict()).mockResolvedValueOnce(RESULT)
    renderWithProviders(<DdbImportSheet open onClose={() => undefined} />)
    await userEvent.type(screen.getByRole('textbox'), LINK)
    await userEvent.click(screen.getByText('ddb_import.submit'))
    await screen.findByText('ddb_import.edition_title')
    expect(screen.queryByText('ddb_import.errors.edition_required')).toBeNull()
    await userEvent.click(screen.getByText('ddb_import.edition_2024'))
    await waitFor(() => expect(importDdb).toHaveBeenLastCalledWith(LINK, '2024'))
    await screen.findByText('ddb_import.open')
  })
})
