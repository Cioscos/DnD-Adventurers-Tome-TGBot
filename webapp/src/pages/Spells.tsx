import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type ConcentrationSaveResult } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import DndInput from '@/components/DndInput'
import ScrollArea from '@/components/ScrollArea'
import { haptic } from '@/auth/telegram'
import SpellFilter from '@/pages/spells/SpellFilter'
import SpellItem from '@/pages/spells/SpellItem'
import SpellForm, { type SpellFormData } from '@/pages/spells/SpellForm'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import type { Spell, SpellSlot } from '@/types'

export default function Spells() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editingSpell, setEditingSpell] = useState<Spell | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [castingSpell, setCastingSpell] = useState<Spell | null>(null)
  const [concDamage, setConcDamage] = useState('')
  const [concSaveResult, setConcSaveResult] = useState<ConcentrationSaveResult | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  // --- Mutations ---

  const addMutation = useMutation({
    mutationFn: (data: SpellFormData) =>
      api.spells.add(charId, {
        name: data.name.trim(),
        level: Number(data.level),
        description: data.description.trim() || undefined,
        casting_time: data.casting_time.trim() || undefined,
        range_area: data.range_area.trim() || undefined,
        components: data.components.trim() || undefined,
        duration: data.duration.trim() || undefined,
        is_concentration: data.is_concentration,
        is_ritual: data.is_ritual,
        damage_dice: data.damage_dice.trim() || undefined,
        damage_type: data.damage_type.trim() || undefined,
        is_pinned: false,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setEditingSpell(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ spellId, data }: { spellId: number; data: SpellFormData }) =>
      api.spells.update(charId, spellId, {
        name: data.name.trim(),
        level: Number(data.level),
        description: data.description.trim() || undefined,
        casting_time: data.casting_time.trim() || undefined,
        range_area: data.range_area.trim() || undefined,
        components: data.components.trim() || undefined,
        duration: data.duration.trim() || undefined,
        is_concentration: data.is_concentration,
        is_ritual: data.is_ritual,
        damage_dice: data.damage_dice.trim() || undefined,
        damage_type: data.damage_type.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAdd(false)
      setEditingSpell(null)
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

  const useSlotMutation = useMutation({
    mutationFn: ({ slotId, newUsed }: { slotId: number; newUsed: number }) =>
      api.spellSlots.update(charId, slotId, { used: newUsed }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
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

  // --- Callbacks ---

  const handleFormSubmit = useCallback((data: SpellFormData) => {
    if (editingSpell) {
      updateMutation.mutate({ spellId: editingSpell.id, data })
    } else {
      addMutation.mutate(data)
    }
  }, [editingSpell, updateMutation, addMutation])

  const handleFormCancel = useCallback(() => {
    setShowAdd(false)
    setEditingSpell(null)
  }, [])

  const handleEditSpell = useCallback((spell: Spell) => {
    setEditingSpell(spell)
    setShowAdd(true)
  }, [])

  const handleCastSlot = useCallback((slotLevel: number) => {
    if (castingSpell) {
      castMutation.mutate({ spell: castingSpell, slotLevel })
    }
  }, [castingSpell, castMutation])

  // --- Derived data ---

  if (!char) return null

  const spells: Spell[] = char.spells ?? []
  const spellSlots: SpellSlot[] = char.spell_slots ?? []
  const filtered = search
    ? spells.filter((s) => s.name.toLowerCase().includes(search.toLowerCase()))
    : spells

  const byLevel = filtered.reduce<Record<number, Spell[]>>((acc, s) => {
    if (!acc[s.level]) acc[s.level] = []
    acc[s.level].push(s)
    return acc
  }, {})

  const sortedLevels = Object.keys(byLevel).map(Number).sort((a, b) => a - b)
  const concentratingId = char.concentrating_spell_id

  const availableSlotsFor = (spellLevel: number) =>
    spellSlots
      .filter((s) => s.level >= spellLevel && s.available > 0)
      .sort((a, b) => a.level - b.level)

  return (
    <Layout title={t('character.spells.title')} backTo={`/char/${charId}`} group="magic" page="spells">
      <SpellFilter
        search={search}
        onSearchChange={setSearch}
        onAddClick={() => setShowAdd(true)}
      />

      {/* Concentration panel */}
      {concentratingId && (
        <Card variant="elevated">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[#a569bd] text-sm font-medium">{t('character.spells.concentration')}</span>
            <button
              onClick={() => concentrationMutation.mutate(null)}
              className="text-xs text-[var(--dnd-danger)]"
            >
              {t('character.spells.stop_concentration')}
            </button>
          </div>
          <div className="flex gap-2 items-center">
            <DndInput
              value={concDamage}
              onChange={setConcDamage}
              placeholder={t('character.spells.conc_save_damage_placeholder')}
              inputMode="numeric"
              className="flex-1"
            />
            <DndButton
              variant="secondary"
              onClick={() => {
                const dmg = parseInt(concDamage, 10)
                if (!isNaN(dmg) && dmg >= 0) {
                  concSaveMutation.mutate(dmg)
                  setConcDamage('')
                }
              }}
              disabled={concSaveMutation.isPending || !concDamage}
              className="!bg-dnd-arcane/30 !text-[#a569bd] !border-dnd-arcane/30"
            >
              {concSaveMutation.isPending ? '...' : t('character.spells.conc_save_btn')}
            </DndButton>
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
            className={`rounded-2xl bg-dnd-surface-elevated p-5 w-full max-w-xs text-center space-y-3 border-2
              ${concSaveResult.success ? 'border-dnd-success' : 'border-[var(--dnd-danger)]'}`}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm text-dnd-text-secondary">
              {t('character.spells.concentration')} — DC {concSaveResult.dc}
            </p>
            {concSaveResult.is_critical && <p className="text-[var(--dnd-gold)] font-bold">CRITICO!</p>}
            {concSaveResult.is_fumble && <p className="text-[var(--dnd-danger)] font-bold">FUMBLE!</p>}
            <p className={`text-4xl font-black ${concSaveResult.success ? 'text-[#2ecc71]' : 'text-[var(--dnd-danger)]'}`}>
              {concSaveResult.total}
            </p>
            <p className="text-sm text-dnd-text-secondary">
              d20 ({concSaveResult.die}) {concSaveResult.bonus >= 0 ? '+' : ''}{concSaveResult.bonus}
            </p>
            <p className={`font-bold ${concSaveResult.success ? 'text-[#2ecc71]' : 'text-[var(--dnd-danger)]'}`}>
              {concSaveResult.success ? t('character.spells.conc_save_success') : t('character.spells.conc_save_fail')}
            </p>
            {concSaveResult.lost_concentration && (
              <p className="text-xs text-[var(--dnd-danger)]">{t('character.spells.conc_lost')}</p>
            )}
            <DndButton onClick={() => setConcSaveResult(null)} className="w-full">
              OK
            </DndButton>
          </div>
        </div>
      )}

      {spells.length === 0 && !showAdd && (
        <Card>
          <p className="text-center text-dnd-text-secondary">{t('common.none')}</p>
        </Card>
      )}

      <ScrollArea>
        {sortedLevels.map((level) => {
          const slot = level > 0 ? spellSlots.find((s) => s.level === level) : undefined
          return (
            <div key={level} className="mb-3">
              <div
                className="sticky z-[5] -mx-4 px-5 py-1.5 flex items-center gap-2 bg-dnd-bg"
                style={{ top: '53px' }}
              >
                <p className="text-sm font-semibold text-dnd-text-secondary flex-1">
                  {level === 0 ? t('character.spells.cantrip') : `${t('character.spells.level')} ${level}`}
                </p>
                {slot && slot.total > 0 && (
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1 items-center flex-wrap">
                      {Array.from({ length: slot.total }).map((_, i) => (
                        <span
                          key={i}
                          className={`w-3 h-3 rounded-full border-2 inline-block
                            ${i < slot.available
                              ? 'bg-dnd-gold border-transparent'
                              : 'bg-transparent border-dnd-text-secondary opacity-30'
                            }`}
                        />
                      ))}
                    </div>
                    <button
                      disabled={slot.used === 0 || useSlotMutation.isPending}
                      onClick={() => useSlotMutation.mutate({ slotId: slot.id, newUsed: slot.used - 1 })}
                      className="w-8 h-8 rounded-lg bg-dnd-surface text-lg font-bold leading-none
                                 flex items-center justify-center active:opacity-60 disabled:opacity-25 text-dnd-text"
                    >
                      &#x2212;
                    </button>
                    <button
                      disabled={slot.available === 0 || useSlotMutation.isPending}
                      onClick={() => useSlotMutation.mutate({ slotId: slot.id, newUsed: slot.used + 1 })}
                      className="w-8 h-8 rounded-lg bg-dnd-gold/80 text-dnd-bg text-lg font-bold leading-none
                                 flex items-center justify-center active:opacity-60 disabled:opacity-25"
                    >
                      +
                    </button>
                  </div>
                )}
              </div>
              <div className="space-y-1">
                {byLevel[level].map((spell) => (
                  <SpellItem
                    key={spell.id}
                    spell={spell}
                    isExpanded={expanded === spell.id}
                    onToggle={() => setExpanded(expanded === spell.id ? null : spell.id)}
                    onCast={() => setCastingSpell(spell)}
                    onCastCantrip={() => castCantrip.mutate(spell)}
                    onConcentrationToggle={() =>
                      concentrationMutation.mutate(concentratingId === spell.id ? null : spell.id)
                    }
                    onEdit={() => handleEditSpell(spell)}
                    onRemove={() => removeMutation.mutate(spell.id)}
                    concentratingSpellId={concentratingId ?? null}
                    castCantripPending={castCantrip.isPending}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </ScrollArea>

      {/* Cast spell slot picker modal */}
      {castingSpell && (
        <CastSpellModal
          spell={castingSpell}
          availableSlots={availableSlotsFor(castingSpell.level)}
          onCast={handleCastSlot}
          onCancel={() => setCastingSpell(null)}
          isPending={castMutation.isPending}
        />
      )}

      {/* Add/Edit spell form modal */}
      {showAdd && (
        <SpellForm
          initialData={editingSpell}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
          isPending={addMutation.isPending || updateMutation.isPending}
        />
      )}
    </Layout>
  )
}
