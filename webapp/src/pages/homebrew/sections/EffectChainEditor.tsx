import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from 'lucide-react'
import Button from '@/components/ui/Button'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Sheet from '@/components/ui/Sheet'
import { actionLabel, type Locale } from '@/lib/homebrew/i18n-dsl'
import type { Effect, EffectAction, Table } from '@/lib/homebrew/types'
import EffectFormModal, { defaultEffect } from './EffectFormModal'

const ACTION_TYPES: readonly EffectAction[] = [
  'roll_dice',
  'lookup_table',
  'match',
  'if',
  'set_property',
  'inc_property',
  'unequip',
  'damage_character',
  'heal_character',
  'change_resource',
  'restore_resource',
  'apply_condition',
  'remove_condition',
  'apply_modifier_once',
  'notify',
  'add_history',
] as const

export interface EffectChainEditorProps {
  effects: Effect[]
  tables?: Table[]
  onChange: (effects: Effect[]) => void
  /** Visual indent depth for nested if/match branches. 0 by default. */
  depth?: number
}

/**
 * Task 4.11 — Recursive editor for an Effect[] chain.
 *
 * Numbered card list, action-specific edit modal (EffectFormModal), and
 * indented sub-editors for branching actions (`if.then`, `if.else`,
 * `match.cases`). Each EffectChainEditor instance numbers its own list
 * 1..N — depth alone communicates nesting (no compound numbering).
 */
export default function EffectChainEditor({
  effects,
  tables,
  onChange,
  depth = 0,
}: EffectChainEditorProps) {
  const { t, i18n } = useTranslation()
  const locale: Locale = i18n.language?.startsWith('en') ? 'en' : 'it'

  const [pickerOpen, setPickerOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [draftEffect, setDraftEffect] = useState<Effect | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [confirmDeleteIndex, setConfirmDeleteIndex] = useState<number | null>(null)

  const openPicker = () => {
    setEditingIndex(null)
    setDraftEffect(null)
    setPickerOpen(true)
  }

  const handlePick = (action: EffectAction) => {
    setPickerOpen(false)
    setDraftEffect(defaultEffect(action))
    setModalOpen(true)
  }

  const openEdit = (index: number) => {
    setEditingIndex(index)
    setDraftEffect(effects[index])
    setModalOpen(true)
  }

  const handleSave = (next: Effect) => {
    if (editingIndex === null) {
      onChange([...effects, next])
    } else {
      const copy = effects.slice()
      copy[editingIndex] = next
      onChange(copy)
    }
    setModalOpen(false)
    setDraftEffect(null)
    setEditingIndex(null)
  }

  const move = (index: number, dir: -1 | 1) => {
    const target = index + dir
    if (target < 0 || target >= effects.length) return
    const copy = effects.slice()
    const [item] = copy.splice(index, 1)
    copy.splice(target, 0, item)
    onChange(copy)
  }

  const handleDelete = () => {
    if (confirmDeleteIndex === null) return
    const copy = effects.slice()
    copy.splice(confirmDeleteIndex, 1)
    onChange(copy)
    setConfirmDeleteIndex(null)
  }

  // Branch mutators — used by nested editors.
  const updateBranch = (index: number, patch: Partial<Effect>) => {
    const copy = effects.slice()
    copy[index] = { ...copy[index], ...patch } as Effect
    onChange(copy)
  }

  return (
    <div
      className="space-y-2"
      style={depth > 0 ? { paddingLeft: depth * 16 } : undefined}
    >
      {effects.length === 0 ? (
        <p className="px-2 py-3 text-center text-xs font-body italic text-dnd-text-muted">
          {t('homebrew.effects.empty')}
        </p>
      ) : (
        <ul className="space-y-2">
          {effects.map((effect, index) => (
            <li key={index} className="space-y-2">
              <EffectCard
                effect={effect}
                index={index}
                total={effects.length}
                locale={locale}
                onMoveUp={() => move(index, -1)}
                onMoveDown={() => move(index, 1)}
                onEdit={() => openEdit(index)}
                onDelete={() => setConfirmDeleteIndex(index)}
              />

              {/* Nested branches */}
              {effect.action === 'if' && (
                <IfBranches
                  effect={effect}
                  tables={tables}
                  depth={depth + 1}
                  onChange={(patch) => updateBranch(index, patch)}
                />
              )}
              {effect.action === 'match' && (
                <MatchBranches
                  effect={effect}
                  tables={tables}
                  depth={depth + 1}
                  onChange={(cases) => updateBranch(index, { cases } as Partial<Effect>)}
                />
              )}
            </li>
          ))}
        </ul>
      )}

      <Button
        variant="secondary"
        size="sm"
        icon={<Plus size={14} />}
        onClick={openPicker}
      >
        {t('homebrew.effects.add_step')}
      </Button>

      {/* Action-type picker */}
      <ActionPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={handlePick}
      />

      {/* Per-action form */}
      <EffectFormModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false)
          setDraftEffect(null)
          setEditingIndex(null)
        }}
        effect={draftEffect}
        tables={tables}
        onSave={handleSave}
      />

      {/* Delete confirm */}
      <ConfirmSheet
        open={confirmDeleteIndex !== null}
        onClose={() => setConfirmDeleteIndex(null)}
        onConfirm={handleDelete}
        title={t('common.delete')}
        body={t('homebrew.effects.delete_confirm')}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

interface CardProps {
  effect: Effect
  index: number
  total: number
  locale: Locale
  onMoveUp: () => void
  onMoveDown: () => void
  onEdit: () => void
  onDelete: () => void
}

function EffectCard({
  effect,
  index,
  total,
  locale,
  onMoveUp,
  onMoveDown,
  onEdit,
  onDelete,
}: CardProps) {
  return (
    <div className="bg-dnd-surface-raised border border-dnd-border rounded-2xl p-3">
      <div className="flex items-start gap-2">
        <div className="shrink-0 w-7 h-7 rounded-full bg-dnd-gold-bright/15 text-dnd-gold-bright font-mono text-xs inline-flex items-center justify-center">
          {index + 1}
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <p className="text-sm font-body text-dnd-text break-words">
            {actionLabel(effect, locale)}
          </p>
        </div>
        <div className="flex flex-col gap-0.5 shrink-0">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={index === 0}
            className="w-11 h-11 inline-flex items-center justify-center rounded-lg text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface transition-colors disabled:opacity-30 disabled:pointer-events-none"
            aria-label="Move up"
          >
            <ChevronUp size={16} />
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={index === total - 1}
            className="w-11 h-11 inline-flex items-center justify-center rounded-lg text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface transition-colors disabled:opacity-30 disabled:pointer-events-none"
            aria-label="Move down"
          >
            <ChevronDown size={16} />
          </button>
          <button
            type="button"
            onClick={onEdit}
            className="w-11 h-11 inline-flex items-center justify-center rounded-lg text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface transition-colors"
            aria-label="Edit"
          >
            <Pencil size={16} />
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="w-11 h-11 inline-flex items-center justify-center rounded-lg text-dnd-crimson hover:text-dnd-crimson-bright hover:bg-dnd-crimson/10 transition-colors"
            aria-label="Delete"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Branches: if (then / else)
// ---------------------------------------------------------------------------

interface IfBranchesProps {
  effect: Extract<Effect, { action: 'if' }>
  tables?: Table[]
  depth: number
  onChange: (patch: Partial<Effect>) => void
}

function IfBranches({ effect, tables, depth, onChange }: IfBranchesProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-2">
      <BranchLabel label={t('homebrew.effects.branch_then')} depth={depth} />
      <EffectChainEditor
        effects={effect.then}
        tables={tables}
        depth={depth}
        onChange={(then) => onChange({ then } as Partial<Effect>)}
      />

      <BranchLabel label={t('homebrew.effects.branch_else')} depth={depth} />
      <EffectChainEditor
        effects={effect.else ?? []}
        tables={tables}
        depth={depth}
        onChange={(els) =>
          onChange({ else: els.length === 0 ? undefined : els } as Partial<Effect>)
        }
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Branches: match (cases)
// ---------------------------------------------------------------------------

interface MatchBranchesProps {
  effect: Extract<Effect, { action: 'match' }>
  tables?: Table[]
  depth: number
  onChange: (cases: Record<string, Effect[]>) => void
}

function MatchBranches({ effect, tables, depth, onChange }: MatchBranchesProps) {
  const keys = Object.keys(effect.cases)
  return (
    <div className="space-y-2">
      {keys.map((k) => (
        <div key={k} className="space-y-2">
          <BranchLabel label={`"${k}"`} depth={depth} mono />
          <EffectChainEditor
            effects={effect.cases[k]}
            tables={tables}
            depth={depth}
            onChange={(branch) => onChange({ ...effect.cases, [k]: branch })}
          />
        </div>
      ))}
    </div>
  )
}

function BranchLabel({
  label,
  depth,
  mono = false,
}: {
  label: string
  depth: number
  mono?: boolean
}) {
  return (
    <div
      className="flex items-center gap-2"
      style={{ paddingLeft: depth * 16 }}
    >
      <span className="w-3 h-px bg-dnd-gold-dim/50" aria-hidden />
      <span
        className={`text-[10px] uppercase tracking-widest font-cinzel font-bold text-dnd-gold-dim ${
          mono ? 'font-mono normal-case tracking-normal' : ''
        }`}
      >
        {label}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Action picker
// ---------------------------------------------------------------------------

function ActionPicker({
  open,
  onClose,
  onPick,
}: {
  open: boolean
  onClose: () => void
  onPick: (action: EffectAction) => void
}) {
  const { t } = useTranslation()
  return (
    <Sheet open={open} onClose={onClose} title={t('homebrew.effects.action_picker_title')} centered>
      <div className="p-5">
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {ACTION_TYPES.map((action) => (
            <li key={action}>
              <button
                type="button"
                onClick={() => onPick(action)}
                className="w-full min-h-[48px] px-3 py-2.5 rounded-xl bg-dnd-surface-raised border border-dnd-border hover:border-dnd-gold/70 text-left text-sm font-body text-dnd-text transition-colors"
              >
                {t(`homebrew.effects.actions.${action}`)}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </Sheet>
  )
}
