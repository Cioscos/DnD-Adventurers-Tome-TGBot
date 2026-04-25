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
      if (charId) qc.invalidateQueries({ queryKey: ['dice-history', charId] })
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
        const total = e.kind === 'd100' ? pairD100(vals) : vals.reduce((s, v) => s + v, 0)
        const notation = `${e.count}${e.kind}`
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

      await persist.mutateAsync({
        rolls: bodyRolls,
        label: opts.label ?? null,
        modifier: opts.modifier ?? 0,
        notation: opts.notation ?? null,
      })

      return groupResults
    },
    [animate3d, charId, dice, persist, reducedMotion],
  )

  return { roll, isPending: persist.isPending, error: persist.error }
}

function pairD100(vals: number[]): number {
  let total = 0
  for (let i = 0; i < vals.length; i += 2) {
    const tens = vals[i]
    const ones = vals[i + 1]
    let v = tens * 10 + ones
    if (v === 0) v = 100
    total += v
  }
  return total
}
