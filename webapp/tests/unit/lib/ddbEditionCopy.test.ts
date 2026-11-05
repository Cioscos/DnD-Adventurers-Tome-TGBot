import { describe, it, expect } from 'vitest'
import it_ from '@/locales/it.json'
import en from '@/locales/en.json'

// `mixed` vale anche per una sola classe con fonte ignota o homebrew: il testo non può dire solo "edizioni diverse".
describe('ddb_import.edition_body', () => {
  it('copre anche una fonte non riconosciuta, in italiano', () => {
    expect(it_.ddb_import.edition_body).toMatch(/non riconosc/i)
  })
  it('covers an unrecognised source too, in English', () => {
    expect(en.ddb_import.edition_body).toMatch(/not recogni[sz]ed|can't tell|cannot tell/i)
  })
})
