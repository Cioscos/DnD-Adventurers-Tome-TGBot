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
import { ShieldEmblem } from '@/components/ui/Ornament'
import HomebrewBreakdownRow from '@/components/homebrew/HomebrewBreakdownRow'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { useReducedMotion } from '@/hooks/useReducedMotion'

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
    onError: () => haptic.error(),
  })

  const resetOverrideMutation = useMutation({
    mutationFn: () => api.characters.resetACOverride(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setBase('')
      setShield('')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const equippedBodyArmor = char.items?.find(
    (i) => i.is_equipped && i.equipment_slot === 'body' && i.item_type === 'armor',
  ) ?? null
  const equippedShield = char.items?.find(
    (i) => i.is_equipped && i.equipment_slot === 'off_hand' && i.item_type === 'shield',
  ) ?? null

  const isDirty = base !== '' || shield !== '' || magic !== ''
  const previewBase = base !== '' ? Number(base) : char.base_armor_class
  const previewShield = shield !== '' ? Number(shield) : char.shield_armor_class
  const previewMagic = magic !== '' ? Number(magic) : char.magic_armor
  const previewTotal = previewBase + previewShield + previewMagic

  return (
    <Layout title={t('character.ac.title')} backTo={`/char/${charId}`} group="combat" page="ac">
      {/* Hero AC */}
      <Surface variant="tome" ornamented className="relative overflow-hidden">
        <div className="flex flex-col items-center py-4">
          <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim mb-2">
            {t('character.ac.total')}
          </p>

          <div className="relative flex items-center justify-center">
            <m.div
              initial={reduceMotion ? false : { rotate: -3, opacity: 0.6 }}
              animate={reduceMotion ? {} : { rotate: 0, opacity: 1 }}
              transition={reduceMotion ? undefined : { duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
              className="drop-shadow-[0_8px_24px_var(--dnd-gold-glow)]"
            >
              <ShieldEmblem size={200} />
            </m.div>
            <m.span
              key={char.ac}
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: [0.6, 1.15, 1], opacity: 1 }}
              transition={spring.elastic}
              className="absolute font-display font-black text-dnd-gold-bright leading-none"
              style={{
                fontSize: '4rem',
                textShadow: '0 2px 8px var(--dnd-gold-glow), 0 0 2px rgba(0,0,0,0.6)',
              }}
            >
              {char.ac}
            </m.span>
          </div>

          <p className="text-sm text-dnd-text-muted font-mono mt-3">
            {char.base_armor_class} + {char.shield_armor_class} + {char.magic_armor}
          </p>
          <p className="text-[10px] text-dnd-text-faint font-cinzel uppercase tracking-wider mt-0.5">
            base · shield · magic
          </p>
        </div>
        <HomebrewBreakdownRow value={char.ac_breakdown?.homebrew ?? 0} />
      </Surface>

      {/* Single-row 3-col: Base · Shield · Magic */}
      <m.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring.drift, delay: 0.10 }}
        className="grid grid-cols-3 gap-2"
      >
        <Surface variant="elevated">
          <div className="flex items-center gap-1 flex-wrap">
            <p
              className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim cursor-help"
              title={t('character.ac.base_help', {
                defaultValue: 'Base = 10 + bonus DEX (con cap se armatura media/pesante) oppure valore armatura equipaggiata.',
              })}
            >
              {t('character.ac.base')}
            </p>
            {char.base_armor_class_override ? (
              <span className="text-[8px] font-cinzel uppercase tracking-wider px-1 py-px rounded-full bg-[var(--dnd-crimson-deep)]/30 text-[var(--dnd-crimson-bright)] border border-dnd-crimson/50">
                {t('character.ac.manual_override')}
              </span>
            ) : equippedBodyArmor && (
              <span className="text-[8px] font-cinzel uppercase tracking-wider px-1 py-px rounded-full bg-dnd-gold/20 text-dnd-gold-bright border border-dnd-gold/50">
                {t('character.ac.auto_from_armor')}
              </span>
            )}
          </div>
          <p className="text-2xl font-display font-black text-dnd-gold-bright mt-0.5">
            {char.base_armor_class}
          </p>
          <Input
            type="number"
            min={0}
            value={base}
            onChange={setBase}
            placeholder={String(char.base_armor_class)}
            inputMode="numeric"
            className="mt-2 w-full [&_input]:text-base [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
          />
        </Surface>
        <Surface variant="elevated">
          <div className="flex items-center gap-1 flex-wrap">
            <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">
              {t('character.ac.shield')}
            </p>
            {char.shield_armor_class_override ? (
              <span className="text-[8px] font-cinzel uppercase tracking-wider px-1 py-px rounded-full bg-[var(--dnd-crimson-deep)]/30 text-[var(--dnd-crimson-bright)] border border-dnd-crimson/50">
                {t('character.ac.manual_override')}
              </span>
            ) : equippedShield && (
              <span className="text-[8px] font-cinzel uppercase tracking-wider px-1 py-px rounded-full bg-dnd-gold/20 text-dnd-gold-bright border border-dnd-gold/50">
                {t('character.ac.auto_from_armor')}
              </span>
            )}
          </div>
          <p className="text-2xl font-display font-black text-dnd-gold-bright mt-0.5">
            {char.shield_armor_class}
          </p>
          <Input
            type="number"
            min={0}
            value={shield}
            onChange={setShield}
            placeholder={String(char.shield_armor_class)}
            inputMode="numeric"
            className="mt-2 w-full [&_input]:text-base [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
          />
        </Surface>
        <Surface variant="elevated">
          <p className="font-cinzel text-[10px] uppercase tracking-widest text-dnd-gold-dim">
            {t('character.ac.magic')}
          </p>
          <p className="text-2xl font-display font-black text-dnd-gold-bright mt-0.5">
            {char.magic_armor}
          </p>
          <Input
            type="number"
            min={0}
            value={magic}
            onChange={setMagic}
            placeholder={String(char.magic_armor)}
            inputMode="numeric"
            className="mt-2 w-full [&_input]:text-base [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
          />
        </Surface>
      </m.div>

      {equippedBodyArmor && !char.base_armor_class_override && (
        <p className="text-[10px] text-dnd-text-faint font-body italic px-2 -mt-1">
          {t('character.ac.auto_from_armor_hint', { name: equippedBodyArmor.name })}
        </p>
      )}

      {(char.base_armor_class_override || char.shield_armor_class_override) && (
        <div className="flex items-center justify-between gap-2 px-2 -mt-1">
          <p className="text-[10px] text-[var(--dnd-crimson-bright)] font-body italic flex-1">
            {t('character.ac.manual_override_hint')}
          </p>
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw size={12} />}
            onClick={() => resetOverrideMutation.mutate()}
            disabled={resetOverrideMutation.isPending}
            haptic="warning"
          >
            {t('character.ac.reset_to_auto')}
          </Button>
        </div>
      )}

      {isDirty && previewTotal !== char.ac && (
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
