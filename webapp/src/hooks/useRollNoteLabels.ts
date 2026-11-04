import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { CharacterFull } from '@/types'

/** Traduce le note di un tiro: `condition:<slug>`, `armor:untrained`, `feature:<chiave>`. */
export function useRollNoteLabels(): (notes: string[]) => string[] {
  const { t } = useTranslation()
  const qc = useQueryClient()

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
      return value === 'exhaustion'
        ? t('character.conditions.exhaustion_condition')
        : t(`character.conditions.${value}`)
    }
    if (kind === 'armor') return t('character.roll_notes.armor_untrained')
    if (kind === 'feature') return featureName(value)
    return note
  })
}
