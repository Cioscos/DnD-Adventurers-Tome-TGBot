import type { TFunction } from 'i18next'

/** Nome di classe da mostrare: la chiave inglese canonica (`barbarian`) si traduce, un nome libero o custom resta com'è. */
export const classLabel = (t: TFunction, name: string): string => t(`dnd.classes.${name}`, { defaultValue: name })
