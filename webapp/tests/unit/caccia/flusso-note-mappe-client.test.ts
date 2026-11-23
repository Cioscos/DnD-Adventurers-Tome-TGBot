import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'

afterEach(() => { vi.unstubAllGlobals() })

describe('caccia: indirizzo delle note', () => {
  // caccia: {"id": "CB-028", "fonte": "invariante: eliminare una nota non tocca altro che la nota", "zona": "flusso:note-mappe", "voce": "limiti", "copre": []}
  it.each(['..', '.', 'a/../..'])('il titolo «%s» non parte: il browser ne farebbe un altro indirizzo', async (titolo) => {
    const richiesta = vi.fn(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', richiesta)
    for (const azione of [() => api.notes.remove(1, titolo), () => api.notes.update(1, titolo, 'x'), () => api.share.note(1, titolo)]) {
      await expect((async () => azione())()).rejects.toThrow()
    }
    expect(richiesta).not.toHaveBeenCalled()
    await api.notes.remove(1, 'Atto 1/2')
    expect(richiesta).toHaveBeenCalledTimes(1)
  })
})
