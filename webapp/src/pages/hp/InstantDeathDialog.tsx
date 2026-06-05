import { m } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { GiSkullCrossedBones as Skull } from 'react-icons/gi'
import { spring } from '@/styles/motion'
import ResultDialog from '@/components/ui/ResultDialog'

interface Props {
  open: boolean
  onClose: () => void
}

export default function InstantDeathDialog({ open, onClose }: Props) {
  const { t } = useTranslation()
  if (!open) return null
  return (
    <ResultDialog
      open
      onClose={onClose}
      accent="crimson"
      pulse
      size="sm"
      title={t('character.death_saves.instant_death_title')}
    >
      <m.div
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ ...spring.swipe, delay: 0.1 }}
        className="flex justify-center text-[var(--dnd-crimson-bright)]"
      >
        <Skull size={64} />
      </m.div>
      <p className="text-sm font-body italic text-dnd-text-muted">
        {t('character.death_saves.instant_death_body')}
      </p>
    </ResultDialog>
  )
}
