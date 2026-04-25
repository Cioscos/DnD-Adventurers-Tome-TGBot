import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Settings2, Languages, Sparkles, Gem, Dices, RefreshCw, Eye } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import SectionDivider from '@/components/ui/SectionDivider'
import Sheet from '@/components/ui/Sheet'
import { haptic } from '@/auth/telegram'
import { useCharacterStore } from '@/store/characterStore'
import { useDiceSettings } from '@/store/diceSettings'
import { BUNDLED_PACKS, type PackId } from '@/dice/packs/registry'
import { loadManifest } from '@/dice/packs/loader'
import { useDicePack } from '@/dice/packs/DicePackProvider'
import { spring } from '@/styles/motion'

export default function Settings() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const { locale, setLocale } = useCharacterStore()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const setAnimate3d = useDiceSettings((s) => s.setAnimate3d)
  const packId = useDiceSettings((s) => s.packId)
  const setPackId = useDiceSettings((s) => s.setPackId)
  const { loading: packLoading, error: packError } = useDicePack()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const { data: packNames } = useQuery({
    queryKey: ['pack-manifest-names'],
    queryFn: async () => {
      const entries = await Promise.all(
        BUNDLED_PACKS.map(async (id) => [id, (await loadManifest(id)).name] as const),
      )
      return Object.fromEntries(entries) as Record<PackId, string>
    },
    staleTime: Infinity,
  })

  const updateMutation = useMutation({
    mutationFn: (settings: Record<string, unknown>) =>
      api.characters.update(charId, { settings }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const [showRecalcConfirm, setShowRecalcConfirm] = useState(false)

  const recalcMutation = useMutation({
    mutationFn: () => api.characters.recalcHp(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const settings = (char.settings as Record<string, unknown>) ?? {}
  const slotsMode = (settings.spell_slots_mode as string) ?? 'auto'

  const toggleLanguage = () => {
    const newLang = locale === 'it' ? 'en' : 'it'
    setLocale(newLang)
    i18n.changeLanguage(newLang)
  }

  return (
    <Layout title={t('character.settings.title')} backTo={`/char/${charId}`}>
      <SectionDivider icon={<Gem size={11} />} align="center">
        {t('character.settings.spell_slots_mode')}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="flex items-start gap-3 mb-3">
          <Sparkles size={16} className="text-dnd-arcane-bright shrink-0 mt-0.5" />
          <p className="text-xs text-dnd-text-muted font-body italic flex-1">
            {t('character.settings.spell_slots_hint', { defaultValue: 'Auto = dedotto da classi e livello; Manual = controllo manuale' })}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(['auto', 'manual'] as const).map((mode) => (
            <m.button
              key={mode}
              onClick={() => updateMutation.mutate({ ...settings, spell_slots_mode: mode })}
              className={`min-h-[44px] rounded-xl font-cinzel text-xs uppercase tracking-widest transition-colors
                ${slotsMode === mode
                  ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                  : 'bg-dnd-surface border border-dnd-border text-dnd-text-muted'}`}
              whileTap={{ scale: 0.96 }}
              transition={spring.press}
            >
              {t(`character.settings.mode_${mode}`)}
            </m.button>
          ))}
        </div>
      </Surface>

      <SectionDivider icon={<Settings2 size={11} />} align="center">
        {t('character.settings.preferences', { defaultValue: 'Preferenze' })}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Languages size={16} className="text-dnd-gold-bright" />
            <p className="font-display font-bold text-dnd-gold-bright">
              {t('character.settings.language')}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={toggleLanguage}>
            {locale === 'it' ? '🇮🇹 Italiano' : '🇬🇧 English'}
          </Button>
        </div>
      </Surface>

      <Surface variant="elevated">
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1 flex items-start gap-2">
            <Dices size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
            <div>
              <p className="font-display font-bold text-dnd-gold-bright">
                {t('character.settings.dice_3d')}
              </p>
              <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
                {t('character.settings.dice_3d_hint')}
              </p>
            </div>
          </div>
          <m.button
            type="button"
            role="switch"
            aria-checked={animate3d}
            onClick={() => {
              setAnimate3d(!animate3d)
              haptic.light()
            }}
            className={`w-12 h-7 rounded-full transition-colors shrink-0 border flex items-center px-0.5
              ${animate3d
                ? 'bg-gradient-to-r from-dnd-gold-dim to-dnd-gold-bright border-dnd-gold-bright shadow-[0_0_8px_rgba(212,170,90,0.4)] justify-end'
                : 'bg-dnd-surface border-dnd-border justify-start'}`}
            whileTap={{ scale: 0.92 }}
          >
            <m.span
              layout
              transition={spring.snappy}
              className="block w-5 h-5 rounded-full bg-dnd-parchment shadow-parchment-md"
            />
          </m.button>
        </div>
      </Surface>

      <Surface variant="elevated" className={animate3d ? '' : 'opacity-50 pointer-events-none'}>
        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <Dices size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
            <div>
              <p className="font-display font-bold text-dnd-gold-bright">
                {t('character.settings.dice.pack.title')}
              </p>
              <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
                {t('character.settings.dice.pack.description')}
              </p>
            </div>
          </div>
          {!animate3d && (
            <p className="text-xs text-dnd-text-faint italic pl-6">
              {t('character.settings.dice.pack.disabled_hint')}
            </p>
          )}
          <div className="flex flex-col gap-1.5 pl-6 mt-2">
            {BUNDLED_PACKS.map((id) => (
              <label
                key={id}
                className="flex items-center gap-2 cursor-pointer text-sm font-body text-dnd-text"
              >
                <input
                  type="radio"
                  name="dice-pack"
                  value={id}
                  checked={packId === id}
                  onChange={() => setPackId(id)}
                  disabled={!animate3d}
                  className="w-4 h-4"
                />
                <span>{packNames?.[id] ?? id}</span>
              </label>
            ))}
          </div>
          {packLoading && (
            <p className="text-xs text-dnd-text-faint pl-6">…</p>
          )}
          {packError && (
            <p className="text-xs text-[var(--dnd-crimson-bright)] pl-6">
              {t('character.settings.dice.pack.load_error')}
            </p>
          )}
        </div>
      </Surface>

      <SectionDivider icon={<RefreshCw size={11} />} align="center">
        {t('character.settings.hp.title')}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="space-y-3">
          <label className="flex items-center justify-between gap-3 cursor-pointer">
            <div>
              <p className="font-display font-bold text-dnd-gold-bright">
                {t('character.settings.hp.auto_calc_toggle')}
              </p>
              <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
                {t('character.settings.hp.auto_calc_hint')}
              </p>
            </div>
            <input
              type="checkbox"
              checked={(settings.hp_auto_calc as boolean | undefined) !== false}
              onChange={(e) => {
                updateMutation.mutate({ ...settings, hp_auto_calc: e.target.checked })
              }}
              className="w-5 h-5 shrink-0"
            />
          </label>

          <button
            type="button"
            onClick={() => setShowRecalcConfirm(true)}
            className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-dnd-surface border border-[var(--dnd-crimson-bright)]/40 text-[var(--dnd-crimson-bright)] text-sm font-body"
          >
            <RefreshCw size={14} />
            {t('character.settings.hp.recalc')}
          </button>
        </div>
      </Surface>

      <SectionDivider icon={<Eye size={11} />} align="center">
        {t('character.settings.privacy.title')}
      </SectionDivider>

      <Surface variant="elevated">
        <label className="flex items-center justify-between gap-3 cursor-pointer">
          <div className="min-w-0">
            <p className="font-display font-bold text-dnd-gold-bright">
              {t('character.settings.privacy.show_private_label')}
            </p>
            <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
              {t('character.settings.privacy.show_private_hint')}
            </p>
          </div>
          <input
            type="checkbox"
            checked={(settings.show_private_identity as boolean | undefined) === true}
            onChange={(e) =>
              updateMutation.mutate({
                ...settings,
                show_private_identity: e.target.checked,
              })
            }
            className="w-5 h-5 shrink-0"
            aria-label={t('character.settings.privacy.show_private_label')}
          />
        </label>
      </Surface>

      <Sheet
        open={showRecalcConfirm}
        onClose={() => setShowRecalcConfirm(false)}
        title={t('character.settings.hp.recalc_confirm_title')}
      >
        <div className="space-y-4 p-5">
          <p className="text-sm font-body">{t('character.settings.hp.recalc_confirm_body')}</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowRecalcConfirm(false)}
              className="flex-1 px-3 py-2 rounded-xl bg-dnd-surface border border-dnd-border text-sm font-body"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              onClick={() => {
                recalcMutation.mutate()
                setShowRecalcConfirm(false)
              }}
              className="flex-1 px-3 py-2 rounded-xl bg-[var(--dnd-crimson-bright)] text-white text-sm font-bold font-display"
            >
              {t('common.confirm')}
            </button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}
