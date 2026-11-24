import { useCallback, useState } from 'react'

/** Scelte legate a edizione+classe: cambiando chiave si riparte dalle predefinite (null). */
export function useEquipPicks<T = number[]>(key: string) {
  const [s, set] = useState<{ key: string; picks: T | null } | null>(null)
  if (s && s.key !== key) set(null) // stato derivato: scarta subito le scelte della classe precedente
  const setPicks = useCallback((picks: T | null) => set({ key, picks }), [key])
  return [s?.key === key ? s.picks : null, setPicks] as const
}
