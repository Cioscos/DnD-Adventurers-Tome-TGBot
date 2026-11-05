import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'

type Props = { allies: { id: number; name: string }[]; pending?: boolean; onPick: (allyId: number) => void; onClose: () => void }

/** A chi va un dado o un effetto che aiuta un alleato: i personaggi seduti alla stessa serata (Ispirazione Bardica). */
export default function AllyTargetSheet({ allies, pending = false, onPick, onClose }: Props) {
  const { t } = useTranslation()
  return (
    <Sheet open onClose={onClose} title={t('character.turn.ally_title')} zClassName="z-[60]">
      <div className="flex flex-col gap-2 px-4 pb-4">
        <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{t('character.turn.ally_pick')}</p>
        {allies.map((a) => (
          <Button key={a.id} variant="secondary" className="justify-start break-words text-left" disabled={pending}
            onClick={() => onPick(a.id)}>
            {a.name}
          </Button>
        ))}
      </div>
    </Sheet>
  )
}
