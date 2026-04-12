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

export default function Abilities() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState<AddForm>(emptyForm)

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
      setShowAdd(false)
      setForm(emptyForm)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const useMutation_ = useMutation({
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

  if (!char) return null

  const abilities: Ability[] = char.abilities ?? []

  return (
    <Layout title={t('character.abilities.title')} backTo={`/char/${charId}`}>
      <button
        onClick={() => setShowAdd(true)}
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

      <div className="space-y-2">
        {abilities.map((ab) => (
          <Card key={ab.id}>
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{ab.name}</span>
                  <span className="text-xs text-[var(--tg-theme-hint-color)]">
                    {ab.is_passive ? t('character.abilities.passive') : t('character.abilities.active')}
                  </span>
                </div>
                {ab.description && (
                  <p className="text-xs text-[var(--tg-theme-hint-color)] mt-1 line-clamp-2">{ab.description}</p>
                )}
                {ab.max_uses != null && (
                  <p className="text-sm font-medium mt-1">
                    ⚡ {t('character.abilities.uses_left', { current: ab.uses ?? 0, max: ab.max_uses })}
                    {' '}· {t(`character.abilities.restoration.${ab.restoration_type}`, { defaultValue: ab.restoration_type })}
                  </p>
                )}
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                {ab.max_uses != null && (
                  <div className="flex gap-1">
                    <button
                      onClick={() => useMutation_.mutate({ abilityId: ab.id, uses: Math.max(0, (ab.uses ?? 0) - 1) })}
                      disabled={(ab.uses ?? 0) <= 0}
                      className="w-7 h-7 rounded-lg bg-red-500/20 text-red-300 font-bold text-sm disabled:opacity-30"
                    >−</button>
                    <button
                      onClick={() => useMutation_.mutate({ abilityId: ab.id, uses: Math.min(ab.max_uses!, (ab.uses ?? 0) + 1) })}
                      disabled={(ab.uses ?? 0) >= (ab.max_uses ?? 0)}
                      className="w-7 h-7 rounded-lg bg-green-500/20 text-green-300 font-bold text-sm disabled:opacity-30"
                    >+</button>
                  </div>
                )}
                <button
                  onClick={() => deleteMutation.mutate(ab.id)}
                  className="text-xs text-red-400"
                >
                  {t('common.delete')}
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full space-y-3">
            <h3 className="font-semibold">{t('character.abilities.add')}</h3>
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
                onClick={() => addMutation.mutate()}
                disabled={!form.name.trim() || addMutation.isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                           text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
              >
                {addMutation.isPending ? '...' : t('common.add')}
              </button>
              <button onClick={() => setShowAdd(false)} className="flex-1 py-2 rounded-xl bg-white/10">
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}
