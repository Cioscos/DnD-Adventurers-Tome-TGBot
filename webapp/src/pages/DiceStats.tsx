import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Trash2, BarChart3 } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import DiceIcon from '@/components/ui/DiceIcon'
import EmptyState from '@/components/ui/EmptyState'
import { haptic } from '@/auth/telegram'

type DieSide = 4 | 6 | 8 | 10 | 12 | 20 | 100

const KIND_ORDER: readonly DieSide[] = [4, 6, 8, 10, 12, 20, 100]

interface KindSummary {
  sides: DieSide
  kind: string
  faces: Record<string, number>
  count: number
  sum: number
  avg: number
}

function summarize(stats: Record<string, Record<string, number>>): KindSummary[] {
  return KIND_ORDER.flatMap((sides) => {
    const kind = `d${sides}`
    const faces = stats[kind]
    if (!faces) return []
    let count = 0
    let sum = 0
    for (const [face, n] of Object.entries(faces)) {
      count += n
      sum += Number(face) * n
    }
    if (count === 0) return []
    return [{ sides, kind, faces, count, sum, avg: sum / count }]
  })
}

function FaceHistogram({ sides, faces }: { sides: DieSide; faces: Record<string, number> }) {
  const values = Array.from({ length: sides }, (_, i) => i + 1)
  const max = Math.max(1, ...values.map((v) => faces[String(v)] ?? 0))
  return (
    <div className="flex items-end gap-px h-12 mt-2">
      {values.map((v) => {
        const n = faces[String(v)] ?? 0
        const pct = (n / max) * 100
        const tone =
          sides === 20 && v === 20
            ? 'bg-dnd-emerald'
            : sides === 20 && v === 1
              ? 'bg-dnd-crimson'
              : 'bg-dnd-gold-dim'
        // Oltre le 20 facce (d100) le colonne sono ~3px: un'etichetta per
        // faccia diventa una poltiglia illeggibile, mostra solo i multipli di 10.
        const showTick = sides <= 20 || v % 10 === 0
        return (
          <div key={v} className="flex-1 flex flex-col items-center gap-0.5 min-w-0">
            <div className="w-full flex items-end h-9 rounded-sm bg-dnd-surface">
              <div
                className={`w-full rounded-sm ${n > 0 ? tone : ''}`}
                style={{ height: `${pct}%` }}
              />
            </div>
            <span className="text-[7px] leading-none text-dnd-text-faint tabular-nums">
              {showTick ? v : ' '}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function DiceStats() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showResetConfirm, setShowResetConfirm] = useState(false)

  const { data } = useQuery({
    queryKey: ['dice-stats', charId],
    queryFn: () => api.dice.stats(charId),
  })

  const resetMutation = useMutation({
    mutationFn: () => api.dice.resetStats(charId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dice-stats', charId] })
      haptic.success()
      setShowResetConfirm(false)
    },
    onError: () => haptic.error(),
  })

  const stats = data?.stats ?? {}
  const kinds = summarize(stats)
  const totalRolls = kinds.reduce((acc, k) => acc + k.count, 0)
  const nat20 = stats.d20?.['20'] ?? 0
  const nat1 = stats.d20?.['1'] ?? 0

  return (
    <Layout
      title={t('character.dice_stats.title')}
      backTo={`/char/${charId}/dice`}
      group="tools"
      page="dice"
    >
      {totalRolls === 0 ? (
        <EmptyState
          icon={<BarChart3 size={32} />}
          title={t('character.dice_stats.empty_title')}
          hint={t('character.dice_stats.empty_hint')}
        />
      ) : (
        <div className="space-y-3">
          {/* Trofei nat 20 / nat 1 + totale */}
          <div className="grid grid-cols-2 gap-3">
            <Surface variant="elevated" className="text-center py-3">
              <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-emerald-bright">
                {t('character.dice_stats.nat20')}
              </p>
              <p className="text-3xl font-mono font-bold tabular-nums text-dnd-emerald-bright mt-1">
                {nat20}
              </p>
            </Surface>
            <Surface variant="elevated" className="text-center py-3">
              <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-crimson-bright">
                {t('character.dice_stats.nat1')}
              </p>
              <p className="text-3xl font-mono font-bold tabular-nums text-dnd-crimson-bright mt-1">
                {nat1}
              </p>
            </Surface>
          </div>

          <Surface variant="elevated" className="flex items-center justify-between px-4 py-3">
            <span className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">
              {t('character.dice_stats.total_rolls')}
            </span>
            <span className="text-xl font-mono font-bold tabular-nums text-dnd-gold-bright">
              {totalRolls}
            </span>
          </Surface>

          {/* Card per tipo di dado */}
          {kinds.map((k, i) => (
            <m.div
              key={k.kind}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <Surface variant="elevated">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <DiceIcon sides={k.sides} size={28} className="text-dnd-gold" />
                    <span className="font-cinzel font-bold text-dnd-gold-bright uppercase">
                      {k.kind}
                    </span>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-dnd-text-muted font-body">
                      {t('character.dice_stats.rolls_count', { count: k.count })}
                    </p>
                    <p className="text-sm font-mono tabular-nums text-dnd-text">
                      {t('character.dice_stats.average')}{' '}
                      <span className="font-bold">{k.avg.toFixed(1)}</span>
                    </p>
                  </div>
                </div>
                <FaceHistogram sides={k.sides} faces={k.faces} />
              </Surface>
            </m.div>
          ))}

          <div className="flex justify-end pt-1">
            <Button
              variant="danger"
              size="sm"
              icon={<Trash2 size={12} />}
              haptic="warning"
              onClick={() => setShowResetConfirm(true)}
            >
              {t('character.dice_stats.reset')}
            </Button>
          </div>
        </div>
      )}

      <ConfirmSheet
        open={showResetConfirm}
        onClose={() => setShowResetConfirm(false)}
        onConfirm={() => resetMutation.mutate()}
        title={t('character.dice_stats.reset_confirm_title')}
        body={t('character.dice_stats.reset_confirm_body')}
        confirmLabel={t('character.dice_stats.reset')}
        cancelLabel={t('common.cancel')}
        confirmVariant="danger"
        loading={resetMutation.isPending}
      />
    </Layout>
  )
}
