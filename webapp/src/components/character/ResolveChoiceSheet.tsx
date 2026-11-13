import { uiLang } from '@/lib/lang'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Minus, Plus } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { ABILITY_KEYS, featsFor } from '@/lib/feats'
import FeatChoiceList from '@/components/character/FeatChoiceList'
import { CLASS_NAME_TO_PROGRESSION_KEY } from '@/lib/classProgression'
import type { CharacterFull, PendingChoice, ResolveChoiceBody } from '@/types'

interface Props {
  char: CharacterFull
  choice: PendingChoice
  open: boolean
  onClose: () => void
}

const CAP = 20

const POINTS = 2
const FIELD = 'w-full min-h-[44px] px-3 rounded-xl bg-dnd-surface border border-dnd-border text-sm font-body text-dnd-text'

/** Risolve una scelta di livello: aumento caratteristiche (+2 / +1+1, max 20) o talento. */
export default function ResolveChoiceSheet({ char, choice, open, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = uiLang(i18n.language)
  const qc = useQueryClient()
  const isBoon = choice.kind === 'epic_boon'
  const is2024 = char.rules_edition === '2024'
  const [mode, setMode] = useState<'asi' | 'feat'>(isBoon ? 'feat' : 'asi')
  const [inc, setInc] = useState<Record<string, number>>({})
  const [featKey, setFeatKey] = useState<string>('')
  const [ability, setAbility] = useState('')
  const [customName, setCustomName] = useState('')
  const [customText, setCustomText] = useState('')

  const score = (name: string) => char.ability_scores.find((s) => s.name === name)?.value ?? 10
  const spent = Object.values(inc).reduce((a, b) => a + b, 0)
  // 2014 con testi nei locale; 2024: talenti generali e d'Origine, o i Doni Epici
  const featList = featsFor(char, is2024 || isBoon ? '2024' : '2014', isBoon ? 'boon' : 'level', lang)
  const feat = featList.find((f) => f.key === featKey)
  const taken = new Set((char.abilities ?? []).map((a) => a.feature_key))
  // class_key e' il nome-tabella italiano ("Guerriero"): lo traduciamo nella lingua UI.
  const classEn = Object.entries(CLASS_NAME_TO_PROGRESSION_KEY).find(([, v]) => v === choice.class_key)?.[0]
  const classLabel = classEn ? t(`dnd.classes.${classEn}`, { defaultValue: choice.class_key }) : choice.class_key

  const bump = (name: string, delta: number) => {
    const next = (inc[name] ?? 0) + delta
    if (next < 0 || spent + delta > POINTS || score(name) + next > CAP) return
    haptic.light()
    setInc({ ...inc, [name]: next })
  }

  const mutation = useMutation({
    mutationFn: (body: ResolveChoiceBody) => api.choices.resolve(char.id, choice.id, body),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      qc.invalidateQueries({ queryKey: ['homebrew-rules', char.id] })
      haptic.success()
      onClose()
    },
    onError: () => haptic.error(),
  })

  const canConfirm = mode === 'asi'
    ? spent === POINTS
    : featKey === 'custom'
      ? customName.trim().length > 0
      : featKey !== '' && (!feat?.abilities || ability !== '')

  const confirm = () => {
    const picked = Object.fromEntries(Object.entries(inc).filter(([, v]) => v > 0))
    mutation.mutate(mode === 'asi'
      ? { kind: 'asi', increases: picked }
      : featKey === 'custom'
        ? { kind: 'feat', feat_key: 'custom', custom_name: customName.trim(), custom_text: customText.trim() || null }
        : isBoon
          ? { kind: 'epic_boon', feat_key: featKey, ability: feat?.abilities ? ability : null }
          : { kind: 'feat', feat_key: featKey, ability: feat?.abilities ? ability : null })
  }

  const tab = (m: 'asi' | 'feat', label: string) => (
    <Pressable
      onClick={() => setMode(m)}
      className={`flex-1 min-h-[44px] rounded-xl border text-sm font-body ${
        mode === m ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright' : 'border-dnd-border text-dnd-text-muted'
      }`}
    >
      {label}
    </Pressable>
  )

  return (
    <Sheet open={open} onClose={onClose} title={`${t(isBoon ? 'character.level_choice.epic_boon' : 'character.level_choice.title')} · ${classLabel} ${choice.level}`}>
      <div className="p-5 space-y-3">
        {!isBoon && (
          <div className="flex gap-2">
            {tab('asi', t('character.level_choice.asi'))}
            {tab('feat', t('character.level_choice.feat'))}
          </div>
        )}

        {mode === 'asi' ? (
          <div className="space-y-2">
            <p className="text-xs font-body text-dnd-text-muted">
              {t('character.level_choice.points_left', { n: POINTS - spent })}
            </p>
            {ABILITY_KEYS.map((name) => {
              const label = t(`common.abilities.${name}`)
              return (
                <div key={name} className="flex items-center gap-2">
                  <span className="flex-1 text-sm font-body text-dnd-text">{label}</span>
                  <Pressable
                    onClick={() => bump(name, -1)}
                    disabled={(inc[name] ?? 0) === 0}
                    aria-label={t('character.level_choice.decrease', { name: label })}
                    className="w-11 h-11 flex items-center justify-center rounded-xl border border-dnd-border disabled:opacity-40"
                  >
                    <Minus size={16} />
                  </Pressable>
                  <span className="w-14 text-center font-mono tabular-nums text-sm text-dnd-text">
                    {score(name)}{(inc[name] ?? 0) > 0 && <span className="text-dnd-gold-bright"> +{inc[name]}</span>}
                  </span>
                  <Pressable
                    onClick={() => bump(name, 1)}
                    disabled={spent >= POINTS || score(name) + (inc[name] ?? 0) >= CAP}
                    aria-label={t('character.level_choice.increase', { name: label })}
                    className="w-11 h-11 flex items-center justify-center rounded-xl border border-dnd-border disabled:opacity-40"
                  >
                    <Plus size={16} />
                  </Pressable>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="space-y-2">
            <FeatChoiceList
              items={featList}
              value={featKey}
              onPick={setFeatKey}
              taken={taken}
              ability={ability}
              onAbility={setAbility}
              score={score}
            />
            {!isBoon && (
              <Pressable
                onClick={() => { setFeatKey('custom'); setAbility('') }}
                className={`w-full min-h-[44px] px-3 py-2 rounded-xl border text-left ${
                  featKey === 'custom' ? 'bg-dnd-gold/15 border-dnd-gold' : 'border-dnd-border'
                }`}
              >
                <span className="block text-sm font-body text-dnd-text">{t('character.level_choice.custom')}</span>
              </Pressable>
            )}
            {featKey === 'custom' && (
              <>
                <input
                  type="text"
                  value={customName}
                  maxLength={200}
                  onChange={(e) => setCustomName(e.target.value)}
                  aria-label={t('character.level_choice.custom_name')}
                  placeholder={t('character.level_choice.custom_name')}
                  className={FIELD}
                />
                <textarea
                  value={customText}
                  maxLength={2000}
                  onChange={(e) => setCustomText(e.target.value)}
                  aria-label={t('character.level_choice.custom_text')}
                  placeholder={t('character.level_choice.custom_text')}
                  className={`${FIELD} py-2 min-h-[88px]`}
                />
              </>
            )}
          </div>
        )}

        {mutation.isError && (
          <p className="text-xs font-body text-dnd-crimson-bright">{t('character.level_choice.error')}</p>
        )}
        <Pressable
          onClick={confirm}
          disabled={!canConfirm}
          pending={mutation.isPending}
          className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright disabled:opacity-40"
        >
          {t('character.level_choice.confirm')}
        </Pressable>
      </div>
    </Sheet>
  )
}
