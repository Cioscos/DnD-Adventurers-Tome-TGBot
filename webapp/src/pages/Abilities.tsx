import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Minus, Pencil, Trash2, RotateCcw, ChevronDown } from 'lucide-react'
import { GiLightningTrio as Zap, GiSparkles as Sparkles } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Surface from '@/components/ui/Surface'
import ScrollArea from '@/components/ScrollArea'
import StatPill from '@/components/ui/StatPill'
import EmptyState from '@/components/ui/EmptyState'
import CustomResourceCounter from '@/components/homebrew/CustomResourceCounter'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import type { Ability } from '@/types'
import type { HomebrewResource } from '@/lib/homebrew/types'

type AddForm = { name: string; description: string; max_uses: string; is_passive: boolean; restoration_type: string }
const emptyForm: AddForm = { name: '', description: '', max_uses: '', is_passive: false, restoration_type: 'long_rest' }

// Smart-default lookup: 5e ability names → expected restoration cadence.
// User can always override via the select; this only sets the initial value
// so common picks like "Action Surge" don't require an extra tap.
const SHORT_REST_HINTS = [
  'action surge', 'second wind', 'ki', 'ki points', 'channel divinity',
  'wind rush', 'arcane recovery', 'martial arts', 'flurry of blows',
  'patient defense', 'step of the wind', 'tide of chaos', 'wild shape',
  'bardic inspiration', 'song of rest', 'fontana di magia',
  'recupero magico', 'incanalare la divinità', 'azione impetuosa',
  'secondo fiato', 'punti ki', 'forma selvatica', 'ispirazione bardica',
] as const

const MANUAL_HINTS = [
  'lucky', 'fortuna', 'inspiration', 'ispirazione eroica', 'heroic inspiration',
] as const

function detectRestoration(name: string): string {
  const lower = name.trim().toLowerCase()
  if (!lower) return 'long_rest'
  if (SHORT_REST_HINTS.some((h) => lower.includes(h))) return 'short_rest'
  if (MANUAL_HINTS.some((h) => lower.includes(h))) return 'manual'
  return 'long_rest'
}

function abilityToForm(ab: Ability): AddForm {
  return {
    name: ab.name,
    description: ab.description ?? '',
    max_uses: ab.max_uses != null ? String(ab.max_uses) : '',
    is_passive: ab.is_passive,
    restoration_type: ab.restoration_type,
  }
}

export default function Abilities() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState<AddForm>(emptyForm)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [editingAbility, setEditingAbility] = useState<Ability | null>(null)
  const [wizardStep, setWizardStep] = useState<'basics' | 'details'>('basics')

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  // Homebrew resources spawned by ResourceDef entries in installed rules.
  // Cache key is shared across the app (e.g. Conditions page may surface the
  // same resources for "depleted" CTAs later) so we don't refetch redundantly.
  const { data: resources } = useQuery({
    queryKey: ['homebrew-resources', charId],
    queryFn: () => api.homebrew.listResources(charId),
  })

  // +/- and restore all funnel through PATCH /resources/{id} (server clamps).
  // Optimistic-ish: we splice the returned row into the cached list rather
  // than invalidating, so the counter updates without a flicker.
  const resourceMutation = useMutation({
    mutationFn: ({ resourceId, current }: { resourceId: number; current: number }) =>
      api.homebrew.patchResource(charId, resourceId, current),
    onSuccess: (updated) => {
      qc.setQueryData<HomebrewResource[]>(['homebrew-resources', charId], (prev) =>
        (prev ?? []).map((r) => (r.id === updated.id ? updated : r)),
      )
    },
  })

  const addMutation = useMutation({
    mutationFn: () =>
      api.abilities.add(charId, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        max_uses: form.max_uses !== '' ? Number(form.max_uses) : undefined,
        uses: form.max_uses !== '' ? Number(form.max_uses) : undefined,
        is_passive: form.is_passive,
        is_active: !form.is_passive,
        restoration_type: form.restoration_type,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      closeForm()
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: () =>
      api.abilities.update(charId, editingAbility!.id, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        max_uses: form.max_uses !== '' ? Number(form.max_uses) : undefined,
        is_passive: form.is_passive,
        is_active: !form.is_passive,
        restoration_type: form.restoration_type,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      closeForm()
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const usesMutation = useMutation({
    mutationFn: ({ abilityId, uses }: { abilityId: number; uses: number }) =>
      api.abilities.update(charId, abilityId, { uses }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (abilityId: number) => api.abilities.remove(charId, abilityId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
  })

  function openAdd() {
    setEditingAbility(null)
    setForm(emptyForm)
    setWizardStep('basics')
    setShowAdd(true)
  }

  function openEdit(ab: Ability) {
    setEditingAbility(ab)
    setForm(abilityToForm(ab))
    setWizardStep('basics')
    setShowAdd(true)
  }

  function closeForm() {
    setShowAdd(false)
    setEditingAbility(null)
    setForm(emptyForm)
    setWizardStep('basics')
  }

  function submitForm() {
    // Client-side validation: max_uses must be a non-negative integer when set.
    // Pydantic validates on the backend too, but failing fast here gives the user
    // an immediate signal instead of a generic API error.
    if (form.max_uses !== '') {
      const n = Number(form.max_uses)
      if (!Number.isFinite(n) || n < 0 || !Number.isInteger(n)) {
        haptic.error()
        return
      }
    }
    if (editingAbility) {
      updateMutation.mutate()
    } else {
      addMutation.mutate()
    }
  }

  if (!char) return null

  const abilities: Ability[] = char.abilities ?? []
  const isPending = addMutation.isPending || updateMutation.isPending

  return (
    <Layout title={t('character.abilities.title')} backTo={`/char/${charId}`} group="skills" page="abilities">
      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={openAdd}
        icon={<Plus size={18} />}
        haptic="medium"
      >
        {t('character.abilities.add')}
      </Button>

      {abilities.length === 0 && (
        <EmptyState
          icon={<Zap size={32} />}
          title={t('common.none')}
          hint={t('character.abilities.empty_hint')}
          action={{
            label: t('character.abilities.add'),
            onClick: openAdd,
            icon: <Plus size={14} />,
          }}
        />
      )}

      <ScrollArea>
        <div className="space-y-2">
          {abilities.map((ab) => {
            const isOpen = expanded === ab.id
            const hasUses = ab.max_uses != null
            const current = ab.uses ?? 0
            const isDepleted = hasUses && current === 0

            return (
              <m.div
                key={ab.id}
                layout
                className={`rounded-2xl border overflow-hidden transition-colors
                  ${ab.is_passive
                    ? 'bg-dnd-surface-raised border-dnd-gold-dim/30'
                    : 'bg-gradient-parchment border-dnd-border'}
                  ${isDepleted ? 'opacity-60' : ''}`}
              >
                <m.button
                  className="w-full flex items-center gap-2 px-3 py-3 text-left"
                  onClick={() => setExpanded(isOpen ? null : ab.id)}
                  whileTap={{ scale: 0.995 }}
                >
                  <span className="flex-1 font-display font-bold text-sm text-dnd-gold-bright">
                    {ab.name}
                  </span>
                  <div className="flex gap-1.5 items-center shrink-0">
                    {ab.is_passive ? (
                      <StatPill tone="cobalt" size="sm" value={t('character.abilities.passive')} />
                    ) : (
                      <StatPill tone="amber" size="sm" value={t('character.abilities.active')} />
                    )}
                    {hasUses && (
                      <span className="flex items-center gap-1">
                        {Array.from({ length: Math.min(ab.max_uses!, 8) }).map((_, i) => (
                          <span
                            key={i}
                            className={`w-2 h-2 rounded-full
                              ${i < current
                                ? 'bg-dnd-gold-bright shadow-[0_0_3px_var(--dnd-gold-glow)]'
                                : 'bg-dnd-gold-dim/40'}`}
                          />
                        ))}
                        <span className="text-[10px] text-dnd-text-faint font-mono tabular-nums ml-1">
                          {current}/{ab.max_uses}
                        </span>
                      </span>
                    )}
                  </div>
                  <m.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                    <ChevronDown size={14} className="text-dnd-text-faint" />
                  </m.div>
                </m.button>

                <AnimatePresence initial={false}>
                  {isOpen && (
                    <m.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.22 }}
                    >
                      <div className="px-3 pb-3 space-y-3 border-t border-dnd-gold-dim/15">
                        {ab.description ? (
                          <p className="text-xs text-dnd-text mt-2.5 whitespace-pre-wrap leading-relaxed font-body italic">
                            {ab.description}
                          </p>
                        ) : (
                          <p className="text-xs text-dnd-text-faint/60 mt-2 italic font-body">—</p>
                        )}

                        {hasUses && (
                          <div className="flex items-center gap-1.5 text-[10px] text-dnd-text-muted font-cinzel uppercase tracking-widest">
                            <RotateCcw size={11} />
                            <span>
                              {t('character.abilities.restoration_label')}:{' '}
                              {t(`character.abilities.restoration_short.${ab.restoration_type}`, {
                                defaultValue: t(`character.abilities.restoration.${ab.restoration_type}`, { defaultValue: ab.restoration_type }),
                              })}
                            </span>
                          </div>
                        )}

                        {hasUses && (
                          <div className="flex items-center gap-3 rounded-xl bg-dnd-surface border border-dnd-border p-2">
                            <m.button
                              onClick={() => usesMutation.mutate({ abilityId: ab.id, uses: Math.max(0, current - 1) })}
                              disabled={current <= 0 || usesMutation.isPending}
                              className="w-11 h-11 rounded-xl bg-[var(--dnd-crimson)]/15 text-[var(--dnd-crimson-bright)] border border-[var(--dnd-crimson)]/30 flex items-center justify-center disabled:opacity-30"
                              whileTap={{ scale: 0.9 }}
                            >
                              <Minus size={16} />
                            </m.button>
                            <div className="flex-1 text-center">
                              <p className="text-lg font-display font-black text-dnd-gold-bright">
                                <span className="font-mono">{current}</span>
                                <span className="text-sm text-dnd-text-muted"> / {ab.max_uses}</span>
                              </p>
                            </div>
                            <m.button
                              onClick={() => usesMutation.mutate({ abilityId: ab.id, uses: Math.min(ab.max_uses!, current + 1) })}
                              disabled={current >= (ab.max_uses ?? 0) || usesMutation.isPending}
                              className="w-11 h-11 rounded-xl bg-[var(--dnd-emerald)]/15 text-[var(--dnd-emerald-bright)] border border-dnd-emerald/30 flex items-center justify-center disabled:opacity-30"
                              whileTap={{ scale: 0.9 }}
                            >
                              <Plus size={16} />
                            </m.button>
                          </div>
                        )}

                        <div className="flex gap-2 pt-1 border-t border-dnd-gold-dim/15">
                          <Button variant="secondary" size="sm" onClick={() => openEdit(ab)} icon={<Pencil size={12} />}>
                            {t('character.abilities.edit')}
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => deleteMutation.mutate(ab.id)}
                            disabled={deleteMutation.isPending}
                            icon={<Trash2 size={12} />}
                          >
                            {t('common.delete')}
                          </Button>
                        </div>
                      </div>
                    </m.div>
                  )}
                </AnimatePresence>
              </m.div>
            )
          })}
        </div>
      </ScrollArea>

      {resources && resources.length > 0 && (
        <Surface variant="elevated" className="mt-3">
          <h3 className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright mb-3">
            {t('character.homebrew.resources.section_title')}
          </h3>
          <div className="space-y-2">
            {resources.map((r) => (
              <CustomResourceCounter
                key={r.id}
                resource={r}
                onDecrement={() =>
                  resourceMutation.mutate({
                    resourceId: r.id,
                    current: Math.max(0, r.current - 1),
                  })
                }
                onIncrement={() =>
                  resourceMutation.mutate({
                    resourceId: r.id,
                    current: Math.min(r.max, r.current + 1),
                  })
                }
                onRestore={() =>
                  resourceMutation.mutate({ resourceId: r.id, current: r.max })
                }
                isPending={resourceMutation.isPending}
              />
            ))}
          </div>
        </Surface>
      )}

      {/* Add/Edit Sheet — 2-step wizard */}
      <Sheet
        open={showAdd}
        onClose={closeForm}
        title={
          (editingAbility ? t('character.abilities.edit') : t('character.abilities.add')) +
          ` · ${wizardStep === 'basics' ? '1' : '2'}/2`
        }
      >
        <div className="p-5 space-y-3">
          {wizardStep === 'basics' && (
            <>
              <Input
                label={t('character.abilities.name_label')}
                value={form.name}
                onChange={(v) =>
                  setForm((f) => {
                    if (editingAbility) return { ...f, name: v }
                    const auto = detectRestoration(v)
                    const stillAtPriorAuto = f.restoration_type === detectRestoration(f.name)
                    return {
                      ...f,
                      name: v,
                      restoration_type: stillAtPriorAuto ? auto : f.restoration_type,
                    }
                  })
                }
                placeholder="Rage, Action Surge, ..."
                autoFocus
              />
              <m.label
                className="flex items-center gap-3 p-3 rounded-xl bg-dnd-surface border border-dnd-border cursor-pointer"
                whileTap={{ scale: 0.98 }}
                transition={spring.press}
              >
                <input
                  type="checkbox"
                  checked={form.is_passive}
                  onChange={(e) => setForm((f) => ({ ...f, is_passive: e.target.checked }))}
                  className="w-5 h-5 accent-[var(--dnd-gold)]"
                />
                <Sparkles size={14} className="text-dnd-gold-bright" />
                <span className="text-sm font-cinzel uppercase tracking-wider text-dnd-gold-bright">
                  {t('character.abilities.passive')}
                </span>
              </m.label>
              <div className="flex gap-2 pt-2">
                <Button
                  variant="primary"
                  fullWidth
                  onClick={() => setWizardStep('details')}
                  disabled={!form.name.trim()}
                  haptic="medium"
                >
                  {t('common.next', { defaultValue: 'Avanti' })}
                </Button>
                <Button variant="secondary" fullWidth onClick={closeForm}>
                  {t('common.cancel')}
                </Button>
              </div>
            </>
          )}

          {wizardStep === 'details' && (
            <>
              <Input
                variant="textarea"
                label={t('character.abilities.description_label')}
                value={form.description}
                onChange={(v) => setForm((f) => ({ ...f, description: v }))}
                rows={3}
              />
              {!form.is_passive && (
                <div className="grid grid-cols-2 gap-2">
                  <Input
                    label={t('character.abilities.max_uses_label')}
                    value={form.max_uses}
                    onChange={(v) => setForm((f) => ({ ...f, max_uses: v }))}
                    type="number"
                    min={0}
                    inputMode="numeric"
                    placeholder="—"
                  />
                  <div>
                    <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
                      {t('character.abilities.restoration_label')}
                    </label>
                    <select
                      value={form.restoration_type}
                      onChange={(e) => setForm((f) => ({ ...f, restoration_type: e.target.value }))}
                      className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text
                                 border-b-2 border-dnd-border outline-none font-body text-sm"
                    >
                      <option value="long_rest">{t('character.abilities.restoration.long_rest')}</option>
                      <option value="short_rest">{t('character.abilities.restoration.short_rest')}</option>
                      <option value="manual">{t('character.abilities.restoration.manual')}</option>
                    </select>
                  </div>
                </div>
              )}
              <div className="flex gap-2 pt-2">
                <Button
                  variant="secondary"
                  onClick={() => setWizardStep('basics')}
                  className="px-4"
                >
                  {t('common.back', { defaultValue: 'Indietro' })}
                </Button>
                <Button
                  variant="primary"
                  fullWidth
                  onClick={submitForm}
                  disabled={!form.name.trim() || isPending}
                  loading={isPending}
                  haptic="success"
                >
                  {editingAbility ? t('common.save') : t('common.add')}
                </Button>
              </div>
            </>
          )}
        </div>
      </Sheet>
    </Layout>
  )
}
