import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import NoteEditor from '@/pages/notes/NoteEditor'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

describe('NoteEditor campaign', () => {
  const camps = [{ id: 7, name: 'Coda', current: true }, { id: 8, name: 'Altra', current: false }]

  it('new entry preselects the current campaign and can be saved with it', async () => {
    const onSave = vi.fn()
    renderWithProviders(<NoteEditor onSave={onSave} onCancel={() => {}} isPending={false} campaigns={camps} defaultCampaignId={7} />)
    expect(screen.getByRole('button', { name: 'Coda' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.type(screen.getByPlaceholderText('character.notes.title_placeholder'), 'T')
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(onSave).toHaveBeenCalledWith('T', '', [], 7))
  })

  it('"none" saves with a null campaign', async () => {
    const onSave = vi.fn()
    renderWithProviders(<NoteEditor onSave={onSave} onCancel={() => {}} isPending={false} campaigns={camps} defaultCampaignId={7} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.notes.campaign_none' }))
    await userEvent.type(screen.getByPlaceholderText('character.notes.title_placeholder'), 'T')
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(onSave).toHaveBeenCalledWith('T', '', [], null))
  })

  it('editing starts from the entry campaign, not the default', () => {
    renderWithProviders(<NoteEditor initialNote={{ title: 'A', body: 'b', tags: [], campaign_id: 8 }} onSave={() => {}} onCancel={() => {}} isPending={false} campaigns={camps} defaultCampaignId={7} />)
    expect(screen.getByRole('button', { name: 'Altra' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('a dead campaign id on the entry counts as none', () => {
    renderWithProviders(<NoteEditor initialNote={{ title: 'A', body: 'b', tags: [], campaign_id: 99 }} onSave={() => {}} onCancel={() => {}} isPending={false} campaigns={camps} />)
    expect(screen.getByRole('button', { name: 'character.notes.campaign_none' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('editing without touching the chips keeps the campaign (dead id or list not loaded)', async () => {
    const onSave = vi.fn()
    const note = { title: 'A', body: 'b', tags: [], campaign_id: 99 }
    const { unmount } = renderWithProviders(<NoteEditor initialNote={note} onSave={onSave} onCancel={() => {}} isPending={false} campaigns={camps} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSave).toHaveBeenLastCalledWith('A', 'b', [], undefined)
    unmount()
    renderWithProviders(<NoteEditor initialNote={{ ...note, campaign_id: 8 }} onSave={onSave} onCancel={() => {}} isPending={false} campaigns={[]} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSave).toHaveBeenLastCalledWith('A', 'b', [], undefined)
  })

  it('editing and explicitly picking «none» clears the campaign', async () => {
    const onSave = vi.fn()
    renderWithProviders(<NoteEditor initialNote={{ title: 'A', body: 'b', tags: [], campaign_id: 8 }} onSave={onSave} onCancel={() => {}} isPending={false} campaigns={camps} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.notes.campaign_none' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSave).toHaveBeenLastCalledWith('A', 'b', [], null)
  })

  it('a default arriving late does not wipe typed title', async () => {
    let arrive: () => void = () => {}
    function Host() {
      const [ready, setReady] = useState(false)
      arrive = () => setReady(true)
      return <NoteEditor onSave={() => {}} onCancel={() => {}} isPending={false} campaigns={ready ? camps : []} defaultCampaignId={ready ? 7 : null} />
    }
    renderWithProviders(<Host />)
    await userEvent.type(screen.getByPlaceholderText('character.notes.title_placeholder'), 'Abc')
    act(() => arrive())
    expect(screen.getByPlaceholderText('character.notes.title_placeholder')).toHaveValue('Abc')
    expect(screen.getByRole('button', { name: 'Coda' })).toHaveAttribute('aria-pressed', 'true')
  })
})
