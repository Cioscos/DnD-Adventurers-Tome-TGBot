import type { TFunction } from 'i18next'
import { classKey } from '@/lib/classProgression'

/** Nome di classe da mostrare: la chiave inglese canonica (`barbarian`) si traduce, un nome libero o custom resta com'è. */
/** «Mago» e «Wizard» valgono `wizard`: il nome salvato è quello della lingua di quando è stato creato. */
export const classLabel = (t: TFunction, name: string): string => t(`dnd.classes.${classKey(name) ?? name}`, { defaultValue: name })

/** «Mago 5 (Scuola) / Guerriero 2», con i nomi tradotti; «Nessuna classe» senza classi. */
export const classSummary = (t: TFunction, classes: { class_name: string; level: number; subclass?: string | null }[]): string =>
  classes.length
    ? classes.map((c) => `${classLabel(t, c.class_name)} ${c.level}${c.subclass ? ` (${c.subclass})` : ''}`).join(' / ')
    : t('character.select.no_class')
