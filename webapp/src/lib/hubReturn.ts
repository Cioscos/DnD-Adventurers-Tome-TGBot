// Ultimo PG di cui è stato mostrato l'hub. Tornando da una sottopagina dello stesso PG l'hub non rifà
// le animazioni d'ingresso (sembrava un flash); la lista personaggi azzera, così riaprirlo le rifà.
let lastHubCharId: number | null = null
export const isHubReturn = (charId: number) => lastHubCharId === charId
export const markHubShown = (charId: number) => { lastHubCharId = charId }
export const resetHubReturn = () => { lastHubCharId = null }
