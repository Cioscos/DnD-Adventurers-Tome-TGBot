import { useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { api, type DiceResultRequestBody } from '@/api/client'
import { useDiceSettings } from '@/store/diceSettings'
import { useDiceAnimation } from './useDiceAnimation'
import { rollMany } from './rng'
import type { DiceKind, DiceTint } from './types'

export interface RollEntry {
  kind: DiceKind
  count: number
  tint?: DiceTint
}

export interface RollOpts {
  label?: string
  modifier?: number
  notation?: string
  // Keep highest N of the rolled dice. The kept-top-N sum becomes the persisted
  // and returned total; the dropped dice stay in `rolls` for display.
  keepHighest?: number
}

export interface RollGroup {
  kind: DiceKind
  notation: string
  rolls: number[]
  total: number
}

export function useRollAndPersist(charId: number | null) {
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  const dice = useDiceAnimation()
  const qc = useQueryClient()

  const persist = useMutation({
    mutationFn: (body: DiceResultRequestBody) =>
      charId ? api.dice.result(charId, body) : Promise.reject(new Error('no charId')),
    onSettled: () => {
      if (charId) {
        qc.invalidateQueries({ queryKey: ['dice-history', charId] })
        qc.invalidateQueries({ queryKey: ['history', charId] })
      }
    },
  })

  const roll = useCallback(
    async (entries: RollEntry[], opts: RollOpts = {}): Promise<RollGroup[]> => {
      if (!charId) throw new Error('no charId')
      if (entries.length === 0) return []

      const useAnimation = animate3d && !reducedMotion

      let resultsPerEntry: number[][]

      if (useAnimation) {
        const playGroups = entries.map((e) => ({
          kind: e.kind,
          tint: e.tint,
          count: e.kind === 'd100' ? e.count * 2 : e.count,
        }))
        const detected = await dice.playAndCollect(playGroups)
        resultsPerEntry = entries.map((_e, gi) =>
          detected.filter((d) => d.groupIndex === gi).map((d) => d.value),
        )
      } else {
        resultsPerEntry = entries.map((e) => rollMany(e.kind, e.count).map((r) => r.value))
      }

      const bodyRolls: DiceResultRequestBody['rolls'] = []
      const groupResults: RollGroup[] = entries.map((e, i) => {
        const vals = resultsPerEntry[i]
        let total: number
        if (e.kind === 'd100') {
          total = pairD100(vals)
        } else if (opts.keepHighest && opts.keepHighest < vals.length) {
          const sortedDesc = [...vals].sort((a, b) => b - a)
          total = sortedDesc.slice(0, opts.keepHighest).reduce((s, v) => s + v, 0)
        } else {
          total = vals.reduce((s, v) => s + v, 0)
        }
        // opts.notation overrides only when there is a single entry (e.g. 4d6kh3
        // stat-roll). For multi-entry rolls each group keeps its computed notation.
        const notation = opts.notation && entries.length === 1 ? opts.notation : `${e.count}${e.kind}`
        if (e.kind === 'd100') {
          for (const v of vals) bodyRolls.push({ kind: 'd10', value: v })
        } else {
          for (const v of vals) {
            bodyRolls.push({
              kind: e.kind as DiceResultRequestBody['rolls'][number]['kind'],
              value: v,
            })
          }
        }
        return { kind: e.kind, notation, rolls: vals, total }
      })

      // When keepHighest is in effect, send the kept-top-N sum as `total` so the
      // backend persists it verbatim (the default server-side computation would
      // include the dropped dice).
      const bodyTotal =
        opts.keepHighest && groupResults.length === 1 ? groupResults[0].total : undefined

      await persist.mutateAsync({
        rolls: bodyRolls,
        label: opts.label ?? null,
        modifier: opts.modifier ?? 0,
        notation: opts.notation ?? null,
        total: bodyTotal ?? null,
      })

      return groupResults
    },
    [animate3d, charId, dice, persist, reducedMotion],
  )

  return { roll, isPending: persist.isPending, error: persist.error }
}

function pairD100(vals: number[]): number {
  // Geometry d10 face values are 1..10. In percentile convention, "10" represents
  // the digit 0 (e.g. tens=10 → 00 in percentile, ones=10 → 0 in percentile).
  // Pair 00+0 represents 100.
  let total = 0
  for (let i = 0; i < vals.length; i += 2) {
    const tens = vals[i] % 10
    const ones = vals[i + 1] % 10
    let v = tens * 10 + ones
    if (v === 0) v = 100
    total += v
  }
  return total
}
