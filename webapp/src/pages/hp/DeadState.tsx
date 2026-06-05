import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { GiSkullCrossedBones as Skull } from 'react-icons/gi'
import { GiHeartPlus as Heart } from 'react-icons/gi'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import ConfirmSheet from '@/components/ui/ConfirmSheet'

interface DeadStateProps {
  cause: 'death_saves' | 'massive_damage'
  onRevive: () => void
  reviving: boolean
}

export default function DeadState({ cause, onRevive, reviving }: DeadStateProps) {
  const { t } = useTranslation()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const causeKey = cause === 'death_saves'
    ? 'character.death_saves.cause_death_saves'
    : 'character.death_saves.cause_massive_damage'

  return (
    <Surface variant="ember" ornamented className="flex flex-col items-center gap-4 text-center">
      <Skull size={56} className="text-[var(--dnd-crimson-bright)]" />
      <div className="flex flex-col gap-1">
        <h3 className="font-display font-black text-[var(--dnd-crimson-bright)] text-2xl uppercase tracking-[0.15em]">
          {t('character.death_saves.dead_title')}
        </h3>
        <p className="text-sm font-body text-dnd-text-muted">
          {t(causeKey)}
        </p>
      </div>
      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => setConfirmOpen(true)}
        loading={reviving}
        icon={<Heart size={18} />}
        haptic="success"
      >
        {t('character.death_saves.revive')}
      </Button>

      <ConfirmSheet
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          onRevive()
        }}
        title={t('character.death_saves.revive_confirm_title')}
        body={t('character.death_saves.revive_confirm_body')}
        confirmLabel={t('character.death_saves.revive')}
        cancelLabel={t('common.cancel')}
        confirmVariant="primary"
        loading={reviving}
      />
    </Surface>
  )
}
