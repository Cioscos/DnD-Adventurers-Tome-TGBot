export const HERO_SECTIONS = ['slots', 'stats', 'quick_actions'] as const
export type HeroSectionKey = (typeof HERO_SECTIONS)[number]

export interface HeroLayout {
  order: HeroSectionKey[]
  hidden: HeroSectionKey[]
}

const isSectionKey = (v: unknown): v is HeroSectionKey =>
  typeof v === 'string' && (HERO_SECTIONS as readonly string[]).includes(v)

/** Legge settings.hero_layout in modo difensivo: chiavi ignote scartate,
 *  sezioni mancanti accodate nell'ordine di default, duplicati rimossi.
 *  Un settings assente o malformato produce il layout di default. */
export function readHeroLayout(settings: Record<string, unknown> | undefined): HeroLayout {
  const raw = settings?.hero_layout as { order?: unknown; hidden?: unknown } | undefined
  const rawOrder = Array.isArray(raw?.order) ? raw.order : []
  const rawHidden = Array.isArray(raw?.hidden) ? raw.hidden : []

  const order: HeroSectionKey[] = []
  for (const key of rawOrder) {
    if (isSectionKey(key) && !order.includes(key)) order.push(key)
  }
  for (const key of HERO_SECTIONS) {
    if (!order.includes(key)) order.push(key)
  }
  const hidden = [...new Set(rawHidden.filter(isSectionKey))]
  return { order, hidden }
}
