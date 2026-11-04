import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { RotateCcw, Save } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import { ShieldEmblem } from '@/components/ui/Ornament'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import ArmorClassSkeleton from '@/components/skeletons/ArmorClassSkeleton'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useIsFirstValue } from '@/hooks/useIsFirstValue'
import { LEDGER_LABEL, LEDGER_TITLE } from '@/styles/ledger'

const AC_BADGE_GOLD = 'border-dnd-chip-border bg-dnd-chip-bg text-dnd-gold-bright'
const AC_BADGE_AMBER = 'border-dnd-amber/50 bg-dnd-amber/10 text-dnd-amber'

type AcRow = {
  key: string
  label: string
  title?: string
  current: number
  draft: string
  setDraft: (v: string) => void
  disabled?: boolean
  badge?: { text: string; tone: string } | null
}

export default function ArmorClass() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const reduceMotion = useReducedMotion()

  const [base, setBase] = useState('')
  const [shield, setShield] = useState('')
  const [magic, setMagic] = useState('')

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })
  // Pop del valore solo quando CAMBIA, non all'ingresso nella pagina.
  const isFirstValue = useIsFirstValue(char)

  const mutation = useMutation({
    mutationFn: () =>
      api.characters.updateAC(charId, {
        base: base !== '' ? Number(base) : undefined,
        shield: shield !== '' ? Number(shield) : undefined,
        magic: magic !== '' ? Number(magic) : undefined,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setBase('')
      setShield('')
      setMagic('')
      haptic.success()
    },
  })

  const resetOverrideMutation = useMutation({
    mutationFn: () => api.characters.resetACOverride(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setBase('')
      setShield('')
      haptic.success()
    },
  })

  const unarmoredMutation = useMutation({
    mutationFn: (ability: 'wisdom' | 'constitution' | null) =>
      api.characters.setUnarmoredDefense(charId, ability),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setBase('')
      haptic.success()
    },
  })

  if (!char) {
    return (
      <Layout title={t('character.ac.title')} backTo={`/char/${charId}`} group="combat" page="ac">
        <ArmorClassSkeleton />
      </Layout>
    )
  }

  // Come `_worn` del backend: un'armatura legacy senza slot conta ancora come indossata.
  const wornArmor = char.items?.filter((i) => i.is_equipped && i.item_type === 'armor') ?? []
  const equippedBodyArmor = wornArmor.find((i) => i.equipment_slot) ?? wornArmor[0] ?? null
  const equippedShield = char.items?.find(
    (i) => i.is_equipped && i.equipment_slot === 'off_hand' && i.item_type === 'shield',
  ) ?? null

  const unarmoredAbility = char.unarmored_defense_ability ?? null
  const unarmoredActive = unarmoredAbility !== null
  const abilityMod = (name: string) => char.ability_scores?.find((a) => a.name === name)?.modifier ?? 0
  // Come il backend: mai peggio di 10 + DES, anche con la seconda caratteristica negativa.
  const unarmoredPreview = (ability: 'wisdom' | 'constitution') =>
    10 + abilityMod('dexterity') + Math.max(0, abilityMod(ability))

  const baseHint = char.base_armor_class_override
    ? null
    : equippedBodyArmor
      ? t('character.ac.auto_from_armor_hint', { name: equippedBodyArmor.name })
      : char.unarmored_formula ? null : t('character.ac.auto_no_armor_hint')

  const isDirty = base !== '' || shield !== '' || magic !== ''
  const hbAc = char.ac_breakdown?.homebrew ?? 0
  const itemsAc = char.ac_breakdown?.items ?? 0
  const acTotal = char.ac + hbAc + itemsAc
  const previewBase = base !== '' ? Number(base) : char.base_armor_class
  const previewShield = shield !== '' ? Number(shield) : char.shield_armor_class
  const previewMagic = magic !== '' ? Number(magic) : char.magic_armor
  const previewTotal = previewBase + previewShield + previewMagic + hbAc + itemsAc

  return (
    <Layout title={t('character.ac.title')} backTo={`/char/${charId}`} group="combat" page="ac">
      {isDirty && (
        <Surface
          variant="ember"
          className="sticky top-[calc(var(--crumb-offset,0px)+0.5rem)] z-20 flex items-center justify-between gap-3 !py-2.5 !px-3"
        >
          <span className="text-xs font-body text-dnd-text">
            {t('character.identity.unsaved_changes')}
          </span>
          <Button
            variant="primary"
            size="sm"
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            icon={<Save size={14} />}
            haptic="success"
          >
            {t('character.identity.save_now')}
          </Button>
        </Surface>
      )}

      {/* Hero AC */}
      <div>
        <div className="flex flex-col items-center pb-1">
          <div className="relative flex items-center justify-center">
            <m.div
              initial={reduceMotion ? false : { rotate: -3, opacity: 0.6 }}
              animate={reduceMotion ? {} : { rotate: 0, opacity: 1 }}
              transition={reduceMotion ? undefined : { duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
              className="drop-shadow-[0_8px_24px_var(--dnd-gold-glow)]"
            >
              <ShieldEmblem size={150} />
            </m.div>
            <m.span
              key={acTotal}
              initial={isFirstValue ? false : { scale: 0.6, opacity: 0 }}
              animate={{ scale: [0.6, 1.15, 1], opacity: 1 }}
              transition={spring.elastic}
              className="absolute pb-2 font-display font-black text-dnd-gold-bright leading-none"
              style={{
                fontSize: '3.5rem',
                textShadow: '0 2px 8px var(--dnd-gold-glow), 0 0 2px rgba(0,0,0,0.6)',
              }}
            >
              {acTotal}
            </m.span>
          </div>

          <p className="text-sm text-dnd-text-muted font-mono tabular-nums mt-1">
            {char.base_armor_class} + {char.shield_armor_class} + {char.magic_armor}
          </p>
          <p className="text-xs text-dnd-text-muted font-cinzel uppercase tracking-wider mt-0.5">
            {t('character.ac.legend')}
          </p>
        </div>
        <HomebrewBreakdownRow value={char.ac_breakdown?.homebrew ?? 0} />
        <HomebrewBreakdownRow value={itemsAc} label={t('character.ac.items_label')} />
      </div>

      {/* Registro: voce e stato a sinistra, valore e correzione a destra. */}
      <m.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring.drift, delay: 0.10 }}
        className="border-y border-dnd-border divide-y divide-dnd-border/60"
      >
        {([
          {
            key: 'base',
            label: t('character.ac.base'),
            title: t('character.ac.base_help'),
            current: char.base_armor_class,
            draft: base,
            setDraft: setBase,
            disabled: unarmoredActive && !char.base_armor_class_override,
            badge: char.base_armor_class_override
              ? { text: t('character.ac.manual_override'), tone: AC_BADGE_AMBER }
              : char.unarmored_formula
                ? { text: t('character.ac.unarmored_badge'), tone: AC_BADGE_GOLD }
                : { text: t('character.ac.auto_from_armor'), tone: AC_BADGE_GOLD },
          },
          {
            key: 'shield',
            label: t('character.ac.shield'),
            current: char.shield_armor_class,
            draft: shield,
            setDraft: setShield,
            badge: char.shield_armor_class_override
              ? { text: t('character.ac.manual_override'), tone: AC_BADGE_AMBER }
              : equippedShield ? { text: t('character.ac.auto_from_armor'), tone: AC_BADGE_GOLD } : null,
          },
          {
            key: 'magic',
            label: t('character.ac.magic'),
            current: char.magic_armor,
            draft: magic,
            setDraft: setMagic,
          },
        ] as AcRow[]).map((row) => (
          <div key={row.key} className="flex min-h-[60px] items-center gap-3 px-1 py-2">
            <div className="min-w-0 flex-1">
              <p className={LEDGER_LABEL} title={row.title}>{row.label}</p>
              {row.badge && <span className={`mt-1 inline-block max-w-full truncate rounded-lg border px-1.5 py-px text-xs font-cinzel uppercase tracking-wider ${row.badge.tone}`}>{row.badge.text}</span>}
            </div>
            <span className="font-mono text-lg font-bold tabular-nums text-dnd-text">{row.current}</span>
            <Input
              type="number"
              min={0}
              value={row.draft}
              onChange={row.setDraft}
              placeholder={String(row.current)}
              inputMode="numeric"
              disabled={row.disabled}
              className="w-20 shrink-0 [&_input]:text-base [&_input]:font-mono [&_input]:tabular-nums [&_input]:font-bold [&_input]:text-center"
            />
          </div>
        ))}
      </m.div>

      {baseHint && (
        <p className="text-xs text-dnd-text-faint font-body italic px-2 -mt-1">{baseHint}</p>
      )}

      {(char.base_armor_class_override || char.shield_armor_class_override) && (
        <div className="flex max-xs:flex-col max-xs:items-start items-center justify-between gap-2 px-2 -mt-1">
          <p className="text-xs text-dnd-amber font-body italic flex-1">
            {t('character.ac.manual_override_hint')}
          </p>
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw size={12} />}
            onClick={() => resetOverrideMutation.mutate()}
            loading={resetOverrideMutation.isPending}
            haptic="warning"
          >
            {t('character.ac.reset_to_auto')}
          </Button>
        </div>
      )}

      {/* Unarmored Defense (Monk: WIS, Barbarian: CON) */}
      <section className="space-y-2.5 px-1">
        <h2 className={LEDGER_TITLE}>
          {t('character.ac.unarmored_title')}
        </h2>
        <p className="text-xs text-dnd-text-muted font-body">
          {t('character.ac.unarmored_hint')}
        </p>
        <div className="grid grid-cols-3 gap-2">
          {([
            { key: null, label: t('character.ac.unarmored_off') },
            { key: 'wisdom' as const, label: t('character.ability.wisdom_short'), preview: unarmoredPreview('wisdom') },
            { key: 'constitution' as const, label: t('character.ability.constitution_short'), preview: unarmoredPreview('constitution') },
          ]).map((opt) => {
            const active = unarmoredAbility === opt.key
            return (
              <Pressable
                key={String(opt.key)}
                onClick={() => unarmoredMutation.mutate(opt.key)}
                pending={unarmoredMutation.isPending && unarmoredMutation.variables === opt.key}
                whileTap={{ scale: 0.96 }}
                className={`min-h-[44px] rounded-lg px-2 py-1.5 font-cinzel text-xs uppercase tracking-wider border transition-colors disabled:opacity-50 ${
                  active
                    ? 'bg-dnd-gold/20 text-dnd-gold-bright border-dnd-gold'
                    : 'bg-dnd-surface text-dnd-text-muted border-dnd-border hover:border-dnd-gold/60'
                }`}
                aria-pressed={active}
              >
                <span className="block">{opt.label}</span>
                {opt.preview !== undefined && (
                  <span className="block text-xs font-mono tabular-nums mt-0.5 opacity-80">
                    {t('character.ac.unarmored_formula', { value: opt.preview })}
                  </span>
                )}
              </Pressable>
            )
          })}
        </div>
        {unarmoredActive && (
          <p className="text-xs text-dnd-text-faint font-body italic">
            {t('character.ac.unarmored_active_hint')}
          </p>
        )}
      </section>

      {isDirty && previewTotal !== acTotal && (
        <m.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-center gap-2 px-3 py-2 rounded-full bg-dnd-chip-bg border border-dnd-gold-dim/40 text-dnd-gold-bright text-xs font-cinzel uppercase tracking-widest mx-auto w-fit"
        >
          <span>{t('character.ac.new_total')}:</span>
          <span className="font-mono font-bold tabular-nums text-base">{previewTotal}</span>
        </m.div>
      )}

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending || !isDirty}
        loading={mutation.isPending}
        icon={<Save size={18} />}
        haptic="success"
      >
        {t('common.save')}
      </Button>
    </Layout>
  )
}
