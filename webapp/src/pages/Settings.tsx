import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Settings2, Languages, RefreshCw, Eye, Sun, History, Coins, Trash2, BookmarkCheck, Bell } from 'lucide-react'
import {
  GiSparkles as Sparkles, GiCutDiamond as Gem,
  GiPerspectiveDiceSixFacesRandom as Dices,
} from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import SectionDivider from '@/components/ui/SectionDivider'
import SwitchToggle from '@/components/ui/SwitchToggle'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { FlagIT, FlagEN } from '@/components/ui/Flags'
import { haptic } from '@/auth/telegram'
import { useCharacterStore } from '@/store/characterStore'
import { useDiceSettings } from '@/store/diceSettings'
import { useThemeSettings, type ThemeMode } from '@/store/themeSettings'
import { useUnitSettings, type UnitSystem } from '@/store/unitSettings'
import { BUNDLED_PACKS, PACK_PREVIEW, type PackId } from '@/dice/packs/registry'
import { loadManifest } from '@/dice/packs/loader'
import { useDicePack } from '@/dice/packs/dicePackContext'
import { spring } from '@/styles/motion'

type RetentionMode = 'off' | 'events' | 'days'
const RETENTION_MODES: readonly RetentionMode[] = ['off', 'events', 'days'] as const

function D20Thumb({ body, accent, active }: { body: string; accent: string; active: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="24"
      height="24"
      aria-hidden
      className="shrink-0"
      style={{
        filter: active
          ? 'drop-shadow(0 0 4px var(--dnd-gold-glow))'
          : 'drop-shadow(0 1px 2px rgba(0,0,0,0.35))',
      }}
    >
      <polygon
        points="12,2 22,8 22,16 12,22 2,16 2,8"
        fill={body}
        stroke={accent}
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <polygon
        points="12,5 18,9 12,13 6,9"
        fill="none"
        stroke={accent}
        strokeOpacity="0.55"
        strokeWidth="0.8"
      />
      <text
        x="12"
        y="17.5"
        textAnchor="middle"
        fontSize="6"
        fontWeight="700"
        fill={accent}
        fontFamily="Cinzel, serif"
      >
        20
      </text>
    </svg>
  )
}

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
  const themeMode = useThemeSettings((s) => s.mode)
  const setThemeMode = useThemeSettings((s) => s.setMode)
  const unitSystem = useUnitSettings((s) => s.system)
  const setUnitSystem = useUnitSettings((s) => s.setSystem)
  const { loading: packLoading, error: packError } = useDicePack()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  // Read retention thresholds from settings (falling back to defaults) so the
  // preview reflects the same caps used by the backend prune.
  const charSettings = ((char as { settings?: Record<string, unknown> } | undefined)?.settings as
    | Record<string, unknown>
    | undefined) ?? {}
  const retentionEventsParam = Math.max(1, Number(charSettings.history_retention_events ?? 100) || 100)
  const retentionDaysParam = Math.max(1, Number(charSettings.history_retention_days ?? 30) || 30)

  const { data: retentionPreview } = useQuery({
    queryKey: ['history-retention-preview', charId, retentionEventsParam, retentionDaysParam],
    queryFn: () => api.history.retentionPreview(charId, retentionEventsParam, retentionDaysParam),
    enabled: !!char,
    refetchOnWindowFocus: false,
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
  const [showSlotModeConfirm, setShowSlotModeConfirm] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  // Tetto preparazione manuale: input mai precompilato (placeholder only).
  const [prepCapInput, setPrepCapInput] = useState('')

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
  const spellcasting = char.spellcasting ?? null
  const prepCapMode = (settings.prepared_cap_mode as string) ?? 'auto'
  const hpAutoCalc = (settings.hp_auto_calc as boolean | undefined) !== false
  const showPrivateIdentity = (settings.show_private_identity as boolean | undefined) === true
  const hideElectrum = (settings.hide_electrum as boolean | undefined) === true
  const retentionMode = ((settings.history_retention_mode as RetentionMode | undefined) ?? 'off') as RetentionMode
  const retentionEvents = Number(settings.history_retention_events ?? 100)
  const retentionDays = Number(settings.history_retention_days ?? 30)
  const notifPrefs = (settings.notifications as Record<string, boolean> | undefined) ?? {}

  const toggleLanguage = () => {
    const newLang = locale === 'it' ? 'en' : 'it'
    setLocale(newLang)
    i18n.changeLanguage(newLang)
  }

  const applySlotMode = (mode: 'auto' | 'manual') => {
    if (mode === 'auto' && slotsMode === 'manual') {
      setShowSlotModeConfirm(true)
      return
    }
    updateMutation.mutate({ ...settings, spell_slots_mode: mode })
  }

  const confirmManualToAuto = () => {
    updateMutation.mutate({ ...settings, spell_slots_mode: 'auto' })
    setShowSlotModeConfirm(false)
  }

  const confirmReset = () => {
    updateMutation.mutate({})
    setShowResetConfirm(false)
  }

  return (
    <Layout title={t('character.settings.title')} backTo={`/char/${charId}`}>
      <SectionDivider icon={<Settings2 size={11} />} align="center">
        {t('character.settings.preferences')}
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
            <span className="inline-flex items-center gap-1.5">
              {locale === 'it' ? <FlagIT size={14} /> : <FlagEN size={14} />}
              {locale === 'it' ? 'Italiano' : 'English'}
            </span>
          </Button>
        </div>
      </Surface>

      <Surface variant="elevated">
        <div className="flex items-start gap-3 mb-3">
          <Sun size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-display font-bold text-dnd-gold-bright">
              {t('character.settings.theme.title')}
            </p>
            <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
              {t('character.settings.theme.hint')}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {(['auto', 'light', 'dark'] as const satisfies readonly ThemeMode[]).map((mode) => (
            <m.button
              key={mode}
              type="button"
              aria-pressed={themeMode === mode}
              onClick={() => {
                setThemeMode(mode)
                haptic.light()
              }}
              className={`min-h-[44px] rounded-xl font-cinzel text-xs uppercase tracking-widest transition-colors
                ${themeMode === mode
                  ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                  : 'bg-dnd-surface border border-dnd-border text-dnd-text-muted'}`}
              whileTap={{ scale: 0.96 }}
              transition={spring.press}
            >
              {t(`character.settings.theme.mode_${mode}`)}
            </m.button>
          ))}
        </div>
      </Surface>

      <Surface variant="elevated">
        <SwitchToggle
          icon={<Dices size={16} />}
          label={t('character.settings.dice_3d')}
          hint={t('character.settings.dice_3d_hint')}
          checked={animate3d}
          onChange={setAnimate3d}
        />
      </Surface>

      {/* Measurement unit system — affects length displays (speed, ranges). */}
      <Surface variant="elevated">
        <div className="flex items-start gap-3 mb-3">
          <Settings2 size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-display font-bold text-dnd-gold-bright">
              {t('character.settings.unit_system', { defaultValue: 'Sistema di misura' })}
            </p>
            <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
              {t('character.settings.unit_system_hint', {
                defaultValue: 'Distanze in piedi/metri e pesi in libbre/chili (5 ft ≈ 1,5 m · 1 lb = 0,5 kg).',
              })}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(['imperial', 'metric'] as const satisfies readonly UnitSystem[]).map((mode) => (
            <m.button
              key={mode}
              type="button"
              aria-pressed={unitSystem === mode}
              onClick={() => {
                setUnitSystem(mode)
                haptic.light()
              }}
              className={`min-h-[44px] rounded-xl font-cinzel text-xs uppercase tracking-widest transition-colors
                ${unitSystem === mode
                  ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                  : 'bg-dnd-surface border border-dnd-border text-dnd-text-muted'}`}
              whileTap={{ scale: 0.96 }}
              transition={spring.press}
            >
              {mode === 'imperial'
                ? t('character.settings.unit_imperial', { defaultValue: 'Piedi & libbre' })
                : t('character.settings.unit_metric', { defaultValue: 'Metri & chili' })}
            </m.button>
          ))}
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
            {BUNDLED_PACKS.map((id) => {
              const selected = packId === id
              const preview = PACK_PREVIEW[id]
              return (
                <label
                  key={id}
                  className="flex items-center gap-2 min-h-[44px] cursor-pointer text-sm font-body text-dnd-text"
                >
                  <input
                    type="radio"
                    name="dice-pack"
                    value={id}
                    checked={selected}
                    onChange={() => setPackId(id)}
                    disabled={!animate3d}
                    className="sr-only"
                  />
                  <span
                    aria-hidden
                    className={`relative w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors
                      ${selected
                        ? 'bg-dnd-gold border-dnd-gold-bright shadow-[0_0_6px_var(--dnd-gold-glow)]'
                        : 'border-dnd-border'}`}
                  >
                    {selected && <span className="w-2 h-2 rounded-full bg-dnd-ink" />}
                  </span>
                  <D20Thumb body={preview.body} accent={preview.accent} active={selected} />
                  <span>{packNames?.[id] ?? id}</span>
                </label>
              )
            })}
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

      {/* Telegram game notifications — per-category opt-out (BE: telegram_notify) */}
      <SectionDivider icon={<Bell size={11} />} align="center">
        {t('character.settings.notifications.title')}
      </SectionDivider>

      <Surface variant="elevated" className="space-y-3">
        {(['party_emergency', 'gm_events', 'level_up', 'encounter'] as const).map((key) => (
          <SwitchToggle
            key={key}
            icon={<Bell size={16} />}
            label={t(`character.settings.notifications.${key}`)}
            hint={t(`character.settings.notifications.${key}_hint`)}
            checked={notifPrefs[key] !== false}
            onChange={(next) =>
              updateMutation.mutate({
                ...settings,
                notifications: { ...notifPrefs, [key]: next },
              })
            }
          />
        ))}
      </Surface>

      {/* Currency preferences — hide Electrum toggle */}
      <SectionDivider icon={<Coins size={11} />} align="center">
        {t('character.settings.currency_group')}
      </SectionDivider>

      <Surface variant="elevated">
        <SwitchToggle
          checked={!hideElectrum}
          onChange={(next) => updateMutation.mutate({ ...settings, hide_electrum: !next })}
          icon={<Coins size={16} />}
          label={t('character.settings.currency_show_electrum')}
          hint={t('character.settings.currency_show_electrum_hint')}
        />
      </Surface>

      {/* History retention */}
      <SectionDivider icon={<History size={11} />} align="center">
        {t('character.settings.history_group')}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="flex items-start gap-3 mb-3">
          <History size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-display font-bold text-dnd-gold-bright">
              {t('character.settings.history_retention')}
            </p>
            <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">
              {t('character.settings.history_retention_hint')}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {RETENTION_MODES.map((mode) => {
            const selected = retentionMode === mode
            const label =
              mode === 'off' ? t('character.settings.history_retention_off')
              : mode === 'events' ? t('character.settings.history_retention_events', { n: retentionEvents })
              : t('character.settings.history_retention_days', { n: retentionDays })
            return (
              <m.button
                key={mode}
                type="button"
                onClick={() => updateMutation.mutate({ ...settings, history_retention_mode: mode })}
                className={`min-h-[44px] rounded-xl px-2 font-cinzel text-[10px] uppercase tracking-widest transition-colors
                  ${selected
                    ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                    : 'bg-dnd-surface border border-dnd-border text-dnd-text-muted'}`}
                whileTap={{ scale: 0.96 }}
                transition={spring.press}
              >
                {label}
              </m.button>
            )
          })}
        </div>
        {/* Retention purge preview — shows what each mode would delete now,
            so users can decide before committing the change (U080). */}
        {retentionPreview && retentionPreview.total > 0 && (
          <div className="mt-3 space-y-1 text-[11px] text-dnd-text-muted font-body italic leading-snug">
            <p>
              {t('character.settings.history_retention_total', {
                n: retentionPreview.total,
                defaultValue: 'Cronologia attuale: {{n}} voci.',
              })}
            </p>
            <p
              className={
                retentionPreview.would_purge_events > 0
                  ? 'text-[var(--dnd-crimson-bright)]'
                  : ''
              }
            >
              {t('character.settings.history_retention_preview_events', {
                n: retentionPreview.would_purge_events,
                keep: retentionEvents,
                defaultValue:
                  'Ultimi {{keep}} eventi: perderai {{n}} voci più vecchie ora.',
              })}
            </p>
            <p
              className={
                retentionPreview.would_purge_days > 0
                  ? 'text-[var(--dnd-crimson-bright)]'
                  : ''
              }
            >
              {t('character.settings.history_retention_preview_days', {
                n: retentionPreview.would_purge_days,
                days: retentionDays,
                defaultValue:
                  'Ultimi {{days}} giorni: perderai {{n}} voci precedenti.',
              })}
            </p>
          </div>
        )}
      </Surface>

      <SectionDivider icon={<RefreshCw size={11} />} align="center">
        {t('character.settings.hp.title')}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="space-y-3">
          <SwitchToggle
            checked={hpAutoCalc}
            onChange={(next) => updateMutation.mutate({ ...settings, hp_auto_calc: next })}
            label={t('character.settings.hp.auto_calc_toggle')}
            hint={t('character.settings.hp.auto_calc_hint')}
          />

          <button
            type="button"
            onClick={() => setShowRecalcConfirm(true)}
            className="w-full inline-flex items-center justify-center gap-2 min-h-[44px] px-3 py-2 rounded-xl bg-dnd-surface border border-[var(--dnd-crimson-bright)]/40 text-[var(--dnd-crimson-bright)] text-sm font-body"
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
        <SwitchToggle
          checked={showPrivateIdentity}
          onChange={(next) => updateMutation.mutate({ ...settings, show_private_identity: next })}
          icon={<Eye size={16} />}
          label={t('character.settings.privacy.show_private_label')}
          hint={t('character.settings.privacy.show_private_hint')}
        />
      </Surface>

      {/* Advanced — spell slots mode (Auto/Manual). Less commonly toggled than
          language/theme, so kept near the bottom per U082. */}
      <SectionDivider icon={<Gem size={11} />} align="center">
        {t('character.settings.spell_slots_mode')}
      </SectionDivider>

      <Surface variant="elevated">
        <div className="flex items-start gap-3 mb-3">
          <Sparkles size={16} className="text-dnd-arcane-bright shrink-0 mt-0.5" />
          <p className="text-xs text-dnd-text-muted font-body italic flex-1">
            {slotsMode === 'auto'
              ? t('character.settings.mode_auto_hint')
              : t('character.settings.mode_manual_hint')}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(['auto', 'manual'] as const).map((mode) => (
            <m.button
              key={mode}
              onClick={() => applySlotMode(mode)}
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

      {/* Tetto preparazione incantesimi: solo per PG con classi preparanti. */}
      {spellcasting?.has_preparing_class && (
        <>
          <SectionDivider icon={<BookmarkCheck size={11} />} align="center">
            {t('character.settings.prepared_cap')}
          </SectionDivider>

          <Surface variant="elevated">
            <div className="flex items-start gap-3 mb-3">
              <BookmarkCheck size={16} className="text-dnd-gold-bright shrink-0 mt-0.5" />
              <p className="text-xs text-dnd-text-muted font-body italic flex-1">
                {prepCapMode === 'auto'
                  ? t('character.settings.prepared_cap_auto_hint', { cap: spellcasting.prepared_cap ?? 0 })
                  : t('character.settings.prepared_cap_manual_hint')}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(['auto', 'manual'] as const).map((mode) => (
                <m.button
                  key={mode}
                  onClick={() => updateMutation.mutate({ ...settings, prepared_cap_mode: mode })}
                  className={`min-h-[44px] rounded-xl font-cinzel text-xs uppercase tracking-widest transition-colors
                    ${prepCapMode === mode
                      ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                      : 'bg-dnd-surface border border-dnd-border text-dnd-text-muted'}`}
                  whileTap={{ scale: 0.96 }}
                  transition={spring.press}
                >
                  {t(`character.settings.mode_${mode}`)}
                </m.button>
              ))}
            </div>
            {prepCapMode === 'manual' && (
              <div className="flex gap-2 mt-3">
                <input
                  type="number"
                  min={1}
                  inputMode="numeric"
                  value={prepCapInput}
                  onChange={(e) => setPrepCapInput(e.target.value)}
                  placeholder={t('character.settings.prepared_cap_value_placeholder', {
                    cap: spellcasting.prepared_cap ?? 0,
                  })}
                  className="flex-1 min-w-0 bg-dnd-surface border border-dnd-border rounded-xl px-3 py-2 text-sm font-mono"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!prepCapInput || Number(prepCapInput) < 1}
                  onClick={() => {
                    updateMutation.mutate({
                      ...settings,
                      prepared_cap_mode: 'manual',
                      prepared_cap_value: Number(prepCapInput),
                    })
                    setPrepCapInput('')
                  }}
                >
                  {t('character.settings.prepared_cap_save')}
                </Button>
              </div>
            )}
          </Surface>
        </>
      )}

      {/* Reset all character settings */}
      <Button
        variant="danger"
        size="md"
        fullWidth
        icon={<Trash2 size={16} />}
        onClick={() => setShowResetConfirm(true)}
        haptic="warning"
      >
        {t('character.settings.reset_settings')}
      </Button>

      <ConfirmSheet
        open={showRecalcConfirm}
        onClose={() => setShowRecalcConfirm(false)}
        title={t('character.settings.hp.recalc_confirm_title')}
        body={t('character.settings.hp.recalc_confirm_body')}
        confirmLabel={t('common.confirm')}
        cancelLabel={t('common.cancel')}
        confirmVariant="danger"
        loading={recalcMutation.isPending}
        onConfirm={() => {
          recalcMutation.mutate()
          setShowRecalcConfirm(false)
        }}
      />

      <ConfirmSheet
        open={showSlotModeConfirm}
        onClose={() => setShowSlotModeConfirm(false)}
        title={t('character.settings.manual_to_auto_warn_title')}
        body={t('character.settings.manual_to_auto_warn_body')}
        confirmLabel={t('common.confirm')}
        cancelLabel={t('common.cancel')}
        confirmVariant="primary"
        onConfirm={confirmManualToAuto}
      />

      <ConfirmSheet
        open={showResetConfirm}
        onClose={() => setShowResetConfirm(false)}
        title={t('character.settings.reset_settings')}
        body={t('character.settings.reset_settings_confirm')}
        confirmLabel={t('common.confirm')}
        cancelLabel={t('common.cancel')}
        confirmVariant="danger"
        onConfirm={confirmReset}
      />
    </Layout>
  )
}
