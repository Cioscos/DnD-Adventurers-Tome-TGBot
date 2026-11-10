/** Proprietà di un'arma che il client legge dai metadati (Leggera, Accurata). Il dado di Arti Marziali e quali armi lo
 *  accettano li decide il server (`unarmed_damage_dice` della scheda, `Item.martial_arts`). */
type ItemLike = { item_metadata?: Record<string, unknown> | null }

function hasProperty(item: ItemLike, ...words: string[]): boolean {
  const props = item.item_metadata?.properties
  const listed = (Array.isArray(props) ? props : []).map(String).join(' ').toLowerCase()
  return words.some((w) => listed.includes(w))
}

export const isLight = (item: ItemLike) => hasProperty(item, 'light', 'legger')
export const isFinesse = (item: ItemLike) => hasProperty(item, 'finesse', 'accurat')
