import type React from 'react'
import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/hooks/useToast'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Weight, ChevronRight, Pencil, RotateCcw, FolderPlus, FolderInput, Trash2, ListChecks, Check } from 'lucide-react'
import { GiKnapsack as Backpack } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import type { WeaponChoice } from '@/lib/weaponOptions'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
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
import AttunementSection from '@/pages/inventory/AttunementSection'
import { useItemCast } from '@/pages/spells/useItemCast'
import { INVENTORY_TYPE_ORDER, buildItemMetadata, buildHomebrewMetadataPatch, type ItemFormData, type ItemEffect } from '@/pages/inventory/itemMetadata'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { getItemTypeIcon } from '@/lib/itemIcons'
import { itemGrantedSpells } from '@/lib/itemMagic'
import type { Item } from '@/types'
import ContainerCard from '@/pages/inventory/ContainerCard'
import { containerPath, containerMeta, isContainer, movedWeight, type ContainerFormValue } from '@/lib/containers'
import MoveSheet from '@/pages/inventory/MoveSheet'
import ContainerForm from '@/pages/inventory/ContainerForm'
import InventorySkeleton from '@/components/skeletons/InventorySkeleton'

const COIN_KEYS = ['platinum', 'gold', 'electrum', 'silver', 'copper'] as const
const COIN_ABBR = { platinum: 'pp', gold: 'gp', electrum: 'ep', silver: 'sp', copper: 'cp' } as const

export default function Inventory() {
  const { id, containerId: containerParam } = useParams<{ id: string; containerId?: string }>()
  const charId = Number(id)
  const containerId = containerParam != null ? Number(containerParam) : null
  const location = useLocation()
  const navigate = useNavigate()
  const initialHighlight =
    typeof (location.state as { highlightItemId?: unknown } | null)?.highlightItemId === 'number'
      ? ((location.state as { highlightItemId: number }).highlightItemId)
      : null
  const [highlightId, setHighlightId] = useState<number | null>(initialHighlight)
  const highlightHandled = useRef<number | null>(null)
  const itemRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const locale: 'it' | 'en' = i18n.language?.startsWith('en') ? 'en' : 'it'

  const [showAdd, setShowAdd] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [moveTargets, setMoveTargets] = useState<Item[] | null>(null)
  // Nuovo contenitore: da "+ Contenitore" oppure da "Sposta in…" (poi vi si spostano gli oggetti).
  const [newBox, setNewBox] = useState<{ thenMove: Item[] | null } | null>(null)
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [useTarget, setUseTarget] = useState<Item | null>(null)
  type AttackState = {
    result: WeaponAttackResult
    itemId: number
    choice: WeaponChoice
    wasRerolled: boolean
  }
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  // Scelta pre-attacco ricordata per arma (una/due mani, mischia/lancio).
  const weaponChoices = useWeaponChoices((s) => s.choices)
  const setWeaponChoice = useWeaponChoices((s) => s.setChoice)
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
        container_id: containerId,
        item_metadata: buildItemMetadata(form),
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAdd(false)
      setEditingItem(null)
      haptic.success()
    },
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
  })

  const resetCapMutation = useMutation({
    mutationFn: () => api.characters.resetCarryCapacityOverride(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
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

  const exitSelect = () => { setSelecting(false); setSelected(new Set()) }

  const moveMutation = useMutation({
    mutationFn: ({ ids, target, quantity }: { ids: number[]; target: number | null; quantity?: number }) =>
      api.items.move(charId, { item_ids: ids, container_id: target, quantity }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setMoveTargets(null)
      exitSelect()
      const names = updated.unequipped_item_names ?? []
      if (names.length > 0) toast.info(t('character.inventory.containers.unequipped', { names: names.join(', ') }))
      haptic.success()
    },
    onError: () => toast.error(t('common.action_failed')),
  })

  const addBoxMutation = useMutation({
    mutationFn: async ({ name, weight, container, thenMove }: { name: string; weight: number; container: ContainerFormValue; thenMove: Item[] | null }) => {
      const before = new Set((qc.getQueryData<typeof char>(['character', charId])?.items ?? []).map((i) => i.id))
      const created = await api.items.add(charId, {
        name, item_type: 'gear', quantity: 1, weight, is_equipped: false, container_id: containerId,
        item_metadata: { container },
      })
      if (!thenMove) return created
      const box = (created.items ?? []).filter((i) => !before.has(i.id) && isContainer(i)).sort((a, b) => b.id - a.id)[0]
      return box ? api.items.move(charId, { item_ids: thenMove.map((i) => i.id), container_id: box.id }) : created
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setNewBox(null)
      setMoveTargets(null)
      exitSelect()
      haptic.success()
    },
    onError: () => toast.error(t('common.action_failed')),
  })

  const deleteMutation = useMutation({
    mutationFn: (itemId: number) => api.items.remove(charId, itemId),
    onSuccess: (updated, itemId) => {
      qc.setQueryData(['character', charId], updated)
      setDeleteTarget(null)
      if (itemId === containerId) {
        const parent = path.at(-2)
        navigate(parent ? `/char/${charId}/inventory/c/${parent.id}` : `/char/${charId}/inventory`, { replace: true })
      }
      haptic.success()
    },
  })

  const chargesMutation = useMutation({
    mutationFn: ({ itemId, delta }: { itemId: number; delta: number }) => api.items.charges(charId, itemId, delta),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
    },
    onError: () => toast.error(t('common.action_failed')),
  })
  const itemCast = useItemCast(charId)

  const shareItem = useShareMessage((itemId: number) => api.share.item(charId, itemId))

  const rollDice = useAnimatedRoll()
  const rollD20 = useD20Roll()

  const attackMutation = useMutation({
    mutationFn: async ({ itemId, mode }: { itemId: number; mode: RollMode }) =>
      api.items.attack(
        charId, itemId, false, d20Arg(mode, await rollD20(mode)),
        choiceOf(weaponChoices, itemId),
      ),
    onSuccess: (result, { itemId }) => {
      setAttackState({
        result, itemId, choice: choiceOf(weaponChoices, itemId), wasRerolled: false,
      })
      haptic.success()
    },
  })

  const attackRerollMutation = useMutation({
    mutationFn: async ({ itemId, choice }: { itemId: number; choice: WeaponChoice }) => {
      const die = (await rollDice('d20', 1))?.[0]
      return api.items.attack(charId, itemId, true, die, choice)
    },
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

    // Una volta sola per evidenziazione: un refetch di `char` nei 3s non deve riespandere né
    // riportare lo scroll sull'oggetto mentre l'utente sta già scorrendo.
    if (highlightHandled.current === highlightId) return
    highlightHandled.current = highlightId

    // Espandi l'item
    setExpanded(highlightId)

    // Sblocca il tipo collassato (se serve)
    const typeKey = (INVENTORY_TYPE_ORDER as readonly string[]).includes(target.item_type) ? target.item_type : 'generic'
    setCollapsedTypes((prev) => {
      if (!prev.has(typeKey)) return prev
      const next = new Set(prev)
      next.delete(typeKey)
      return next
    })

    // Come in Incantesimi: al primo frame la riga può non essere montata (tipo appena de-collassato)
    // e l'espansione della card (~350ms) sposta il layout fermando lo scroll a metà → riprova, poi
    // un secondo passaggio a layout assestato.
    const scrollToItem = () => itemRefs.current[highlightId]?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    // Niente cleanup (come in Incantesimi): un rerun per refetch annullerebbe lo scroll già avviato.
    let attempts = 0
    const tryScroll = () => {
      if (itemRefs.current[highlightId]) scrollToItem()
      else if (attempts++ < 10) requestAnimationFrame(tryScroll)
    }
    requestAnimationFrame(tryScroll)
    window.setTimeout(scrollToItem, 450)
  }, [highlightId, char, navigate, location.pathname])

  // Fade dopo 3s (da quando la scheda è caricata) e clear della state: separato, così i refetch di
  // `char` non lo riavviano.
  const charLoaded = !!char
  useEffect(() => {
    if (highlightId === null || !charLoaded) return
    const tid = window.setTimeout(() => {
      setHighlightId(null)
      navigate(location.pathname, { replace: true, state: null })
    }, 3000)
    return () => window.clearTimeout(tid)
  }, [highlightId, charLoaded, navigate, location.pathname])

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
  const totalWeight = char.encumbrance_total ?? items.reduce((sum, i) => sum + i.weight * i.quantity, 0)

  const path = containerPath(items, containerId)
  if (containerId != null && path.length === 0) {
    return <Navigate to={`/char/${charId}/inventory`} replace />
  }
  const current = path.at(-1) ?? null
  const currentMeta = current ? containerMeta(current) : null
  // Contenitori in ordine di id (= ordine di prelievo del backend); gli altri oggetti restano per tipo.
  const levelItems = items.filter((i) => (i.container_id ?? null) === containerId)
  const childBoxes = levelItems.filter(isContainer).sort((a, b) => a.id - b.id)

  const TYPE_ORDER: readonly string[] = INVENTORY_TYPE_ORDER
  const grouped = levelItems.filter((i) => !isContainer(i)).reduce<Record<string, Item[]>>((acc, item) => {
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

  const pc = 'character.inventory.containers.'
  const toggleSelected = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  // In modalità selezione un velo trasparente sopra la riga cattura il tocco.
  const selectable = (id: number, node: React.ReactNode) =>
    !selecting ? node : (
      <div className="relative">
        {node}
        <Pressable
          onClick={() => toggleSelected(id)}
          aria-label={items.find((i) => i.id === id)?.name}
          className={`absolute inset-0 z-10 rounded-xl border-2 flex items-start justify-end p-2 ${selected.has(id) ? 'border-dnd-gold bg-dnd-gold/10' : 'border-transparent'}`}
        >
          {selected.has(id) && <Check size={16} className="text-dnd-gold-bright" />}
        </Pressable>
      </div>
    )

  // Cosa succede ai figli se si elimina il contenitore: finiscono nel padre (o fuori).
  const deleting = items.find((i) => i.id === deleteTarget)
  const deleteBody = (() => {
    if (!deleting || !isContainer(deleting)) return t('character.select.delete_confirm', { name: deleting?.name ?? '' })
    const kids = items.filter((i) => i.container_id === deleting.id)
    const parent = items.find((i) => i.id === deleting.container_id)
    const pm = parent ? containerMeta(parent) : null
    const after = (parent?.container_stats?.contents_weight ?? 0) - movedWeight(deleting) + kids.reduce((w, k) => w + movedWeight(k), 0)
    const over = pm?.capacity_lb != null && after > pm.capacity_lb
    return (
      <>
        <p>{t('character.select.delete_confirm', { name: deleting.name })}</p>
        <p className="mt-2">{t(pc + 'delete_moves', { count: kids.length, dest: parent?.name ?? t(pc + 'outside_dest') })}</p>
        {over && pm && (
          <p className="mt-2 text-dnd-crimson-bright">
            {t(pc + 'delete_over', { used: formatWeightValue(after, system), cap: formatWeight(pm.capacity_lb!, system) })}
          </p>
        )}
      </>
    )
  })()

  return (
    <Layout title={t('character.inventory.title')} backTo={`/char/${charId}`} group="equipment" page="inventory">
      {/* Add button — barra sticky che si comprime in pill flottante su scroll.
          Nascosta del tutto se non ci sono oggetti (l'empty-state ha già la sua CTA). */}
      {hasItems && (
        <>
          <div className="sticky top-[calc(var(--crumb-offset,0px)+0.5rem)] z-20 flex pointer-events-none">
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
                className={scrolled ? '!rounded-full' : ''}
              >
                {scrolled ? t('character.inventory.add_short') : t('character.inventory.add')}
              </Button>
            </m.div>
          </div>
          <div ref={topSentinelRef} className="h-px" aria-hidden />
        </>
      )}

      <div className="flex gap-2 mb-2">
        {selecting ? (
          <>
            <Button variant="secondary" size="sm" fullWidth onClick={exitSelect}>{t('common.cancel')}</Button>
            <Button
              variant="primary" size="sm" fullWidth icon={<FolderInput size={14} />}
              disabled={selected.size === 0}
              onClick={() => setMoveTargets(items.filter((i) => selected.has(i.id)))}
            >
              {t(pc + 'move')} ({selected.size})
            </Button>
          </>
        ) : (
          <>
            <Button variant="secondary" size="sm" fullWidth icon={<FolderPlus size={14} />} onClick={() => setNewBox({ thenMove: null })}>
              {t(pc + 'new')}
            </Button>
            {levelItems.length > 0 && (
              <Button variant="secondary" size="sm" fullWidth icon={<ListChecks size={14} />} onClick={() => setSelecting(true)}>
                {t(pc + 'select')}
              </Button>
            )}
          </>
        )}
      </div>

      {current && (
        <Surface variant="elevated" className="!py-2">
          <nav aria-label="breadcrumb" className="flex flex-wrap items-center gap-1 text-xs font-cinzel text-dnd-gold-dim">
            <Pressable
              onClick={() => navigate(`/char/${charId}/inventory`)}
              className="min-h-[44px] min-w-[44px] px-1 flex items-center justify-center"
            >
              {t('character.inventory.containers.root')}
            </Pressable>
            {path.map((c) => (
              <span key={c.id} className="flex items-center gap-1">
                <ChevronRight size={12} aria-hidden />
                {c.id === current.id ? (
                  <span className="text-dnd-gold-bright">{c.name}</span>
                ) : (
                  <Pressable
                    onClick={() => navigate(`/char/${charId}/inventory/c/${c.id}`)}
                    className="min-h-[44px] min-w-[44px] px-1 flex items-center justify-center"
                  >
                    {c.name}
                  </Pressable>
                )}
              </span>
            ))}
          </nav>
          {currentMeta?.capacity_lb != null ? (
            <ProgressTriad
              value={current.container_stats?.contents_weight ?? 0}
              max={currentMeta.capacity_lb}
              label={t('character.inventory.containers.capacity')}
              display={`${formatWeightValue(current.container_stats?.contents_weight ?? 0, system)} / ${formatWeight(currentMeta.capacity_lb, system)}`}
              showNumeric
            />
          ) : (
            <p className="text-xs text-dnd-text-muted font-mono tabular-nums">
              {formatWeight(current.container_stats?.contents_weight ?? 0, system)}
            </p>
          )}
          {COIN_KEYS.some((k) => (currentMeta?.coins?.[k] ?? 0) > 0) && (
            <p className="text-xs text-dnd-text-muted font-mono tabular-nums mt-1.5" aria-label={t('character.inventory.containers.coins')}>
              {COIN_KEYS.filter((k) => (currentMeta?.coins?.[k] ?? 0) > 0)
                .map((k) => `${currentMeta!.coins[k]} ${COIN_ABBR[k]}`).join(' · ')}
            </p>
          )}
          <div className="flex justify-end gap-1 mt-1">
            {([
              [t(pc + 'move'), FolderInput, () => setMoveTargets([current])],
              [t('common.edit'), Pencil, () => handleEdit(current)],
              [t('common.delete'), Trash2, () => setDeleteTarget(current.id)],
            ] as const).map(([label, Icon, run]) => (
              <Pressable key={label} title={label} aria-label={label} onClick={run}
                className="min-h-[44px] min-w-[44px] flex items-center justify-center text-dnd-gold-dim active:opacity-70">
                <Icon size={16} />
              </Pressable>
            ))}
          </div>
        </Surface>
      )}

      {/* Carry capacity progress bar (Semantic Triad coloring) + manual override */}
      {!current && (
      <Surface variant="elevated" className="!py-2">
        <div className="flex items-center gap-2 mb-1.5">
          <Weight size={13} className="text-dnd-gold-dim" />
          <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
            {t('character.inventory.carry_label')}
          </p>
          {!editingCap && (
            <Pressable
              title={t('character.inventory.carry_edit')}
              onClick={() => {
                setCapDraft('')
                setEditingCap(true)
                haptic.light()
              }}
              className="min-h-[44px] min-w-[44px] -my-2 -mr-2 flex items-center justify-center text-dnd-gold-dim active:opacity-70"
            >
              <Pencil size={14} />
            </Pressable>
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
              placeholder={String(lbToDisplay(char.carry_capacity, system))}
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
              disabled={!(Number(capDraft) > 0)}
              loading={updateCapMutation.isPending}
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
            <p className="text-xs text-dnd-crimson-bright font-body italic flex-1">
              {t('character.inventory.carry_override_hint')}
            </p>
            <Button
              variant="ghost"
              size="sm"
              icon={<RotateCcw size={12} />}
              onClick={() => resetCapMutation.mutate()}
              loading={resetCapMutation.isPending}
              haptic="warning"
            >
              {t('character.inventory.carry_reset_to_auto')}
            </Button>
          </div>
        ) : (
          <p className="text-xs text-dnd-text-faint font-body italic mt-1.5">
            {t('character.equipment.carry_formula', {
              str: char.ability_scores.find((s) => s.name.toLowerCase() === 'strength')?.value ?? 10,
              factor: system === 'metric' ? '7.5' : '15',
              cap: formatWeight(char.carry_capacity, system),
              defaultValue: 'Carry capacity = {{factor}} × Strength ({{str}}) = {{cap}}',
            })}
          </p>
        )}
      </Surface>
      )}

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

      {current && levelItems.length === 0 && (
        <EmptyState icon={<Backpack size={32} />} title={t(pc + 'empty')} />
      )}

      {!current && <AttunementSection charId={charId} items={items} />}

      {childBoxes.length > 0 && (
        <section className="space-y-2 mb-4">
          <p className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright">
            {t('character.inventory.containers.section')}
          </p>
          {childBoxes.map((b) => (
            <div key={b.id}>{selectable(b.id, <ContainerCard item={b} onOpen={() => navigate(`/char/${charId}/inventory/c/${b.id}`)} />)}</div>
          ))}
        </section>
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
              <Pressable
                onClick={() => toggleType(type)}
                className={`sticky top-[calc(var(--crumb-offset,0px)-1rem)] z-[5] -mx-4 w-[calc(100%+2rem)] px-5 flex items-center gap-2 bg-dnd-bg border-b border-dnd-border/40 text-left min-h-[44px] ${isSingle ? 'py-1' : 'py-2'} ${scrolled ? 'pr-24' : ''}`}
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
                <span className="text-xs text-dnd-text-muted font-mono tabular-nums">
                  · {groupItems.length}
                </span>
              </Pressable>
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
                        // Niente `layout` per oggetto: framer rimisurava tutta la lista a ogni
                        // render (anche solo aprendo un dettaglio); come negli incantesimi.
                        <div
                          key={item.id}
                          ref={(el) => { itemRefs.current[item.id] = el }}
                          className={highlightId === item.id ? 'animate-pulse-glow' : undefined}
                        >
                          {selectable(item.id, <InventoryItem
                            item={item}
                            isExpanded={expanded === item.id}
                            onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                            onEquipToggle={() => handleEquipToggle(item)}
                            onQuantityChange={(delta) => updateQty.mutate({ itemId: item.id, quantity: item.quantity + delta })}
                            onAttack={(mode) => attackMutation.mutate({ itemId: item.id, mode })}
                            weaponChoice={choiceOf(weaponChoices, item.id)}
                            onWeaponChoice={(c) => setWeaponChoice(item.id, c)}
                            onUse={() => setUseTarget(item)}
                            onEdit={() => handleEdit(item)}
                            onDelete={() => setDeleteTarget(item.id)}
                            onShare={canShareMessage() ? () => shareItem.mutate(item.id) : undefined}
                            equipPending={toggleEquip.isPending && toggleEquip.variables?.itemId === item.id}
                            attackPending={attackMutation.isPending && attackMutation.variables?.itemId === item.id}
                            usePending={consumeMutation.isPending && consumeMutation.variables === item.id}
                            quantityPending={updateQty.isPending && updateQty.variables?.itemId === item.id}
                            sharePending={shareItem.isPending && shareItem.variables === item.id}
                            propertyByKey={propertyByKey}
                            locale={locale}
                            onSetProperty={handleSetProperty}
                            setPropertyPending={setPropertyMutation.isPending && setPropertyMutation.variables?.itemId === item.id}
                            onCharges={(delta) => chargesMutation.mutate({ itemId: item.id, delta })}
                            onCastSpell={(i) => itemCast.mutate({ itemId: item.id, spellIndex: i, name: itemGrantedSpells(item)[i]?.name ?? '' })}
                            chargesPending={chargesMutation.isPending && chargesMutation.variables?.itemId === item.id}
                            castPending={itemCast.isPending && itemCast.variables?.itemId === item.id}
                            onMove={() => setMoveTargets([item])}
                          />)}
                        </div>
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

      {newBox && (
        <ContainerForm
          onSubmit={(v) => addBoxMutation.mutate({ ...v, thenMove: newBox.thenMove })}
          onCancel={() => setNewBox(null)}
          isPending={addBoxMutation.isPending}
        />
      )}

      {moveTargets && !newBox && (
        <MoveSheet
          items={items}
          moving={moveTargets}
          currentId={moveTargets.every((i) => (i.container_id ?? null) === (moveTargets[0].container_id ?? null)) ? (moveTargets[0].container_id ?? null) : -1}
          onMove={(target, quantity) => moveMutation.mutate({ ids: moveTargets.map((i) => i.id), target, quantity })}
          onNewContainer={() => setNewBox({ thenMove: moveTargets })}
          onClose={() => setMoveTargets(null)}
          pending={moveMutation.isPending}
        />
      )}

      {itemCast.elements}

      {attackState && (
        <WeaponAttackModal
          result={attackState.result}
          inspirationAvailable={Boolean(char?.heroic_inspiration)}
          isRerolling={attackRerollMutation.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => attackRerollMutation.mutate({ itemId: attackState.itemId, choice: attackState.choice })}
          onClose={() => setAttackState(null)}
        />
      )}

      {/* Delete confirmation — ConfirmSheet condiviso (annulla sx, elimina dx) */}
      <ConfirmSheet
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget !== null && deleteMutation.mutate(deleteTarget)}
        title={t('common.confirm')}
        body={deleteBody}
        confirmLabel={t('common.delete')}
        loading={deleteMutation.isPending}
      />

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
                  <Pressable
                    key={slot}
                    onClick={() => doEquip(slotPickerItem, slot)}
                    pending={
                      toggleEquip.isPending &&
                      toggleEquip.variables?.itemId === slotPickerItem.id &&
                      toggleEquip.variables?.slot === slot
                    }
                    className="flex items-center gap-2 p-3 rounded-xl bg-dnd-surface border border-dnd-border hover:border-dnd-gold/60 disabled:opacity-50"
                    whileTap={{ scale: 0.96 }}
                  >
                    <Icon size={20} className="text-dnd-gold shrink-0" />
                    <span className="text-sm font-cinzel text-dnd-gold-bright">
                      {t(`character.equipment.slots.${slot}`)}
                    </span>
                  </Pressable>
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
    </Layout>
  )
}
