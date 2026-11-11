import ConcentrationSaveDialog from '@/pages/hp/ConcentrationSaveDialog'
import type { ConcentrationSaveResult, RollOption } from '@/api/client'
import { askRollOptions, refreshAfterOptions } from '@/lib/rollOptions'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiHeartPlus, GiCrossedSwords } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ChipSelect from '@/components/ui/ChipSelect'
import DamageTypeControls from '@/components/ui/DamageTypeControls'
import HPGauge from '@/components/ui/HPGauge'
import CharacterHpSecondary from '@/components/character/CharacterHpSecondary'
import HpQuickChips from '@/components/character/HpQuickChips'
import { useReactionOffers } from '@/components/character/ReactionOffers'
import { useAllyReactionWait, allyReductionText } from '@/hooks/useAllyReactionWait'
import {
  applyDamageModifier, damageMultiplier, damagePreviewText, effectiveDamageMods, type DamageModifier,
} from '@/lib/damageModifier'
import { showUndoToast } from '@/components/ui/UndoToast'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import { notifyMutationError } from '@/lib/mutationError'
import { parseCounterInput } from '@/lib/counterInput'
import { sendWithAllyReaction } from '@/lib/allyReactionPatch'
import { zeroHpSaveMessage } from '@/lib/zeroHpSave'
import { damageTakenMessage, sharedDamageMessage } from '@/lib/sharedDamage'
import type { CharacterFull } from '@/types'

interface HpQuickSheetProps {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

/** Mini-sheet Danno/Cura dal tap sulla barra HP in home (spec 2026-07-17).
 *  Riusa PATCH /hp: PF temporanei, concentrazione e death saves restano
 *  governati dal server. La pagina HP completa resta il posto per temp HP,
 *  death saves e riposo. */
export default function HpQuickSheet({ char, open, onClose }: HpQuickSheetProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [op, setOp] = useState<'damage' | 'heal'>('damage')
  const [amount, setAmount] = useState('')
  const [damageType, setDamageType] = useState('')
  const [damageModifier, setDamageModifier] = useState<DamageModifier>(null)
  const [pendingChip, setPendingChip] = useState<number | null>(null)
  const [lostSave, setLostSave] = useState<ConcentrationSaveResult | null>(null)
  // Reazioni che il danno ha aperto (Ritorsione): la scheda resta aperta per proporle.
  const [reactions, setReactions] = useState<RollOption[]>([])

  const offers = useReactionOffers({
    charId: char.id, char, reactions, onSpent: (key) => setReactions((all) => all.filter((r) => r.key !== key)),
  })

  const allyWait = useAllyReactionWait(char.id)

  const hpMutation = useMutation({
    mutationFn: async ({ op, value, modifier }: {
      op: 'damage' | 'heal'; value: number
      modifier?: { damage_modifier?: 'half' | 'double' | 'half_double' | 'none' | 'immune'; raw_value?: number; damage_type?: string }
    }) => {
      const allyId = op === 'damage' ? await allyWait.wait(value, modifier?.damage_type) : null
      const choice = op === 'damage'
        ? await askRollOptions(char.id, { roll: 'damage_taken', damage_type: modifier?.damage_type, damage: value }, 'damage_in')
        : undefined
      const base = choice?.options.length ? { ...modifier, ...choice } : modifier
      const updated = await sendWithAllyReaction(allyId, base, (body) => body
        ? api.characters.updateHp(char.id, op, value, false, body)
        : api.characters.updateHp(char.id, op, value),
      () => toast.warning(t('allyReaction.lost'), { duration: 5000 }))
      if (updated.option_result) {
        refreshAfterOptions(qc, char.id, updated.option_result)
        if (updated.option_result.damage_before != null && updated.option_result.damage_after != null) { // senza riduzione il server non li manda
          toast.info(t('character.roll_options.damage_changed', {
            before: updated.option_result.damage_before, after: updated.option_result.damage_after,
          }))
        }
        const allies = allyReductionText(t, updated.option_result)
        if (allies) toast.info(allies, { duration: 5000 })
      }
      return updated
    },
  })

  // Annulla tramite lo snapshot del server (mai set_current dal client). 409 = i PF
  // sono cambiati nel frattempo; ogni altro errore (rete compresa) usa l'avviso standard.
  const undoMutation = useMutation({
    mutationFn: (opId: string) => api.characters.undoHp(char.id, opId),
    onSuccess: (u) => {
      qc.setQueryData(['character', char.id], u)
      qc.invalidateQueries({ queryKey: ['homebrew-resources', char.id] })
      setReactions([])  // la reazione era del danno annullato
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.hp.undo_stale'))
        qc.invalidateQueries({ queryKey: ['character', char.id] })
      } else {
        notifyMutationError(err)
      }
    },
  })

  // 0 is parsed successfully by parseCounterInput (it only rejects empty/non-numeric
  // input) but is a meaningless damage/heal amount — treat it as invalid here so the
  // Applica button disables consistently with the apply() guard below.
  const parsedAmount = parseCounterInput(amount, null)
  const isAmountInvalid = parsedAmount === null || parsedAmount === 0

  const proposedModifier = damageMultiplier(effectiveDamageMods(char), damageType)
  const effective: DamageModifier = damageModifier ?? (damageType ? proposedModifier : null)
  const showPreview = op === 'damage' && !!effective && effective !== 'none' && !isAmountInvalid

  // Il chip si comporta come il valore scritto a mano: stesso modificatore, stesso annulla.
  const apply = (n: number | null) => {
    if (hpMutation.isPending) return
    if (n === null || n === 0) { haptic.error(); return }
    setPendingChip(n)
    // Come in HP.tsx: l'override dell'utente viaggia esplicito (valore già applicato),
    // altrimenti il server applica le resistenze al tipo.
    const type = op === 'damage' && damageType ? { damage_type: damageType } : {}
    const payload = op === 'damage' && damageModifier
      ? { value: applyDamageModifier(n, damageModifier), modifier: { damage_modifier: damageModifier, raw_value: n, ...type } }
      : { value: n, modifier: 'damage_type' in type ? type : undefined }
    hpMutation.mutate({ op, ...payload }, {
      onSuccess: (updated) => {
        qc.setQueryData(['character', char.id], updated)
        qc.invalidateQueries({ queryKey: ['homebrew-resources', char.id] })
        haptic.success()
        const zeroSave = zeroHpSaveMessage(updated, t)
        if (zeroSave) (zeroSave.ok ? toast.success : toast.warning)(zeroSave.text, { duration: 5000 })
        const shared = sharedDamageMessage(updated, t)
        if (shared) (shared.ok ? toast.info : toast.warning)(shared.text, { duration: 5000 })
        const conc = updated.concentration_save
        if (conc?.lost_concentration) {
          toast.warning(t('character.hp.concentration_lost'), { duration: 4000 })
          setLostSave(conc)
        }
        const undoId = updated.hp_undo_id
        if (undoId) {
          const base = (op === 'damage' ? damageTakenMessage(updated, t) : null) ?? t(op === 'damage' ? 'character.hp.quick_damage_undo' : 'character.hp.quick_heal_undo', { n: updated.option_result?.hp_lost ?? updated.damage_taken ?? n })
          const hasHomebrew = (updated.homebrew_notifications?.length ?? 0) > 0
          showUndoToast({
            message: hasHomebrew ? `${base} · ${t('character.hp.undo_homebrew_note')}` : base,
            actionLabel: t('character.hp.quick_undo_action'),
            onUndo: () => undoMutation.mutate(undoId),
          })
        }
        setAmount('')
        setDamageType('')
        setDamageModifier(null)
        const offered = op === 'damage' ? updated.reactions ?? [] : []
        setReactions(offered)
        if (!offered.length) onClose()
      },
    })
  }

  return (
    <>
    {offers.elements}
    {allyWait.elements}
    {lostSave && <ConcentrationSaveDialog result={lostSave} onClose={() => setLostSave(null)} afterRoll={{ charId: char.id }} />}
    <Sheet open={open} onClose={() => { setReactions([]); onClose() }} title={t('character.hp.quick_sheet_title')}>
      <div className="p-5 space-y-3">
        {offers.card}
        {char.active_form?.own_hp !== false && char.active_form && (
          <div className="text-center space-y-1.5">
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{char.active_form.name}</p>
            <p data-testid="form-hp-primary" className="font-mono tabular-nums">
              <span className="text-2xl font-bold text-dnd-text">{char.active_form.current_hp}/{char.active_form.max_hp}</span>
              {char.active_form.temp_hp > 0 && (
                <span className="ml-1.5 text-sm text-dnd-cobalt-bright">(+{char.active_form.temp_hp})</span>
              )}
            </p>
            <HPGauge
              current={char.active_form.current_hp}
              max={char.active_form.max_hp}
              temp={char.active_form.temp_hp}
              size="sm"
              segmented
            />
            <CharacterHpSecondary char={char} />
            <p className="text-sm font-body text-dnd-emerald-bright">
              {t('character.extras.hp_goes_to_form', { name: char.active_form.name })}
            </p>
          </div>
        )}
        <ChipSelect
          label=""
          options={[
            { value: 'damage', label: t('character.hp.quick_damage') },
            { value: 'heal', label: t('character.hp.quick_heal') },
          ]}
          value={op}
          onChange={(v) => setOp(v as 'damage' | 'heal')}
          columns={2}
        />
        {op === 'damage' && (
          <DamageTypeControls
            damageType={damageType}
            setDamageType={setDamageType}
            damageModifier={damageModifier}
            setDamageModifier={setDamageModifier}
            proposedModifier={proposedModifier}
          />
        )}
        <HpQuickChips
          sign={op === 'damage' ? '−' : '+'}
          pendingVal={hpMutation.isPending ? pendingChip ?? undefined : undefined}
          onPick={(n) => { haptic.light(); apply(n) }}
        />
        <Input
          label={t('character.hp.quick_apply')}
          value={amount}
          onChange={setAmount}
          type="number"
          min={0}
          inputMode="numeric"
          // Solo con mouse/trackpad: su telefono la tastiera automatica ridimensiona la WebView e fa scattare l'hub.
          autoFocus={window.matchMedia?.('(pointer: fine)').matches ?? false}
          placeholder="0"
        />
        {showPreview && (
          <p className="text-center font-mono text-sm tabular-nums text-dnd-cobalt-bright">
            {damagePreviewText(
              damageType && effective ? t(`character.hp.preview_${effective}`) : null,
              parsedAmount,
              applyDamageModifier(parsedAmount, effective),
            )}
          </p>
        )}
        <Button
          variant={op === 'damage' ? 'danger' : 'primary'}
          fullWidth
          size="lg"
          icon={op === 'damage' ? <GiCrossedSwords size={16} /> : <GiHeartPlus size={16} />}
          loading={hpMutation.isPending}
          disabled={isAmountInvalid}
          onClick={() => apply(parsedAmount)}
          haptic="medium"
        >
          {isAmountInvalid
            ? t('character.hp.quick_apply')
            : t(`character.hp.apply_${op}`, { count: op === 'damage' ? applyDamageModifier(parsedAmount, effective) : parsedAmount })}
        </Button>
        <Button
          variant="ghost"
          fullWidth
          onClick={() => { onClose(); navigate(`/char/${char.id}/hp`) }}
        >
          {t('character.hp.go_full_page')}
        </Button>
      </div>
    </Sheet>
    </>
  )
}
