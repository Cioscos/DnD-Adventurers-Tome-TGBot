import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import Button from '@/components/ui/Button'
import IconButton from '@/components/ui/IconButton'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { resolveLabelI18n, type Locale } from '@/lib/homebrew/i18n-dsl'
import type { PassiveModifier } from '@/lib/homebrew/types'
import PassiveModifierFormModal from './PassiveModifierFormModal'

export interface PassiveModifiersSectionProps {
  mods: PassiveModifier[]
  onChange: (mods: PassiveModifier[]) => void
}

/**
 * Render the modifier target in plain language, e.g.
 *   character.ac                       -> "CA"
 *   character.skill.athletics          -> "Abilità: Atletica"
 *   character.saving_throw.dexterity   -> "Tiro salvezza: Destrezza"
 */
function targetLabel(target: string, t: TFunction): string {
  if (target === 'character.ac') return t('homebrew.passive.target_labels.ac')
  if (target === 'character.hit_points_max') return t('homebrew.passive.target_labels.hp_max')
  if (target === 'character.speed') return t('homebrew.passive.target_labels.speed')
  if (target.startsWith('character.skill.')) {
    const slug = target.slice('character.skill.'.length)
    return (
      t('homebrew.passive.target_labels.skill') +
      ': ' +
      t(`character.skills.${slug}`, { defaultValue: slug })
    )
  }
  if (target.startsWith('character.saving_throw.')) {
    const ability = target.slice('character.saving_throw.'.length)
    return (
      t('homebrew.passive.target_labels.save') +
      ': ' +
      t(`common.abilities.${ability}`, { defaultValue: ability })
    )
  }
  return target
}

/**
 * Format a numeric value with explicit +/- sign.
 * String values (dice notation, future-proofing) are passed through.
 */
function formatValue(value: number | string): string {
  if (typeof value === 'number') {
    return value >= 0 ? `+${value}` : `${value}`
  }
  return value
}

/**
 * Task 4.9 — Passive modifiers list editor.
 *
 * Each modifier applies automatically when its `when` filter matches. For MVP
 * the `when` field is fixed to a sentinel always-true filter (set inside
 * <PassiveModifierFormModal>); advanced conditional editing is deferred to a
 * future task.
 *
 * Renders one card per modifier (IT label + plain-language target + signed
 * value) plus an "+ Aggiungi modificatore" CTA. Edit/delete icon buttons on
 * each card open the modal form or a confirm sheet.
 */
export default function PassiveModifiersSection({ mods, onChange }: PassiveModifiersSectionProps) {
  const { t, i18n } = useTranslation()
  const locale: Locale = i18n.language?.startsWith('en') ? 'en' : 'it'
  const [modalOpen, setModalOpen] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [confirmDeleteIndex, setConfirmDeleteIndex] = useState<number | null>(null)

  const openAdd = () => {
    setEditingIndex(null)
    setModalOpen(true)
  }

  const openEdit = (index: number) => {
    setEditingIndex(index)
    setModalOpen(true)
  }

  const handleSave = (next: PassiveModifier) => {
    if (editingIndex === null) {
      onChange([...mods, next])
    } else {
      const copy = mods.slice()
      copy[editingIndex] = next
      onChange(copy)
    }
    setModalOpen(false)
  }

  const handleDelete = () => {
    if (confirmDeleteIndex === null) return
    const copy = mods.slice()
    copy.splice(confirmDeleteIndex, 1)
    onChange(copy)
    setConfirmDeleteIndex(null)
  }

  const deletingMod = confirmDeleteIndex !== null ? mods[confirmDeleteIndex] : null

  return (
    <div className="space-y-3">
      {mods.length === 0 ? (
        <p className="px-2 py-4 text-center text-sm font-body italic text-dnd-text-muted">
          {t('homebrew.passive.empty')}
        </p>
      ) : (
        <ul className="space-y-2">
          {mods.map((mod, index) => {
            const label = resolveLabelI18n(mod.label_i18n, locale, '?')
            return (
              <li
                key={`${mod.target}-${index}`}
                className="bg-dnd-surface-raised border border-dnd-border rounded-2xl p-3"
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-display font-bold text-dnd-text">{label}</div>
                    <div className="mt-1 text-[11px] text-dnd-text-muted font-body flex items-center gap-2 flex-wrap">
                      <span>{targetLabel(mod.target, t)}</span>
                      <span className="font-mono text-dnd-gold-bright">
                        {formatValue(mod.value)}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <IconButton
                      icon={<Pencil size={16} />}
                      onClick={() => openEdit(index)}
                      haptic="none"
                      className="w-11 h-11 rounded-lg text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface"
                      aria-label={t('common.edit')}
                    />
                    <IconButton
                      icon={<Trash2 size={16} />}
                      onClick={() => setConfirmDeleteIndex(index)}
                      haptic="none"
                      className="w-11 h-11 rounded-lg text-dnd-crimson hover:text-dnd-crimson-bright hover:bg-dnd-crimson/10"
                      aria-label={t('common.delete')}
                    />
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <Button variant="secondary" size="sm" icon={<Plus size={16} />} onClick={openAdd}>
        {t('homebrew.passive.add_button')}
      </Button>

      <PassiveModifierFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        initial={editingIndex !== null ? mods[editingIndex] : null}
        onSave={handleSave}
      />

      <ConfirmSheet
        open={confirmDeleteIndex !== null}
        onClose={() => setConfirmDeleteIndex(null)}
        onConfirm={handleDelete}
        title={t('common.delete')}
        body={
          deletingMod
            ? t('homebrew.passive.delete_confirm', {
                name: resolveLabelI18n(deletingMod.label_i18n, locale, '?'),
              })
            : ''
        }
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
      />
    </div>
  )
}
