import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import FeatChoiceList from '@/components/character/FeatChoiceList'
import { featsFor } from '@/lib/feats'
import { uiLang } from '@/lib/lang'

interface Props {
  value: string | null
  onChange: (key: string | null) => void
}

/** Creazione 2024: il talento d'Origine (di solito quello del background). Si può saltare e aggiungere dopo. */
export default function OriginFeatStep({ value, onChange }: Props) {
  const { t, i18n } = useTranslation()
  const items = featsFor(null, '2024', 'creation', uiLang(i18n.language))
  return (
    <div className="space-y-3">
      <p className="text-xs font-body text-dnd-text-muted">{t('character.feats.origin_hint')}</p>
      <FeatChoiceList items={items} value={value ?? ''} onPick={(key) => onChange(key)} />
      <Pressable
        onClick={() => onChange(null)}
        className={`w-full min-h-[44px] rounded-xl border text-sm font-body ${
          value === null ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text-muted'
        }`}
      >
        {t('character.feats.origin_skip')}
      </Pressable>
    </div>
  )
}
