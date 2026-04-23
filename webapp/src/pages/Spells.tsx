import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { FlaskConical, Ban, Sparkles, ChevronRight } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import ScrollArea from '@/components/ScrollArea'
import { haptic } from '@/auth/telegram'
import SpellFilter from '@/pages/spells/SpellFilter'
import SpellItem from '@/pages/spells/SpellItem'
import SpellForm, { type SpellFormData } from '@/pages/spells/SpellForm'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import SpellDamageSheet from '@/pages/spells/SpellDamageSheet'
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
  const [rollDamageSpell, setRollDamageSpell] = useState<Spell | null>(null)
  const [collapsedLevels, setCollapsedLevels] = useState<Set<number>>(new Set())

  const toggleLevel = (level: number) => {
    setCollapsedLevels((prev) => {
      const next = new Set(prev)
      if (next.has(level)) next.delete(level)
      else next.add(level)
      return next
    })
  }

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

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
  const concentratingSpell = concentratingId ? spells.find(s => s.id === concentratingId) : null

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

      {/* Concentration panel — active spell + description. TS auto on /hp DAMAGE. */}
      {concentratingId && concentratingSpell && (
        <Surface variant="arcane" ornamented className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <FlaskConical size={16} className="text-dnd-arcane-bright shrink-0" />
              <div className="min-w-0">
                <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-arcane-bright">
                  {t('character.spells.concentration')}
                </p>
                <p className="text-base font-display font-bold text-dnd-gold-bright truncate">
                  {concentratingSpell.name}
                </p>
              </div>
            </div>
            <Button
              variant="danger"
              size="sm"
              onClick={() => concentrationMutation.mutate(null)}
              icon={<Ban size={12} />}
              haptic="warning"
            >
              {t('character.spells.stop_concentration')}
            </Button>
          </div>
          {concentratingSpell.description && (
            <p className="text-sm text-dnd-text font-body leading-relaxed break-words">
              {concentratingSpell.description}
            </p>
          )}
        </Surface>
      )}

      {spells.length === 0 && !showAdd && (
        <Surface variant="flat" className="text-center py-8">
          <Sparkles className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('common.none')}</p>
        </Surface>
      )}

      <ScrollArea>
        {sortedLevels.map((level) => {
          const slot = level > 0 ? spellSlots.find((s) => s.level === level) : undefined
          return (
            <div key={level} className="mb-4">
              <m.button
                type="button"
                onClick={() => toggleLevel(level)}
                className="sticky z-[5] -mx-4 w-[calc(100%+2rem)] px-5 py-2 flex items-center gap-2 bg-dnd-bg/95 backdrop-blur-sm border-b border-dnd-border/40 text-left"
                style={{ top: '68px' }}
                aria-expanded={!collapsedLevels.has(level)}
              >
                <ChevronRight
                  size={14}
                  className={`text-dnd-gold-bright transition-transform ${!collapsedLevels.has(level) ? 'rotate-90' : ''}`}
                />
                <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright flex-1">
                  {level === 0 ? t('character.spells.cantrip_label') : t('character.spells.level_label', { level })}
                </span>
                <span className="text-[10px] text-dnd-text-muted font-mono">
                  · {t('character.spells.count', { count: byLevel[level].length })}
                </span>
                {slot && slot.total > 0 && (
                  <>
                    <span className="ml-2 text-[10px] text-dnd-text-faint font-mono tabular-nums">
                      {slot.used}/{slot.total}
                    </span>
                    <div className="flex gap-1 items-center" onClick={(e) => e.stopPropagation()}>
                      {Array.from({ length: slot.total }).map((_, i) => (
                        <m.button
                          key={i}
                          type="button"
                          disabled={useSlotMutation.isPending}
                          onClick={(e) => {
                            e.stopPropagation()
                            if (i < slot.used) {
                              haptic.light()
                              useSlotMutation.mutate({ slotId: slot.id, newUsed: Math.max(0, slot.used - 1) })
                            } else {
                              haptic.medium()
                              useSlotMutation.mutate({ slotId: slot.id, newUsed: Math.min(slot.total, slot.used + 1) })
                            }
                          }}
                          className={`w-6 h-6 rounded-full border-2 transition-all disabled:opacity-40 ${
                            i < slot.used
                              ? 'bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright border-dnd-gold-bright shadow-[0_0_8px_rgba(244,208,111,0.5)]'
                              : 'bg-transparent border-dnd-gold-dim/60 hover:border-dnd-gold-bright'
                          }`}
                          whileTap={{ scale: 0.85 }}
                          aria-label={t('character.slots.gem_aria', {
                            level: slot.level,
                            index: i + 1,
                            total: slot.total,
                            state: i < slot.used
                              ? t('character.slots.state_used')
                              : t('character.slots.state_available'),
                          })}
                          aria-pressed={i < slot.used}
                        />
                      ))}
                    </div>
                  </>
                )}
              </m.button>
              <AnimatePresence>
                {!collapsedLevels.has(level) && (
                  <m.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-1.5 mt-2">
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
                          onRollDamage={setRollDamageSpell}
                        />
                      ))}
                    </div>
                  </m.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </ScrollArea>

      {castingSpell && (
        <CastSpellModal
          spell={castingSpell}
          availableSlots={availableSlotsFor(castingSpell.level)}
          onCast={handleCastSlot}
          onCancel={() => setCastingSpell(null)}
          isPending={castMutation.isPending}
        />
      )}

      {showAdd && (
        <SpellForm
          initialData={editingSpell}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
          isPending={addMutation.isPending || updateMutation.isPending}
        />
      )}

      <SpellDamageSheet
        charId={charId}
        spell={rollDamageSpell}
        onClose={() => setRollDamageSpell(null)}
      />

    </Layout>
  )
}
