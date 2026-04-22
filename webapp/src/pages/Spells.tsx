import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { FlaskConical, Ban, Sparkles, Gem } from 'lucide-react'
import { api, type ConcentrationSaveResult } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ScrollArea from '@/components/ScrollArea'
import { CornerFlourishes } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
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
  const [concDamage, setConcDamage] = useState('')
  const [concSaveResult, setConcSaveResult] = useState<ConcentrationSaveResult | null>(null)

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

      {/* Concentration panel */}
      {concentratingId && (
        <Surface variant="arcane" ornamented>
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-2">
              <FlaskConical size={16} className="text-dnd-arcane-bright" />
              <div>
                <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-arcane-bright">
                  {t('character.spells.concentration')}
                </p>
                {concentratingSpell && (
                  <p className="text-sm font-display font-bold text-dnd-text">{concentratingSpell.name}</p>
                )}
              </div>
            </div>
            <Button
              variant="danger"
              size="sm"
              onClick={() => concentrationMutation.mutate(null)}
              icon={<Ban size={12} />}
            >
              {t('character.spells.stop_concentration')}
            </Button>
          </div>
          <div className="flex gap-2 items-end">
            <Input
              value={concDamage}
              onChange={setConcDamage}
              placeholder={t('character.spells.conc_save_damage_placeholder')}
              inputMode="numeric"
              className="flex-1"
            />
            <Button
              variant="arcane"
              onClick={() => {
                const dmg = parseInt(concDamage, 10)
                if (!isNaN(dmg) && dmg >= 0) {
                  concSaveMutation.mutate(dmg)
                  setConcDamage('')
                }
              }}
              disabled={concSaveMutation.isPending || !concDamage}
              loading={concSaveMutation.isPending}
              haptic="warning"
            >
              {t('character.spells.conc_save_btn')}
            </Button>
          </div>
        </Surface>
      )}

      {/* Concentration save result */}
      <AnimatePresence>
        {concSaveResult && (
          <m.div
            className="fixed inset-0 flex items-center justify-center z-50 p-4"
            style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
            onClick={() => setConcSaveResult(null)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <m.div
              className={`relative rounded-3xl p-6 pt-8 w-full max-w-xs text-center space-y-3
                bg-gradient-parchment surface-parchment border-2 shadow-parchment-2xl
                ${concSaveResult.success ? 'border-dnd-emerald' : 'border-[var(--dnd-crimson)]'}`}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92 }}
              transition={spring.elastic}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-dnd-gold-dim"><CornerFlourishes /></div>
              <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">
                🔮 {t('character.spells.concentration')} — DC {concSaveResult.dc}
              </p>
              {concSaveResult.is_critical && <p className="text-dnd-gold-bright font-bold font-cinzel">✦ CRITICO!</p>}
              {concSaveResult.is_fumble && <p className="text-[var(--dnd-crimson-bright)] font-bold font-cinzel">💀 FUMBLE!</p>}
              <m.p
                initial={{ scale: 0.4 }}
                animate={{ scale: 1 }}
                transition={{ ...spring.elastic, delay: 0.1 }}
                className={`text-5xl font-black font-display ${concSaveResult.success ? 'text-[var(--dnd-emerald-bright)]' : 'text-[var(--dnd-crimson-bright)]'}`}
              >
                {concSaveResult.total}
              </m.p>
              <p className="text-xs text-dnd-text-muted font-mono">
                d20 ({concSaveResult.die}) {concSaveResult.bonus >= 0 ? '+' : ''}{concSaveResult.bonus}
              </p>
              <p className={`font-bold font-cinzel uppercase tracking-wider ${concSaveResult.success ? 'text-[var(--dnd-emerald-bright)]' : 'text-[var(--dnd-crimson-bright)]'}`}>
                {concSaveResult.success ? t('character.spells.conc_save_success') : t('character.spells.conc_save_fail')}
              </p>
              {concSaveResult.lost_concentration && (
                <p className="text-[10px] text-[var(--dnd-crimson-bright)] font-body italic">{t('character.spells.conc_lost')}</p>
              )}
              <Button variant="primary" fullWidth onClick={() => setConcSaveResult(null)}>OK</Button>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>

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
              <div
                className="sticky z-[5] -mx-4 px-5 py-2 flex items-center gap-2 bg-dnd-bg/95 backdrop-blur-sm border-b border-dnd-border/40"
                style={{ top: '68px' }}
              >
                <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
                  {level === 0 ? t('character.spells.cantrip') : `${t('character.spells.level')} ${level}`}
                </p>
                {slot && slot.total > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-dnd-text-faint font-mono tabular-nums">
                      {slot.used}/{slot.total}
                    </span>
                    <div className="flex gap-1 items-center flex-wrap">
                      {Array.from({ length: slot.total }).map((_, i) => {
                        const isUsed = i < slot.used
                        return (
                          <m.button
                            key={i}
                            disabled={useSlotMutation.isPending}
                            onClick={() => {
                              const newUsed = i < slot.used ? i : i + 1
                              useSlotMutation.mutate({
                                slotId: slot.id,
                                newUsed: Math.min(newUsed, slot.total),
                              })
                            }}
                            className={`w-6 h-6 rounded-full flex items-center justify-center
                              ${isUsed
                                ? 'bg-dnd-gold-dim border border-dnd-gold-dim/50'
                                : 'bg-gradient-to-br from-dnd-arcane to-dnd-arcane-deep border border-dnd-arcane-bright shadow-[0_0_6px_rgba(197,137,232,0.5)]'}
                              disabled:opacity-40`}
                            whileTap={{ scale: 0.85 }}
                            aria-label={`Slot ${i+1} ${isUsed ? 'used' : 'available'}`}
                          >
                            {!isUsed && <Gem size={10} className="text-white" />}
                          </m.button>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
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
