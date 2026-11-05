import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { api } from '@/api/client'
import type { CharacterFull } from '@/types'

/** Traduce le note di un tiro: `condition:<slug>`, `armor:untrained`, `armor:stealth`, `weapon:heavy`, `inspiration:advantage`, `feature:<chiave>`.
 *  `charId` serve fuori da /char/:id (sessione): dà l'edizione per il nome della spossatezza. */
export function useRollNoteLabels(charId?: number): (notes: string[]) => string[] {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const { id } = useParams<{ id: string }>()
  const cid = charId ?? (id ? Number(id) : undefined)
  const edition = qc.getQueryData<CharacterFull>(['character', cid])?.rules_edition
  // Fuori da /char/:id (la sessione) il personaggio può non essere in cache: serve per il nome dei privilegi nelle note.
  useQuery({
    queryKey: ['character', cid], queryFn: () => api.characters.get(cid!), retry: false,
    enabled: cid != null && Number.isFinite(cid) && !qc.getQueryData(['character', cid]),
  })

  const featureName = (key: string): string => {
    for (const [, char] of qc.getQueriesData<CharacterFull>({ queryKey: ['character'] })) {
      const name = char?.abilities?.find((a) => a.feature_key === key)?.name
      if (name) return name
    }
    return key
  }

  return (notes) => notes.map((note) => {
    const [kind, value] = note.split(/:(.*)/s)
    if (kind === 'condition') {
      if (value === 'surprised') return t('character.roll_notes.surprised')
      return value === 'exhaustion'
        ? t('character.conditions.exhaustion_condition', { context: edition })
        : t(`character.conditions.${value}`)
    }
    if (kind === 'armor') return t(`character.roll_notes.armor_${value === 'stealth' ? 'stealth' : 'untrained'}`)
    if (kind === 'weapon') return t('character.roll_notes.weapon_heavy')
    if (kind === 'inspiration') return t('character.roll_notes.inspiration')
    if (kind === 'feature') return featureName(value)
    return note
  })
}
