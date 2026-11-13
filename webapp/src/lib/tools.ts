import toolsData from '@/data/tools.json'

/** Catalogo degli strumenti: specchio di `core/data/tools.py` (rigenerato da `scripts/export_tools.py`). */
export type ToolCategory = 'artisan' | 'gaming' | 'instrument' | 'kit' | 'thieves' | 'vehicle'
export type ToolSpec = { key: string; it: string; en: string; category: ToolCategory; ability: string }
export type ToolLevel = boolean | 'expert'

export const TOOLS = toolsData as ToolSpec[]
export const TOOL_CATEGORIES: ToolCategory[] = ['artisan', 'gaming', 'instrument', 'kit', 'thieves', 'vehicle']
const BY_KEY = new Map(TOOLS.map((t) => [t.key, t]))

export function toolByKey(key: string): ToolSpec | undefined {
  return BY_KEY.get(key)
}

export function toolLabel(key: string, lang: string): string {
  const t = BY_KEY.get(key)
  if (!t) return key
  return lang.startsWith('en') ? t.en : t.it
}

/** Strumenti competenti del personaggio, in ordine di catalogo; chiavi sconosciute scartate. */
export function proficientTools(profs: Record<string, ToolLevel> | undefined | null): { tool: ToolSpec; level: ToolLevel }[] {
  return TOOLS.filter((t) => profs?.[t.key]).map((tool) => ({ tool, level: profs![tool.key] }))
}
