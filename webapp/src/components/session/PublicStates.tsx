import { useTranslation } from 'react-i18next'
import type { PublicState } from '@/types'

/** Stati attivi di un PG che portano effetti su altri (Lupo, Orso, Attacco Irruento): li devono vedere il GM e il gruppo. */
export default function PublicStates({ states }: { states?: PublicState[] | null }) {
  const { t } = useTranslation()
  if (!states?.length) return null
  return (
    <ul data-testid="public-states" className="mt-1.5 flex flex-col gap-1">
      {states.map((s) => (
        <li key={s.key} className="min-w-0 text-xs font-body text-dnd-text">
          <span className="font-semibold text-dnd-gold-bright">{s.name}</span>
          {s.rounds_left != null && (
            <span className="ml-1.5 tabular-nums text-dnd-text-muted">{t('character.turn.state_rounds_left', { n: s.rounds_left })}</span>
          )}
          {s.others.map((o) => (
            <p key={o.key} className="break-words text-dnd-text-muted">{o.name}: {o.text}</p>
          ))}
        </li>
      ))}
    </ul>
  )
}
