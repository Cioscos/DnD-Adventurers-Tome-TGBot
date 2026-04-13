import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { Spell, SpellSlot } from '@/types'

type ConcentrationSaveResult = {
  die: number
  bonus: number
  total: number
  dc: number
  success: boolean
  lost_concentration: boolean
  is_critical: boolean
  is_fumble: boolean
}

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
  const [editingSpell, setEditingSpell] = useState<Spell | null>(null)
  const [form, setForm] = useState<AddForm>(emptyForm)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [castingSpell, setCastingSpell] = useState<Spell | null>(null)
  const [concDamage, setConcDamage] = useState('')
  const [concSaveResult, setConcSaveResult] = useState<ConcentrationSaveResult | null>(null)

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

  const updateMutation = useMutation({
    mutationFn: () =>
      api.spells.update(charId, editingSpell!.id, {
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
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setEditingSpell(null)
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

  const castMutation = useMutation({
    mutationFn: async ({ spell, slotLevel }: { spell: Spell; slotLevel: number }) => {
      const updated = await api.spells.use(charId, spell.id, slotLevel)
      if (spell.is_concentration) {
        return api.spells.updateConcentration(charId, spell.id)
      }
      return updated
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setCastingSpell(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const concSaveMutation = useMutation({
    mutationFn: (damage: number) => api.spells.concentrationSave(charId, damage),
    onSuccess: (result) => {
      setConcSaveResult(result)
      if (result.lost_concentration) {
        qc.invalidateQueries({ queryKey: ['character', charId] })
      }
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const castCantrip = useMutation({
    mutationFn: async (spell: Spell) => {
      if (spell.is_concentration) {
        return api.spells.updateConcentration(charId, spell.id)
      }
      return Promise.resolve(char!)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  if (!char) return null

  const spells: Spell[] = char.spells ?? []
  const spellSlots: SpellSlot[] = char.spell_slots ?? []
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

  // Available slots for casting (level >= spell.level, available > 0)
  const availableSlotsFor = (spellLevel: number) =>
    spellSlots
      .filter((s) => s.level >= spellLevel && s.available > 0)
      .sort((a, b) => a.level - b.level)

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
          <div className="flex items-center justify-between mb-2">
            <span className="text-purple-300 text-sm font-medium">🔮 {t('character.spells.concentration')}</span>
            <button
              onClick={() => concentrationMutation.mutate(null)}
              className="text-xs text-red-400"
            >
              {t('character.spells.stop_concentration')}
            </button>
          </div>
          {/* Concentration save input */}
          <div className="flex gap-2 items-center">
            <input
              type="number"
              min="0"
              value={concDamage}
              onChange={(e) => setConcDamage(e.target.value)}
              placeholder={t('character.spells.conc_save_damage_placeholder')}
              className="flex-1 bg-white/10 rounded-xl px-3 py-1.5 text-sm outline-none
                         focus:ring-2 focus:ring-purple-500"
            />
            <button
              onClick={() => {
                const dmg = parseInt(concDamage, 10)
                if (!isNaN(dmg) && dmg >= 0) {
                  concSaveMutation.mutate(dmg)
                  setConcDamage('')
                }
              }}
              disabled={concSaveMutation.isPending || !concDamage}
              className="px-3 py-1.5 rounded-xl bg-purple-500/30 text-purple-300 text-sm font-medium
                         disabled:opacity-30 active:opacity-70"
            >
              {concSaveMutation.isPending ? '...' : t('character.spells.conc_save_btn')}
            </button>
          </div>
        </Card>
      )}

      {/* Concentration save result modal */}
      {concSaveResult && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setConcSaveResult(null)}
        >
          <div
            className={`rounded-2xl p-5 w-full max-w-xs text-center space-y-3
              ${concSaveResult.success ? 'bg-green-500/20 border border-green-500/40' : 'bg-red-500/20 border border-red-500/40'}`}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              🔮 {t('character.spells.concentration')} — DC {concSaveResult.dc}
            </p>
            {concSaveResult.is_critical && <p className="text-yellow-400 font-bold">✨ CRITICO!</p>}
            {concSaveResult.is_fumble && <p className="text-red-400 font-bold">💀 FUMBLE!</p>}
            <p className={`text-4xl font-black ${concSaveResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {concSaveResult.total}
            </p>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">
              d20 ({concSaveResult.die}) {concSaveResult.bonus >= 0 ? '+' : ''}{concSaveResult.bonus}
            </p>
            <p className={`font-bold ${concSaveResult.success ? 'text-green-400' : 'text-red-400'}`}>
              {concSaveResult.success ? t('character.spells.conc_save_success') : t('character.spells.conc_save_fail')}
            </p>
            {concSaveResult.lost_concentration && (
              <p className="text-xs text-red-300">{t('character.spells.conc_lost')}</p>
            )}
            <button
              onClick={() => setConcSaveResult(null)}
              className="w-full py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold"
            >
              OK
            </button>
          </div>
        </div>
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
                    <div className="flex gap-2 pt-1 flex-wrap">
                      {/* Cast button */}
                      {spell.level === 0 ? (
                        <button
                          onClick={() => castCantrip.mutate(spell)}
                          disabled={castCantrip.isPending}
                          className="text-xs px-3 py-2 rounded-lg bg-green-500/20 text-green-300 disabled:opacity-40 active:opacity-70"
                        >
                          ⚡ {t('character.spells.cast_cantrip')}
                        </button>
                      ) : (
                        <button
                          onClick={() => setCastingSpell(spell)}
                          className="text-xs px-3 py-2 rounded-lg bg-green-500/20 text-green-300 active:opacity-70"
                        >
                          ⚡ {t('character.spells.cast')}
                        </button>
                      )}

                      {spell.is_concentration && (
                        <button
                          onClick={() => concentrationMutation.mutate(
                            concentratingId === spell.id ? null : spell.id
                          )}
                          className={`text-xs px-3 py-2 rounded-lg active:opacity-70 ${
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
                        onClick={() => {
                          setEditingSpell(spell)
                          setForm({
                            name: spell.name,
                            level: String(spell.level),
                            description: spell.description || '',
                            casting_time: spell.casting_time || '',
                            range_area: spell.range_area || '',
                            components: spell.components || '',
                            duration: spell.duration || '',
                            is_concentration: spell.is_concentration,
                            is_ritual: spell.is_ritual,
                            damage_dice: spell.damage_dice || '',
                            damage_type: spell.damage_type || '',
                          })
                          setShowAdd(true)
                        }}
                        className="text-xs px-3 py-2 rounded-lg bg-blue-500/20 text-blue-300 active:opacity-70"
                      >
                        ✏️ {t('character.spells.edit')}
                      </button>
                      <button
                        onClick={() => removeMutation.mutate(spell.id)}
                        className="text-xs px-3 py-2 rounded-lg bg-red-500/20 text-red-300 active:opacity-70"
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

      {/* Slot picker modal */}
      {castingSpell && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{t('character.spells.cast_slot_title')}</h3>
              <button onClick={() => setCastingSpell(null)} className="text-[var(--tg-theme-hint-color)] text-sm">
                ✕
              </button>
            </div>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">{castingSpell.name}</p>
            <div className="space-y-2">
              {availableSlotsFor(castingSpell.level).length === 0 ? (
                <p className="text-sm text-red-400 text-center py-2">{t('character.spells.no_slots')}</p>
              ) : (
                availableSlotsFor(castingSpell.level).map((slot) => (
                  <button
                    key={slot.id}
                    onClick={() => castMutation.mutate({ spell: castingSpell, slotLevel: slot.level })}
                    disabled={castMutation.isPending}
                    className="w-full py-2.5 rounded-xl bg-white/10 font-medium
                               active:opacity-70 disabled:opacity-40 text-sm"
                  >
                    {t('character.slots.level', { level: slot.level })} — {slot.available}/{slot.total}
                  </button>
                ))
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Add spell modal */}
      {showAdd && (
        <div
          className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
          onFocusCapture={(e) => (e.target as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'nearest' })}
        >
          <Card className="w-full space-y-3 max-h-[80vh] overflow-y-auto">
            <h3 className="font-semibold">{editingSpell ? t('character.spells.edit') : t('character.spells.add')}</h3>
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
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.spells.damage')}</p>
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
                onClick={() => editingSpell ? updateMutation.mutate() : addMutation.mutate()}
                disabled={!form.name.trim() || addMutation.isPending || updateMutation.isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                           text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
              >
                {(addMutation.isPending || updateMutation.isPending)
                  ? '...'
                  : editingSpell ? t('common.save') : t('common.add')}
              </button>
              <button onClick={() => { setShowAdd(false); setEditingSpell(null); setForm(emptyForm) }} className="flex-1 py-2 rounded-xl bg-white/10">
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}
