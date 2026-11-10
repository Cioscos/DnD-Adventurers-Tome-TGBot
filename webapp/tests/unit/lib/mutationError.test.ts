import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { ApiError } from '@/api/client'
import { notifyMutationError, apiErrorCode, actionFailedKey } from '@/lib/mutationError'
import { uiLang } from '@/lib/lang'

const { error } = vi.hoisted(() => ({ error: vi.fn() }))
vi.mock('sonner', () => ({ toast: { error } }))

beforeEach(() => error.mockClear())

describe('notifyMutationError (punto 54)', () => {
  it('says the reason the server gave, with its own text', () => {
    notifyMutationError(new ApiError(409, { code: 'turn_slot_used' }))
    expect(error).toHaveBeenCalledWith(expect.not.stringContaining('connessione'))
    expect(error.mock.calls[0][0]).not.toBe('common.action_failed')
  })

  it('a server refusal without a known code is a refusal, not a connection problem', () => {
    notifyMutationError(new ApiError(422, 'whatever'))
    const refused = error.mock.calls[0][0]
    notifyMutationError(new Error('network'))
    expect(error.mock.calls[1][0]).not.toBe(refused)
    expect(actionFailedKey(new ApiError(500, null))).toBe('common.action_refused')
    expect(actionFailedKey(new Error('x'))).toBe('common.action_failed')
  })

  it('apiErrorCode reads the code only from server errors', () => {
    expect(apiErrorCode(new ApiError(409, { code: 'no_uses' }))).toBe('no_uses')
    expect(apiErrorCode(new ApiError(409, 'plain'))).toBeUndefined()
    expect(apiErrorCode(new Error('x'))).toBeUndefined()
  })

  it('uiLang maps every language that is not English to Italian', () => {
    expect(uiLang('en-US')).toBe('en')
    expect(uiLang('it')).toBe('it')
    expect(uiLang('fr')).toBe('it')
    expect(uiLang(undefined)).toBe('it')
  })
})

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === 'graphify-out' ? [] : sources(path)
    return /\.(ts|tsx)$/.test(name) ? [path] : []
  })
}

describe('the sweep stays done', () => {
  const files = sources(join(__dirname, '../../../src')).filter((f) => !f.endsWith('mutationError.ts'))

  it('no handler calls notifyMutationError() without the error: the server reason would be lost', () => {
    const bare = files.filter((f) => /notifyMutationError\(\)/.test(readFileSync(f, 'utf8')))
    expect(bare).toEqual([])
  })

  it('no handler shows «controlla la connessione» directly: it goes through notifyMutationError / actionFailedKey', () => {
    // ItemForm: il catalogo SRD è un file locale caricato a richiesta, se manca è davvero un problema di rete, non un rifiuto del server.
    const direct = files.filter((f) => !f.endsWith('ItemForm.tsx') && /toast\.error\(t\('common\.action_failed'\)\)/.test(readFileSync(f, 'utf8')))
    expect(direct).toEqual([])
  })
})
