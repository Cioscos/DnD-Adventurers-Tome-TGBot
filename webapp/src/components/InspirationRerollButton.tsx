import { useTranslation } from 'react-i18next'
import { GiPolarStar as Star } from 'react-icons/gi'
import Pressable from '@/components/ui/Pressable'

type Props = {
  available: boolean
  pending?: boolean
  onClick: () => void | Promise<void>
}

export default function InspirationRerollButton({ available, pending = false, onClick }: Props) {
  const { t } = useTranslation()
  if (!available) return null

  return (
    <Pressable
      type="button"
      onClick={onClick}
      pending={pending}
      className="w-full py-2.5 rounded-xl border border-dnd-arcane/60
                 bg-gradient-to-r from-dnd-arcane-deep/40 to-dnd-gold-deep/30
                 text-dnd-gold-bright font-cinzel uppercase tracking-wider
                 flex items-center justify-center gap-2 min-h-[44px]
                 disabled:opacity-50"
      whileTap={{ scale: 0.95 }}
    >
      <Star size={16} className="text-dnd-arcane-bright" fill="currentColor" />
      {t('character.inspiration.use_reroll')}
    </Pressable>
  )
}
