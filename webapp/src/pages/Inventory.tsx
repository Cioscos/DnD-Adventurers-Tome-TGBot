import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/hooks/useToast'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Weight, ChevronRight, Pencil, RotateCcw } from 'lucide-react'
import { GiKnapsack as Backpack } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import { slotsAllowedFor, SLOT_PLACEHOLDER_ICON, handsConflict } from '@/lib/equipmentSlots'
import type { EquipmentSlot } from '@/types'
import HandsConflictDialog from '@/components/character/HandsConflictDialog'
import ScrollArea from '@/components/ScrollArea'
import EmptyState from '@/components/ui/EmptyState'
import ProgressTriad from '@/components/ui/ProgressTriad'
import Input from '@/components/ui/Input'
import { useUnitSettings, displayToLb, lbToDisplay, formatWeight, formatWeightValue, weightUnitLabel } from '@/store/unitSettings'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'
import { canShareMessage, haptic } from '@/auth/telegram'
import { useShareMessage } from '@/hooks/useShareMessage'
import InventoryItem, { type ItemProperty } from '@/pages/inventory/InventoryItem'
import ItemForm from '@/pages/inventory/ItemForm'
import { buildItemMetadata, buildHomebrewMetadataPatch, type ItemFormData, type ItemEffect } from '@/pages/inventory/itemMetadata'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { getItemTypeIcon } from '@/lib/itemIcons'
import type { Item } from '@/types'
import InventorySkeleton from '@/components/skeletons/InventorySkeleton'

export default function Inventory() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const location = useLocation()
  const navigate = useNavigate()
  const initialHighlight =
    typeof (location.state as { highlightItemId?: unknown } | null)?.highlightItemId === 'number'
      ? ((location.state as { highlightItemId: number }).highlightItemId)
      : null
  const [highlightId, setHighlightId] = useState<number | null>(initialHighlight)
  const itemRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const locale: 'it' | 'en' = i18n.language?.startsWith('en') ? 'en' : 'it'

  const [showAdd, setShowAdd] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [useTarget, setUseTarget] = useState<Item | null>(null)
  type AttackState = {
    result: WeaponAttackResult
    itemId: number
    wasRerolled: boolean
  }
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  const [slotPickerItem, setSlotPickerItem] = useState<Item | null>(null)
  const [equipConflict, setEquipConflict] = useState<{ item: Item; slot: EquipmentSlot; removedItem: Item } | null>(null)
  const toast = useToast()
  const [expanded, setExpanded] = useState<number | null>(null)
  const [collapsedTypes, setCollapsedTypes] = useState<Set<string>>(new Set())
  const system = useUnitSettings((s) => s.system)
  const [editingCap, setEditingCap] = useState(false)
  const [capDraft, setCapDraft] = useState('')
  const [scrolled, setScrolled] = useState(false)
  const topSentinelRef = useRef<HTMLDivElement>(null)

  const toggleType = (type: string) => {
    setCollapsedTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const hasItems = (char?.items?.length ?? 0) > 0

  // Active homebrew rules contribute Property defs that decorate items via
  // hb_<key> metadata. Last-wins on duplicate keys across multiple rules —
  // the inventory chip is purely informational, so the most recently loaded
  // definition wins without ambiguity.
  const { data: rules } = useQuery({
    queryKey: ['homebrew-rules', charId],
    queryFn: () => api.homebrew.listRules(charId),
  })
  const propertyByKey = useMemo(() => {
    const map = new Map<string, ItemProperty>()
    for (const rule of rules ?? []) {
      if (!rule.enabled) continue
      // Only item-subject rules contribute hb_<key> item metadata. Capture the
      // subject's item_types filter (null = applies to every item type) so the
      // chip renderer can scope properties to the right items.
      if (rule.dsl.subject?.type !== 'item') continue
      const itemTypes = rule.dsl.subject.filter?.item_types ?? null
      for (const prop of rule.dsl.properties ?? []) {
        map.set(prop.key, { property: prop, itemTypes })
      }
    }
    return map
  }, [rules])

  const addMutation = useMutation({
    mutationFn: (form: ItemFormData) =>
      api.items.add(charId, {
        name: form.name.trim(),
        item_type: form.item_type,
        quantity: Number(form.quantity) || 1,
        weight: Number(form.weight) || 0,
        description: form.description.trim() || undefined,
        is_equipped: false,
        item_metadata: buildItemMetadata(form),
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAdd(false)
      setEditingItem(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ itemId, form }: { itemId: number; form: ItemFormData }) =>
      api.items.update(charId, itemId, {
        name: form.name.trim(),
        item_type: form.item_type,
        quantity: Number(form.quantity) || 1,
        weight: Number(form.weight) || 0,
        description: form.description.trim() || undefined,
        item_metadata: buildItemMetadata(form),
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAdd(false)
      setEditingItem(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const toggleEquip = useMutation({
    mutationFn: async ({ itemId, equipped, slot, removeId }: { itemId: number; equipped: boolean; slot?: EquipmentSlot; removeId?: number }) => {
      if (removeId != null) {
        await api.items.update(charId, removeId, { is_equipped: false, equipment_slot: null })
      }
      return api.items.update(charId, itemId, slot
        ? { is_equipped: equipped, equipment_slot: slot }
        : { is_equipped: equipped })
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setSlotPickerItem(null)
      setEquipConflict(null)
    },
  })

  const doEquip = (item: Item, slot: EquipmentSlot) => {
    const c = handsConflict(char?.items ?? [], item, slot)
    if (c) {
      setEquipConflict({ item, slot, removedItem: c })
      setSlotPickerItem(null)
      return
    }
    toggleEquip.mutate({ itemId: item.id, equipped: true, slot })
  }

  const handleEquipToggle = (item: Item) => {
    if (item.is_equipped) {
      toggleEquip.mutate({ itemId: item.id, equipped: false })
      return
    }
    const allowedSlots = slotsAllowedFor(item.item_type)
    if (allowedSlots.length === 1) {
      doEquip(item, allowedSlots[0])
      return
    }
    if (allowedSlots.length > 1) {
      setSlotPickerItem(item)
      return
    }
    // No known slot: equip without slot assignment
    toggleEquip.mutate({ itemId: item.id, equipped: true })
  }

  const updateQty = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) =>
      api.items.update(charId, itemId, { quantity: Math.max(0, quantity) }),
    onSuccess: (updated) => qc.setQueryData(['character', charId], updated),
  })

  const updateCapMutation = useMutation({
    mutationFn: (value: number) => api.characters.updateCarryCapacity(charId, { value }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setEditingCap(false)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const resetCapMutation = useMutation({
    mutationFn: () => api.characters.resetCarryCapacityOverride(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  // Edit a single homebrew property (hb_<key>) on an item. The backend PATCH
  // REPLACES item_metadata wholesale, so we always send the full merged object
  // (current metadata spread + the one hb_<key> override).
  const setPropertyMutation = useMutation({
    mutationFn: ({
      itemId,
      metadata,
    }: {
      itemId: number
      metadata: Record<string, unknown>
    }) => api.items.update(charId, itemId, { item_metadata: metadata }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const handleSetProperty = useCallback(
    (itemId: number, key: string, value: unknown) => {
      const cached = qc.getQueryData<typeof char>(['character', charId])
      const target = cached?.items?.find((i) => i.id === itemId)
      const metadata = buildHomebrewMetadataPatch(
        target?.item_metadata as Record<string, unknown> | undefined,
        key,
        value,
      )
      setPropertyMutation.mutate({ itemId, metadata })
    },
    [qc, charId, setPropertyMutation],
  )

  const deleteMutation = useMutation({
    mutationFn: (itemId: number) => api.items.remove(charId, itemId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setDeleteTarget(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const shareItem = useShareMessage((itemId: number) => api.share.item(charId, itemId))

  const attackMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId),
    onSuccess: (result, itemId) => {
      setAttackState({ result, itemId, wasRerolled: false })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const attackRerollMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId, true),
    onSuccess: (result) => {
      setAttackState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        haptic.error()
      }
    },
  })

  const consumeMutation = useMutation({
    mutationFn: (itemId: number) => api.items.use(charId, itemId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setUseTarget(null)
      const cu = updated.consumable_use
      if (cu) {
        const parts: string[] = []
        if (cu.total_healed > 0) parts.push(t('character.inventory.use_result.healed', { hp: cu.total_healed }))
        for (const c of cu.conditions_removed) parts.push(t('character.inventory.use_result.removed', { cond: t(`character.conditions.${c}`, { defaultValue: c }) }))
        for (const c of cu.conditions_added) parts.push(t('character.inventory.use_result.added', { cond: t(`character.conditions.${c}`, { defaultValue: c }) }))
        if (parts.length > 0) toast.success(parts.join(' · '))
      }
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const summarizeEffects = (item: Item): string => {
    const effects = (item.item_metadata?.effects as ItemEffect[] | undefined) ?? []
    const parts = effects.map((e) => {
      if (e.kind === 'heal') return t('character.inventory.use_confirm.heal', { amount: e.amount })
      const cond = t(`character.conditions.${e.condition}`, { defaultValue: e.condition })
      return e.kind === 'add_condition'
        ? t('character.inventory.use_confirm.add', { cond })
        : t('character.inventory.use_confirm.remove', { cond })
    })
    parts.push(t('character.inventory.use_confirm.qty'))
    return parts.join(' · ')
  }

  const handleFormSubmit = useCallback((data: ItemFormData) => {
    if (editingItem) {
      updateMutation.mutate({ itemId: editingItem.id, form: data })
    } else {
      addMutation.mutate(data)
    }
  }, [editingItem, updateMutation, addMutation])

  const handleFormCancel = useCallback(() => {
    setShowAdd(false)
    setEditingItem(null)
  }, [])

  const handleEdit = useCallback((item: Item) => {
    setEditingItem(item)
    setShowAdd(true)
  }, [])

  useEffect(() => {
    if (highlightId === null) return
    if (!char) return // attendi che la character query carichi
    const target = char.items?.find((i) => i.id === highlightId)
    if (!target) {
      setHighlightId(null)
      navigate(location.pathname, { replace: true, state: null })
      return
    }

    // Espandi l'item
    setExpanded(highlightId)

    // Sblocca il tipo collassato (se serve)
    const TYPE_ORDER = ['weapon', 'armor', 'shield', 'consumable', 'tool', 'accessory', 'gear', 'potion', 'scroll', 'generic']
    const typeKey = TYPE_ORDER.includes(target.item_type) ? target.item_type : 'generic'
    setCollapsedTypes((prev) => {
      if (!prev.has(typeKey)) return prev
      const next = new Set(prev)
      next.delete(typeKey)
      return next
    })

    // Scroll into view (dopo il prossimo frame, così il DOM ha avuto tempo di espandere)
    const rafId = requestAnimationFrame(() => {
      itemRefs.current[highlightId]?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })

    // Fade dopo 3s e clear della state
    const tid = window.setTimeout(() => {
      setHighlightId(null)
      navigate(location.pathname, { replace: true, state: null })
    }, 3000)

    return () => {
      cancelAnimationFrame(rafId)
      window.clearTimeout(tid)
    }
  }, [highlightId, char, navigate, location.pathname])

  // Pill flottante: quando la sentinella in cima esce dalla viewport (scroll),
  // il pulsante "Aggiungi" si comprime in pill in alto a destra. Stesso pattern
  // sentinella + IntersectionObserver usato da ScrollArea.
  useEffect(() => {
    const el = topSentinelRef.current
    if (!el) {
      setScrolled(false)
      return
    }
    const io = new IntersectionObserver(
      ([entry]) => setScrolled(!entry.isIntersecting),
      { threshold: 0 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [hasItems])

  if (!char) {
    return (
      <Layout title={t('character.inventory.title')} backTo={`/char/${charId}`} group="equipment" page="inventory">
        <InventorySkeleton />
      </Layout>
    )
  }

  const items: Item[] = char.items ?? []
  const totalWeight = items.reduce((sum, i) => sum + i.weight * i.quantity, 0)

  const TYPE_ORDER: string[] = ['weapon', 'armor', 'shield', 'consumable', 'tool', 'accessory', 'gear', 'potion', 'scroll', 'generic']
  const grouped = items.reduce<Record<string, Item[]>>((acc, item) => {
    const key = TYPE_ORDER.includes(item.item_type) ? item.item_type : 'generic'
    if (!acc[key]) acc[key] = []
    acc[key].push(item)
    return acc
  }, {})
  for (const k of Object.keys(grouped)) {
    grouped[k].sort((a, b) => {
      if (a.is_equipped !== b.is_equipped) return a.is_equipped ? -1 : 1
      return a.name.localeCompare(b.name)
    })
  }
  const orderedTypes = TYPE_ORDER.filter((t) => grouped[t]?.length)

  return (
    <Layout title={t('character.inventory.title')} backTo={`/char/${charId}`} group="equipment" page="inventory">
      {/* Add button — barra sticky che si comprime in pill flottante su scroll.
          Nascosta del tutto se non ci sono oggetti (l'empty-state ha già la sua CTA). */}
      {hasItems && (
        <>
          <div className="sticky top-2 z-20 flex pointer-events-none">
            <m.div
              layout
              transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
              className={scrolled ? 'ml-auto pointer-events-auto' : 'w-full pointer-events-auto'}
            >
              <Button
                variant="primary"
                size="md"
                fullWidth={!scrolled}
                onClick={() => setShowAdd(true)}
                icon={<Plus size={18} />}
                haptic="medium"
                className={scrolled ? '!rounded-full shadow-halo-gold' : ''}
              >
                {scrolled ? t('character.inventory.add_short') : t('character.inventory.add')}
              </Button>
            </m.div>
          </div>
          <div ref={topSentinelRef} className="h-px" aria-hidden />
        </>
      )}

      {/* Carry capacity progress bar (Semantic Triad coloring) + manual override */}
      <Surface variant="elevated" className="!py-2">
        <div className="flex items-center gap-2 mb-1.5">
          <Weight size={13} className="text-dnd-gold-dim" />
          <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
            {t('character.inventory.carry_label')}
          </p>
          {!editingCap && (
            <button
              type="button"
              title={t('character.inventory.carry_edit')}
              onClick={() => {
                setCapDraft(String(lbToDisplay(char.carry_capacity, system)))
                setEditingCap(true)
                haptic.light()
              }}
              className="min-h-[44px] min-w-[44px] -my-2 -mr-2 flex items-center justify-center text-dnd-gold-dim active:opacity-70"
            >
              <Pencil size={14} />
            </button>
          )}
        </div>

        {editingCap ? (
          <div className="flex items-end gap-2">
            <Input
              className="flex-1"
              type="number"
              min={0}
              value={capDraft}
              onChange={setCapDraft}
              inputMode="decimal"
              trailingAction={
                <span className="text-dnd-text-muted text-sm font-cinzel pr-1">
                  {weightUnitLabel(system)}
                </span>
              }
            />
            <Button variant="secondary" size="sm" onClick={() => setEditingCap(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() =>
                updateCapMutation.mutate(
                  Math.max(0, Math.round(displayToLb(Number(capDraft) || 0, system))),
                )
              }
              disabled={updateCapMutation.isPending || !(Number(capDraft) > 0)}
              haptic="success"
            >
              {t('common.save')}
            </Button>
          </div>
        ) : (
          <ProgressTriad
            value={totalWeight}
            max={char.carry_capacity}
            display={`${formatWeightValue(totalWeight, system)} / ${formatWeight(char.carry_capacity, system)}`}
            showNumeric
          />
        )}

        {char.carry_capacity_override ? (
          <div className="flex items-center justify-between gap-2 mt-1.5">
            <p className="text-[10px] text-[var(--dnd-crimson-bright)] font-body italic flex-1">
              {t('character.inventory.carry_override_hint')}
            </p>
            <Button
              variant="ghost"
              size="sm"
              icon={<RotateCcw size={12} />}
              onClick={() => resetCapMutation.mutate()}
              disabled={resetCapMutation.isPending}
              haptic="warning"
            >
              {t('character.inventory.carry_reset_to_auto')}
            </Button>
          </div>
        ) : (
          <p className="text-[10px] text-dnd-text-faint font-body italic mt-1.5">
            {t('character.equipment.carry_formula', {
              str: char.ability_scores.find((s) => s.name.toLowerCase() === 'strength')?.value ?? 10,
              factor: system === 'metric' ? '7.5' : '15',
              cap: formatWeight(char.carry_capacity, system),
              defaultValue: 'Carry capacity = {{factor}} × Strength ({{str}}) = {{cap}}',
            })}
          </p>
        )}
      </Surface>

      {items.length === 0 && (
        <EmptyState
          icon={<Backpack size={32} />}
          title={t('common.none')}
          hint={t('character.inventory.empty_hint')}
          action={{
            label: t('character.inventory.add'),
            onClick: () => setShowAdd(true),
            icon: <Plus size={14} />,
          }}
        />
      )}

      <ScrollArea>
        {orderedTypes.map((type) => {
          const groupItems = grouped[type]
          const isCollapsed = collapsedTypes.has(type)
          const TypeIcon = getItemTypeIcon(type)
          // Compact header for 1-item sections — eliminates ~30% of the per-section
          // vertical waste when inventory is sparse.
          const isSingle = groupItems.length === 1
          return (
            <div key={type} className={isSingle ? 'mb-2' : 'mb-4'}>
              <m.button
                type="button"
                onClick={() => toggleType(type)}
                className={`sticky -top-4 z-[5] -mx-4 w-[calc(100%+2rem)] px-5 flex items-center gap-2 bg-dnd-bg/95 backdrop-blur-sm border-b border-dnd-border/40 text-left ${isSingle ? 'py-1' : 'py-2'} ${scrolled ? 'pr-24' : ''}`}
                aria-expanded={!isCollapsed}
              >
                <ChevronRight
                  size={14}
                  className={`text-dnd-gold-bright transition-transform ${!isCollapsed ? 'rotate-90' : ''}`}
                />
                <TypeIcon size={14} className="text-dnd-gold/80 shrink-0" />
                <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright flex-1">
                  {t(`character.inventory.types.${type}`)}
                </span>
                <span className="text-[10px] text-dnd-text-muted font-mono tabular-nums">
                  · {groupItems.length}
                </span>
              </m.button>
              <AnimatePresence>
                {!isCollapsed && (
                  <m.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-2 mt-2">
                      {groupItems.map((item) => (
                        <m.div
                          key={item.id}
                          layout
                          transition={{ duration: 0.18, ease: [0.25, 0.1, 0.25, 1] }}
                          ref={(el) => { itemRefs.current[item.id] = el }}
                          className={highlightId === item.id ? 'animate-pulse-glow' : undefined}
                        >
                          <InventoryItem
                            item={item}
                            isExpanded={expanded === item.id}
                            onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                            onEquipToggle={() => handleEquipToggle(item)}
                            onQuantityChange={(delta) => updateQty.mutate({ itemId: item.id, quantity: item.quantity + delta })}
                            onAttack={() => attackMutation.mutate(item.id)}
                            onUse={() => setUseTarget(item)}
                            onEdit={() => handleEdit(item)}
                            onDelete={() => setDeleteTarget(item.id)}
                            onShare={canShareMessage() ? () => shareItem.mutate(item.id) : undefined}
                            equipPending={toggleEquip.isPending}
                            attackPending={attackMutation.isPending}
                            usePending={consumeMutation.isPending}
                            propertyByKey={propertyByKey}
                            locale={locale}
                            onSetProperty={handleSetProperty}
                            setPropertyPending={setPropertyMutation.isPending}
                          />
                        </m.div>
                      ))}
                    </div>
                  </m.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </ScrollArea>

      {showAdd && (
        <ItemForm
          initialData={editingItem}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
          isPending={addMutation.isPending || updateMutation.isPending}
        />
      )}

      {attackState && (
        <WeaponAttackModal
          result={attackState.result}
          inspirationAvailable={Boolean(char?.heroic_inspiration)}
          isRerolling={attackRerollMutation.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => attackRerollMutation.mutate(attackState.itemId)}
          onClose={() => setAttackState(null)}
        />
      )}

      {/* Delete confirmation as Sheet */}
      <Sheet
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        centered
        title={t('common.confirm')}
      >
        <div className="p-5 space-y-3">
          <p className="text-sm text-center text-dnd-text font-body">
            {t('character.select.delete_confirm', {
              name: items.find((i) => i.id === deleteTarget)?.name ?? '',
            })}
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              fullWidth
              onClick={() => deleteTarget !== null && deleteMutation.mutate(deleteTarget)}
              loading={deleteMutation.isPending}
              haptic="error"
            >
              {t('common.delete')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setDeleteTarget(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>

      <ConfirmSheet
        open={useTarget !== null}
        onClose={() => setUseTarget(null)}
        onConfirm={() => useTarget && consumeMutation.mutate(useTarget.id)}
        title={t('character.inventory.use_confirm.title')}
        body={useTarget ? summarizeEffects(useTarget) : undefined}
        confirmLabel={t('character.inventory.use')}
        confirmVariant="primary"
        loading={consumeMutation.isPending}
      />

      {/* Slot picker for multi-slot equippable items */}
      <Sheet
        open={slotPickerItem !== null}
        onClose={() => setSlotPickerItem(null)}
        centered
        title={t('character.equipment.slot_picker.title')}
      >
        {slotPickerItem && (
          <div className="p-5 space-y-4">
            <p className="text-sm text-center text-dnd-text-muted font-body">
              {t('character.equipment.slot_picker.subtitle', { name: slotPickerItem.name })}
            </p>
            <div className="grid grid-cols-2 gap-2">
              {slotsAllowedFor(slotPickerItem.item_type).map((slot) => {
                const Icon = SLOT_PLACEHOLDER_ICON[slot]
                return (
                  <m.button
                    key={slot}
                    onClick={() => doEquip(slotPickerItem, slot)}
                    disabled={toggleEquip.isPending}
                    className="flex items-center gap-2 p-3 rounded-xl bg-dnd-surface border border-dnd-border hover:border-dnd-gold/60 disabled:opacity-50"
                    whileTap={{ scale: 0.96 }}
                  >
                    <Icon size={20} className="text-dnd-gold shrink-0" />
                    <span className="text-sm font-cinzel text-dnd-gold-bright">
                      {t(`character.equipment.slots.${slot}`)}
                    </span>
                  </m.button>
                )
              })}
            </div>
            <Button variant="secondary" fullWidth onClick={() => setSlotPickerItem(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        )}
      </Sheet>

      {equipConflict && (
        <HandsConflictDialog
          newItem={equipConflict.item}
          removedItem={equipConflict.removedItem}
          pending={toggleEquip.isPending}
          onCancel={() => setEquipConflict(null)}
          onConfirm={() =>
            toggleEquip.mutate({
              itemId: equipConflict.item.id,
              equipped: true,
              slot: equipConflict.slot,
              removeId: equipConflict.removedItem.id,
            })
          }
        />
      )}

      <AnimatePresence />
    </Layout>
  )
}
