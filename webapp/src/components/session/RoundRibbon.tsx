import { useEffect, useRef } from 'react'
import { GiDeathSkull as Skull } from 'react-icons/gi'
import type { CombatantLive } from '@/types'

type SegState = 'done' | 'active' | 'upcoming' | 'dead'

interface Props {
  combatants: CombatantLive[]
  activeId: number | null
  myUserId: number
}

/** Nastro del round: un segmento per combattente, in ordine d'iniziativa. */
export default function RoundRibbon({ combatants, activeId, myUserId }: Props) {
  const activeIdx = combatants.findIndex((c) => c.id === activeId)
  const ribbonRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)

  // Con molti combattenti il segmento attivo può essere fuori vista: lo centro
  // scorrendo SOLO il nastro (scrollIntoView sposterebbe anche la pagina).
  useEffect(() => {
    const ribbon = ribbonRef.current
    const seg = activeRef.current
    if (!ribbon || !seg) return
    ribbon.scrollTo?.({
      left: seg.offsetLeft - (ribbon.clientWidth - seg.clientWidth) / 2,
      behavior: 'smooth',
    })
  }, [activeId])

  return (
    <div ref={ribbonRef} data-testid="round-ribbon" className="relative flex gap-1 overflow-x-auto py-1 -mx-1 px-1">
      {combatants.map((c, i) => {
        const state: SegState = c.is_dead
          ? 'dead'
          : i === activeIdx
            ? 'active'
            : activeIdx >= 0 && i < activeIdx
              ? 'done'
              : 'upcoming'
        const isMe = c.kind === 'pc' && c.owner_user_id === myUserId
        return (
          <div
            key={c.id}
            ref={state === 'active' ? activeRef : undefined}
            data-testid="ribbon-seg"
            data-state={state}
            data-kind={c.kind}
            data-me={isMe ? 'true' : undefined}
            className={`min-w-[56px] max-w-[88px] shrink-0 flex-1 h-11 rounded-lg border px-1.5
              flex flex-col items-center justify-center leading-tight
              ${state === 'active'
                ? 'border-dnd-gold bg-dnd-surface-raised text-dnd-gold-bright ring-2 ring-dnd-gold-bright/40 shadow-dnd-glow'
                : `bg-dnd-surface ${isMe ? 'border-dnd-cobalt-bright' : 'border-dnd-border'} text-dnd-text`}
              ${c.kind === 'monster' ? 'border-b-2 border-b-dnd-crimson' : ''}
              ${state === 'done' || state === 'dead' ? 'opacity-50' : ''}`}
          >
            <span className="w-full truncate text-center text-xs font-body">{c.name}</span>
            {state === 'dead' ? (
              <Skull size={12} className="text-dnd-text-muted" />
            ) : (
              <span className="font-mono tabular-nums text-xs font-bold">{c.initiative ?? '—'}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
