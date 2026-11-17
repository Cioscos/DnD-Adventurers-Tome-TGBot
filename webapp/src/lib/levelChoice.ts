import type { TFunction } from 'i18next'
import { CLASS_NAME_TO_PROGRESSION_KEY } from '@/lib/classProgression'
import type { PendingChoice } from '@/types'

/** `class_key` è il nome-tabella italiano ("Guerriero"): lo traduciamo nella lingua UI. */
export function choiceClassLabel(t: TFunction, classKey: string): string {
  const classEn = Object.entries(CLASS_NAME_TO_PROGRESSION_KEY).find(([, v]) => v === classKey)?.[0]
  return classEn ? t(`dnd.classes.${classEn}`, { defaultValue: classKey }) : classKey
}

/** Cosa si sceglie, in parole (U4): gruppo noto, altrimenti il privilegio che porta la scelta, poi il generico. */
export function choiceWhat(t: TFunction, lang: 'it' | 'en', choice: PendingChoice): string {
  if (choice.kind === 'asi') return t('character.level_choice.asi_or_feat')
  if (choice.kind === 'epic_boon') return t('character.level_choice.epic_boon')
  if (choice.kind === 'feat') return t('character.level_choice.feat')
  return t(`character.level_choice.groups.${choice.group}`, {
    defaultValue: choice.title?.[lang] ?? t('character.level_choice.class_option_title'),
  })
}

export function choiceTitle(t: TFunction, lang: 'it' | 'en', choice: PendingChoice): string {
  return `${choiceWhat(t, lang, choice)} · ${choiceClassLabel(t, choice.class_key)} ${choice.level}`
}
