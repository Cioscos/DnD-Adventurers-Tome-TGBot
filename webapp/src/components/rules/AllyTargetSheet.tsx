import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'

export type Ally = { id: number; name: string; /** Dado che ha già: darne un altro lo sostituisce. */ die?: number | null }
type Props = {
  allies: Ally[]
  pending?: boolean
  /** `null`: un'altra creatura (PNG o personaggio non seduto): si usa senza bersaglio, solo esito e durata. */
  onPick: (allyId: number | null) => void
  onClose: () => void
}

/** A chi va un dado o un effetto che aiuta un alleato: i personaggi seduti alla stessa serata (Ispirazione Bardica).
 *  Chi ha già un dado lo perde se ne arriva un altro: prima si conferma. */
export default function AllyTargetSheet({ allies, pending = false, onPick, onClose }: Props) {
  const { t } = useTranslation()
  const [replacing, setReplacing] = useState<Ally | null>(null)
  return (
    <Sheet open onClose={onClose} title={t('character.turn.ally_title')} zClassName="z-[60]">
      <div className="flex flex-col gap-2 px-4 pb-4">
        {replacing ? (
          <>
            <p className="text-sm font-body text-dnd-text">{t('character.turn.ally_has_die', { die: replacing.die, name: replacing.name })}</p>
            <Button variant="primary" disabled={pending} onClick={() => onPick(replacing.id)}>
              {t('character.turn.ally_replace')}
            </Button>
            <Button variant="secondary" disabled={pending} onClick={() => setReplacing(null)}>
              {t('character.turn.ally_back')}
            </Button>
          </>
        ) : (
          <>
            <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{t('character.turn.ally_pick')}</p>
            {allies.map((a) => (
              <Button key={a.id} variant="secondary" className="justify-start break-words text-left" disabled={pending}
                onClick={() => (a.die ? setReplacing(a) : onPick(a.id))}>
                {a.name}
                {a.die ? <span className="ml-2 text-xs font-normal text-dnd-text-muted">d{a.die}</span> : null}
              </Button>
            ))}
            <Button variant="ghost" className="justify-start break-words text-left" disabled={pending} onClick={() => onPick(null)}>
              {t('character.turn.ally_other')}
            </Button>
          </>
        )}
      </div>
    </Sheet>
  )
}
