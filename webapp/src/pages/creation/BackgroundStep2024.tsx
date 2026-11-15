import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BookOpen } from 'lucide-react'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import { featByKey } from '@/lib/feats'
import { uiLang } from '@/lib/lang'
import { localized } from '@/lib/srd/catalog'
import { increasesValid, type Background2024Choice } from '@/lib/species'
import { toolLabel } from '@/lib/tools'

interface Props {
  value: Background2024Choice | null
  onChange: (v: Background2024Choice | null) => void
}

const chip = (on: boolean) =>
  `min-h-[44px] min-w-[44px] px-3 rounded-xl border text-sm font-body font-semibold tabular-nums ${
    on ? '!border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright' : 'border-dnd-border text-dnd-text'}`
const label = 'text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5'

/** Creazione 2024: background dal catalogo, aumenti (+2/+1 o +1/+1/+1), strumento, pacchetto o monete. */
export default function BackgroundStep2024({ value, onChange }: Props) {
  const { t, i18n } = useTranslation()
  const lang = uiLang(i18n.language)
  const [picking, setPicking] = useState(false)
  const bg = value?.entry
  const feat = bg ? featByKey(bg.origin_feat) : undefined

  return (
    <div className="space-y-3">
      <p className="text-xs text-dnd-text-faint font-body italic text-center">{t('character.create.bg_hint')}</p>
      <Button variant="secondary" fullWidth icon={<BookOpen size={16} />} onClick={() => setPicking(true)}>
        {bg ? localized(bg.name, lang).text : t('character.create.background_pick')}
      </Button>

      {value && bg && (
        <>
          <div className="rounded-xl border border-dnd-border bg-dnd-surface p-3 text-sm font-body space-y-1">
            <p>
              <span className="text-dnd-text-muted">{t('character.create.bg_origin_feat')}: </span>
              <span className="font-semibold text-dnd-gold-bright">{feat?.name[lang] ?? bg.origin_feat}</span>
            </p>
            <p>
              <span className="text-dnd-text-muted">{t('character.create.bg_skills')}: </span>
              {bg.skills.map((s) => t(`character.skills.${s}`)).join(', ')}
            </p>
            {typeof bg.tool === 'string' && (
              <p>
                <span className="text-dnd-text-muted">{t('character.create.bg_tool')}: </span>
                {toolLabel(bg.tool, lang)}
              </p>
            )}
          </div>

          {Array.isArray(bg.tool) && (
            <div role="group" aria-label={t('character.create.bg_tool')}>
              <p className={label}>{t('character.create.bg_tool')}</p>
              <div className="flex flex-wrap gap-2">
                {bg.tool.map((k) => (
                  <Pressable key={k} aria-pressed={value.tool === k} onClick={() => onChange({ ...value, tool: k })} className={chip(value.tool === k)}>
                    {toolLabel(k, lang)}
                  </Pressable>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className={label}>{t('character.create.bg_increases')}</p>
            <div className="space-y-2">
              {bg.abilities.map((a) => (
                <div key={a} role="group" aria-label={t(`common.abilities.${a}`)} className="flex items-center gap-2">
                  <span className="flex-1 min-w-0 truncate text-sm font-body text-dnd-text">{t(`common.abilities.${a}`)}</span>
                  {[0, 1, 2].map((n) => (
                    <Pressable
                      key={n}
                      aria-pressed={(value.increases[a] ?? 0) === n}
                      onClick={() => onChange({ ...value, increases: { ...value.increases, [a]: n } })}
                      className={chip((value.increases[a] ?? 0) === n)}
                    >
                      {n ? `+${n}` : '0'}
                    </Pressable>
                  ))}
                </div>
              ))}
            </div>
            {!increasesValid(value.increases) && (
              <p className="mt-1.5 text-xs font-body text-dnd-crimson-bright">{t('character.create.bg_increases_invalid')}</p>
            )}
          </div>

          <div role="group" aria-label={t('character.create.bg_equipment')}>
            <p className={label}>{t('character.create.bg_equipment')}</p>
            <div className="grid grid-cols-2 gap-2">
              {(['pack', 'gold'] as const).map((eq) => (
                <Pressable key={eq} aria-pressed={value.equipment === eq} onClick={() => onChange({ ...value, equipment: eq })} className={chip(value.equipment === eq)}>
                  {t(`character.create.bg_${eq}`)}
                </Pressable>
              ))}
            </div>
          </div>

          <Pressable onClick={() => onChange(null)} className="min-h-[44px] text-xs text-dnd-gold-dim underline underline-offset-2">
            {t('character.create.bg_clear')}
          </Pressable>
        </>
      )}

      {picking && (
        <CatalogPicker
          kind="backgrounds-2024"
          onClose={() => setPicking(false)}
          onPick={(e) => {
            onChange({ entry: e, increases: Object.fromEntries(e.abilities.map((a) => [a, 1])), tool: null, equipment: 'pack' })
            setPicking(false)
          }}
        />
      )}
    </div>
  )
}
