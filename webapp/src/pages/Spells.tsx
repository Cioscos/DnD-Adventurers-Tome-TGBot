import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { Spell } from '@/types'

type AddForm = {
  name: string; level: string; description: string; casting_time: string
  range_area: string; components: string; duration: string
  is_concentration: boolean; is_ritual: boolean; damage_dice: string; damage_type: string
}
const emptyForm: AddForm = {
  name: '', level: '0', description: '', casting_time: '', range_area: '',
  components: '', duration: '', is_concentration: false, is_ritual: false,
  damage_dice: '', damage_type: '',
}

export default function Spells() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState<AddForm>(emptyForm)
  const [expanded, setExpanded] = useState<number | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const addMutation = useMutation({
    mutationFn: () =>
      api.spells.add(charId, {
        name: form.name.trim(),
        level: Number(form.level),
        description: form.description.trim() || undefined,
        casting_time: form.casting_time.trim() || undefined,
        range_area: form.range_area.trim() || undefined,
        components: form.components.trim() || undefined,
        duration: form.duration.trim() || undefined,
        is_concentration: form.is_concentration,
        is_ritual: form.is_ritual,
        damage_dice: form.damage_dice.trim() || undefined,
        damage_type: form.damage_type.trim() || undefined,
        is_pinned: false,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setForm(emptyForm)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const removeMutation = useMutation({
    mutationFn: (spellId: number) => api.spells.remove(charId, spellId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  const concentrationMutation = useMutation({
    mutationFn: (spellId: number | null) => api.spells.updateConcentration(charId, spellId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  if (!char) return null

  const spells: Spell[] = char.spells ?? []
  const filtered = search
    ? spells.filter((s) => s.name.toLowerCase().includes(search.toLowerCase()))
    : spells

  // Group by level
  const byLevel = filtered.reduce<Record<number, Spell[]>>((acc, s) => {
    if (!acc[s.level]) acc[s.level] = []
    acc[s.level].push(s)
    return acc
  }, {})

  const sortedLevels = Object.keys(byLevel).map(Number).sort((a, b) => a - b)

  const concentratingId = char.concentrating_spell_id

  return (
    <Layout title={t('character.spells.title')} backTo={`/char/${charId}`}>
      <div className="flex gap-2">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('character.spells.search')}
          className="flex-1 bg-white/10 rounded-xl px-3 py-2 outline-none
                     focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
        />
        <button
          onClick={() => setShowAdd(true)}
          className="px-4 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                     text-[var(--tg-theme-button-text-color)] font-semibold"
        >
          +
        </button>
      </div>

      {concentratingId && (
        <Card>
          <div className="flex items-center justify-between">
            <span className="text-purple-300 text-sm">🔮 {t('character.spells.concentration')}</span>
            <button
              onClick={() => concentrationMutation.mutate(null)}
              className="text-xs text-red-400"
            >
              {t('character.spells.stop_concentration')}
            </button>
          </div>
        </Card>
      )}

      {spells.length === 0 && !showAdd && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      )}

      {sortedLevels.map((level) => (
        <div key={level}>
          <p className="text-sm font-semibold text-[var(--tg-theme-hint-color)] px-1 mb-1">
            {level === 0 ? t('character.spells.cantrip') : `${t('character.spells.level')} ${level}`}
          </p>
          <div className="space-y-1">
            {byLevel[level].map((spell) => (
              <div
                key={spell.id}
                className={`rounded-xl bg-[var(--tg-theme-secondary-bg-color)] overflow-hidden
                  ${concentratingId === spell.id ? 'ring-1 ring-purple-500' : ''}`}
              >
                <button
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-left"
                  onClick={() => setExpanded(expanded === spell.id ? null : spell.id)}
                >
                  <span className="flex-1 font-medium text-sm">{spell.name}</span>
                  <div className="flex gap-1 shrink-0">
                    {spell.is_concentration && <span className="text-xs text-purple-400">C</span>}
                    {spell.is_ritual && <span className="text-xs text-blue-400">R</span>}
                    {spell.is_pinned && <span className="text-xs">📌</span>}
                  </div>
                  <span className="text-[var(--tg-theme-hint-color)] text-xs">{expanded === spell.id ? '▲' : '▼'}</span>
                </button>

                {expanded === spell.id && (
                  <div className="px-3 pb-3 space-y-2 border-t border-white/10">
                    {spell.description && (
                      <p className="text-xs text-[var(--tg-theme-hint-color)] mt-2 whitespace-pre-wrap">{spell.description}</p>
                    )}
                    <div className="grid grid-cols-2 gap-1 text-xs">
                      {spell.casting_time && <span>⏱ {spell.casting_time}</span>}
                      {spell.range_area && <span>📏 {spell.range_area}</span>}
                      {spell.components && <span>🧪 {spell.components}</span>}
                      {spell.duration && <span>⏳ {spell.duration}</span>}
                      {spell.damage_dice && (
                        <span>⚔️ {spell.damage_dice}{spell.damage_type ? ` (${spell.damage_type})` : ''}</span>
                      )}
                    </div>
                    <div className="flex gap-2 pt-1">
                      {spell.is_concentration && (
                        <button
                          onClick={() => concentrationMutation.mutate(
                            concentratingId === spell.id ? null : spell.id
                          )}
                          className={`text-xs px-2 py-1 rounded-lg ${
                            concentratingId === spell.id
                              ? 'bg-red-500/20 text-red-300'
                              : 'bg-purple-500/20 text-purple-300'
                          }`}
                        >
                          🔮 {concentratingId === spell.id
                            ? t('character.spells.stop_concentration')
                            : t('character.spells.concentration')}
                        </button>
                      )}
                      <button
                        onClick={() => removeMutation.mutate(spell.id)}
                        className="text-xs px-2 py-1 rounded-lg bg-red-500/20 text-red-300"
                      >
                        {t('character.spells.forget')}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4 overflow-y-auto">
          <Card className="w-full space-y-3">
            <h3 className="font-semibold">{t('character.spells.add')}</h3>
            <input
              type="text" value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder={t('character.spells.name')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.spells.level')}</p>
                <select
                  value={form.level}
                  onChange={(e) => setForm((f) => ({ ...f, level: e.target.value }))}
                  className="w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-2 py-2 outline-none"
                >
                  <option value="0">{t('character.spells.cantrip')}</option>
                  {[1,2,3,4,5,6,7,8,9].map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.spells.casting_time')}</p>
                <input
                  type="text" value={form.casting_time}
                  onChange={(e) => setForm((f) => ({ ...f, casting_time: e.target.value }))}
                  placeholder="1 azione"
                  className="w-full bg-white/10 rounded-xl px-2 py-2 outline-none text-sm"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.spells.range')}</p>
                <input
                  type="text" value={form.range_area}
                  onChange={(e) => setForm((f) => ({ ...f, range_area: e.target.value }))}
                  placeholder="18m"
                  className="w-full bg-white/10 rounded-xl px-2 py-2 outline-none text-sm"
                />
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.spells.duration')}</p>
                <input
                  type="text" value={form.duration}
                  onChange={(e) => setForm((f) => ({ ...f, duration: e.target.value }))}
                  placeholder="Istantanea"
                  className="w-full bg-white/10 rounded-xl px-2 py-2 outline-none text-sm"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.spells.components')}</p>
                <input
                  type="text" value={form.components}
                  onChange={(e) => setForm((f) => ({ ...f, components: e.target.value }))}
                  placeholder="V, S, M"
                  className="w-full bg-white/10 rounded-xl px-2 py-2 outline-none text-sm"
                />
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">Danno</p>
                <input
                  type="text" value={form.damage_dice}
                  onChange={(e) => setForm((f) => ({ ...f, damage_dice: e.target.value }))}
                  placeholder="2d6"
                  className="w-full bg-white/10 rounded-xl px-2 py-2 outline-none text-sm"
                />
              </div>
            </div>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder={t('character.spells.description')}
              rows={4}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none resize-none"
            />
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox" checked={form.is_concentration}
                  onChange={(e) => setForm((f) => ({ ...f, is_concentration: e.target.checked }))}
                  className="w-4 h-4"
                />
                {t('character.spells.concentration')}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox" checked={form.is_ritual}
                  onChange={(e) => setForm((f) => ({ ...f, is_ritual: e.target.checked }))}
                  className="w-4 h-4"
                />
                {t('character.spells.ritual')}
              </label>
            </div>
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
