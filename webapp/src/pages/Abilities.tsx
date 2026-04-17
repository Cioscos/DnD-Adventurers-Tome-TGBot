import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Zap, Minus, Pencil, Trash2, RotateCcw, Sparkles, ChevronDown } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ScrollArea from '@/components/ScrollArea'
import StatPill from '@/components/ui/StatPill'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import type { Ability } from '@/types'

type AddForm = { name: string; description: string; max_uses: string; is_passive: boolean; restoration_type: string }
const emptyForm: AddForm = { name: '', description: '', max_uses: '', is_passive: false, restoration_type: 'long_rest' }

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

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
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
    setShowAdd(true)
  }

  function openEdit(ab: Ability) {
    setEditingAbility(ab)
    setForm(abilityToForm(ab))
    setShowAdd(true)
  }

  function closeForm() {
    setShowAdd(false)
    setEditingAbility(null)
    setForm(emptyForm)
  }

  function submitForm() {
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
        <Surface variant="flat" className="text-center py-8">
          <Zap className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('common.none')}</p>
        </Surface>
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
                      <span className="flex items-center gap-0.5">
                        {Array.from({ length: Math.min(ab.max_uses!, 8) }).map((_, i) => (
                          <span
                            key={i}
                            className={`w-1.5 h-1.5 rounded-full
                              ${i < current
                                ? 'bg-dnd-gold-bright shadow-[0_0_3px_var(--dnd-gold-glow)]'
                                : 'bg-dnd-gold-dim/40'}`}
                          />
                        ))}
                        {ab.max_uses! > 8 && (
                          <span className="text-[10px] text-dnd-text-faint font-mono ml-1">
                            {current}/{ab.max_uses}
                          </span>
                        )}
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
                          <p className="text-xs text-dnd-text mt-2.5 whitespace-pre-wrap leading-relaxed border-l-2 border-dnd-gold/50 pl-3 font-body">
                            {ab.description}
                          </p>
                        ) : (
                          <p className="text-xs text-dnd-text-faint/60 mt-2 italic font-body">—</p>
                        )}

                        {hasUses && (
                          <div className="flex items-center gap-1.5 text-[10px] text-dnd-text-muted font-cinzel uppercase tracking-widest">
                            <RotateCcw size={11} />
                            {t(`character.abilities.restoration.${ab.restoration_type}`, { defaultValue: ab.restoration_type })}
                          </div>
                        )}

                        {hasUses && (
                          <div className="flex items-center gap-3 rounded-xl bg-dnd-surface border border-dnd-border p-2">
                            <m.button
                              onClick={() => usesMutation.mutate({ abilityId: ab.id, uses: Math.max(0, current - 1) })}
                              disabled={current <= 0 || usesMutation.isPending}
                              className="w-10 h-10 rounded-xl bg-[var(--dnd-crimson)]/15 text-[var(--dnd-crimson-bright)] border border-[var(--dnd-crimson)]/30 flex items-center justify-center disabled:opacity-30"
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
                              className="w-10 h-10 rounded-xl bg-[var(--dnd-emerald)]/15 text-[var(--dnd-emerald-bright)] border border-dnd-emerald/30 flex items-center justify-center disabled:opacity-30"
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

      {/* Add/Edit Sheet */}
      <Sheet open={showAdd} onClose={closeForm} title={editingAbility ? t('character.abilities.edit') : t('character.abilities.add')}>
        <div className="p-5 space-y-3">
          <Input
            label={t('character.abilities.name_label')}
            value={form.name}
            onChange={(v) => setForm((f) => ({ ...f, name: v }))}
            placeholder="Rage, Action Surge, ..."
            autoFocus
          />
          <Input
            variant="textarea"
            label={t('character.abilities.description_label')}
            value={form.description}
            onChange={(v) => setForm((f) => ({ ...f, description: v }))}
            rows={3}
          />
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
              onClick={submitForm}
              disabled={!form.name.trim() || isPending}
              loading={isPending}
              haptic="success"
            >
              {editingAbility ? t('common.save') : t('common.add')}
            </Button>
            <Button variant="secondary" fullWidth onClick={closeForm}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}
