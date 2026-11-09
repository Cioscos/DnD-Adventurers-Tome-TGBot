import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Pressable from '@/components/ui/Pressable'

interface Props {
  edition: string
  className: string
  /** Una alternativa scelta per gruppo; il passo la inizializza alla prima. */
  picks: number[] | null
  onPicks: (picks: number[]) => void
}

/** Equipaggiamento di partenza della classe: oggetti inerti, il giocatore li equipaggia a mano dopo. */
export default function EquipmentStep({ edition, className, picks, onPicks }: Props) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['rules', 'starting-equipment', edition, className],
    queryFn: () => api.rules.startingEquipment(edition, className),
    staleTime: Infinity,
  })
  const groups = useMemo(() => data?.groups ?? [], [data])
  useEffect(() => {
    if (groups.length && picks?.length !== groups.length) onPicks(groups.map(() => 0))
  }, [groups, picks, onPicks])

  if (isLoading) return <p className="text-sm text-dnd-text-muted font-body text-center">{t('common.loading')}</p>
  if (!groups.length) return <p className="text-sm text-dnd-text-muted font-body italic text-center">{t('character.create.equipment_none')}</p>

  return (
    <div className="space-y-3">
      <p className="text-xs text-dnd-text-faint font-body italic text-center">{t('character.create.equipment_hint')}</p>
      {groups.map((alts, gi) =>
        alts.length === 1 ? (
          <div key={gi} className="rounded-xl border border-dnd-border/60 px-3 py-2">
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.create.equipment_fixed')}</p>
            <p className="text-sm font-body text-dnd-text break-words">{alts[0]}</p>
          </div>
        ) : (
          <div key={gi} className="space-y-1.5">
            {alts.map((label, ai) => {
              const on = (picks?.[gi] ?? 0) === ai
              return (
                <Pressable
                  key={ai}
                  onClick={() => onPicks((picks ?? groups.map(() => 0)).map((p, i) => (i === gi ? ai : p)))}
                  className={`w-full min-h-[44px] px-3 py-2 rounded-xl border text-left text-sm font-body break-words transition-colors
                    ${on ? '!border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`}
                >
                  {label}
                </Pressable>
              )
            })}
          </div>
        ),
      )}
    </div>
  )
}
