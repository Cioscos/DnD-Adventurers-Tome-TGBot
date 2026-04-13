import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
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
    <Layout title={t('character.abilities.title')} backTo={`/char/${charId}`}>
      <button
        onClick={openAdd}
        className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                   text-[var(--tg-theme-button-text-color)] font-semibold"
      >
        + {t('character.abilities.add')}
      </button>

      {abilities.length === 0 && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      )}

      <div className="space-y-1">
        {abilities.map((ab) => (
          <div
            key={ab.id}
            className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)] overflow-hidden"
          >
            {/* Collapsed header row — tappable */}
            <button
              className="w-full flex items-center gap-2 px-3 py-3 text-left"
              onClick={() => setExpanded(expanded === ab.id ? null : ab.id)}
            >
              <span className="flex-1 font-medium text-sm">{ab.name}</span>
              <div className="flex gap-1.5 items-center shrink-0">
                <span
                  className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md border
                    ${ab.is_passive
                      ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                      : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                    }`}
                >
                  {ab.is_passive ? t('character.abilities.passive') : t('character.abilities.active')}
                </span>
                {ab.max_uses != null && (
                  <span className="text-xs text-[var(--tg-theme-hint-color)] font-medium tabular-nums">
                    {ab.uses ?? 0}/{ab.max_uses}
                  </span>
                )}
              </div>
              <span className="text-[var(--tg-theme-hint-color)] text-xs ml-1">
                {expanded === ab.id ? '˄' : '˅'}
              </span>
            </button>

            {/* Expanded details */}
            {expanded === ab.id && (
              <div className="px-3 pb-3 space-y-3 border-t border-white/10">
                {ab.description ? (
                  <p className="text-xs text-[var(--tg-theme-hint-color)] mt-2 whitespace-pre-wrap leading-relaxed border-l-2 border-amber-500/40 pl-2">
                    {ab.description}
                  </p>
                ) : (
                  <p className="text-xs text-[var(--tg-theme-hint-color)]/50 mt-2 italic">—</p>
                )}

                {/* Restoration type chip */}
                {ab.max_uses != null && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-[var(--tg-theme-hint-color)]">
                      🔄 {t(`character.abilities.restoration.${ab.restoration_type}`, { defaultValue: ab.restoration_type })}
                    </span>
                  </div>
                )}

                {/* Uses tracker */}
                {ab.max_uses != null && (
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => usesMutation.mutate({ abilityId: ab.id, uses: Math.max(0, (ab.uses ?? 0) - 1) })}
                      disabled={(ab.uses ?? 0) <= 0 || usesMutation.isPending}
                      className="w-10 h-10 rounded-xl bg-red-500/20 text-red-300 font-bold text-lg
                                 flex items-center justify-center active:opacity-70 disabled:opacity-30"
                    >−</button>
                    <span className="text-sm font-semibold tabular-nums flex-1 text-center">
                      ⚡ {t('character.abilities.uses_left', { current: ab.uses ?? 0, max: ab.max_uses })}
                    </span>
                    <button
                      onClick={() => usesMutation.mutate({ abilityId: ab.id, uses: Math.min(ab.max_uses!, (ab.uses ?? 0) + 1) })}
                      disabled={(ab.uses ?? 0) >= (ab.max_uses ?? 0) || usesMutation.isPending}
                      className="w-10 h-10 rounded-xl bg-green-500/20 text-green-300 font-bold text-lg
                                 flex items-center justify-center active:opacity-70 disabled:opacity-30"
                    >+</button>
                  </div>
                )}

                {/* Action buttons */}
                <div className="flex gap-2 pt-1 border-t border-white/10">
                  <button
                    onClick={() => openEdit(ab)}
                    className="text-xs px-3 py-2 rounded-lg bg-white/10 text-[var(--tg-theme-text-color)] font-medium active:opacity-70"
                  >
                    ✏️ {t('character.abilities.edit')}
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(ab.id)}
                    disabled={deleteMutation.isPending}
                    className="text-xs px-3 py-2 rounded-lg bg-red-500/20 text-red-400 font-medium active:opacity-70 disabled:opacity-40"
                  >
                    🗑 {t('common.delete')}
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add / Edit bottom sheet */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4" onClick={closeForm}>
          <Card className="w-full space-y-3" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
            <h3 className="font-semibold">
              {editingAbility ? t('character.abilities.edit') : t('character.abilities.add')}
            </h3>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder={t('character.abilities.name_label')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder={t('character.abilities.description_label')}
              rows={3}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none resize-none"
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.abilities.max_uses_label')}</p>
                <input
                  type="number" min="0" value={form.max_uses}
                  onChange={(e) => setForm((f) => ({ ...f, max_uses: e.target.value }))}
                  placeholder="—"
                  className="w-full bg-white/10 rounded-xl px-3 py-2 text-center outline-none"
                />
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.abilities.restoration_label')}</p>
                <select
                  value={form.restoration_type}
                  onChange={(e) => setForm((f) => ({ ...f, restoration_type: e.target.value }))}
                  className="w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-2 py-2 outline-none text-sm"
                >
                  <option value="long_rest">{t('character.abilities.restoration.long_rest')}</option>
                  <option value="short_rest">{t('character.abilities.restoration.short_rest')}</option>
                  <option value="manual">{t('character.abilities.restoration.manual')}</option>
                </select>
              </div>
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.is_passive}
                onChange={(e) => setForm((f) => ({ ...f, is_passive: e.target.checked }))}
                className="w-4 h-4"
              />
              <span className="text-sm">{t('character.abilities.passive')}</span>
            </label>
            <div className="flex gap-2">
              <button
                onClick={submitForm}
                disabled={!form.name.trim() || isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                           text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
              >
                {isPending ? '...' : editingAbility ? t('common.save') : t('common.add')}
              </button>
              <button onClick={closeForm} className="flex-1 py-2 rounded-xl bg-white/10">
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}
