import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import Button from '@/components/ui/Button'
import IconButton from '@/components/ui/IconButton'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { resolveLabelI18n, type Locale } from '@/lib/homebrew/i18n-dsl'
import type { Property } from '@/lib/homebrew/types'
import PropertyFormModal from './PropertyFormModal'

export interface PropertiesSectionProps {
  properties: Property[]
  onChange: (properties: Property[]) => void
}

/**
 * Render the "default" value of a property as a human-readable string.
 * Numbers and strings stringify directly; otherwise the rendering falls
 * back to JSON.stringify for safety. Boolean defaults are handled at the
 * call site so they can use the i18n `common.yes` / `common.no` keys.
 */
function formatDefault(prop: Property): string {
  const v = prop.default
  if (typeof v === 'string') return v
  if (typeof v === 'number') return String(v)
  return JSON.stringify(v)
}

/**
 * Task 4.7 — Properties list editor.
 *
 * Renders one card per property (label, type badge, key, default, enum
 * value chips) plus an "+ Aggiungi caratteristica" CTA. Edit/delete icon
 * buttons on each card open the modal form or a confirm sheet.
 *
 * Validation (label_i18n IT+EN, key regex, enum non-empty default-in-values)
 * lives inside <PropertyFormModal>; this component is responsible only for
 * the list rendering and the splice/replace orchestration.
 */
export default function PropertiesSection({ properties, onChange }: PropertiesSectionProps) {
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

  const handleSave = (next: Property) => {
    if (editingIndex === null) {
      onChange([...properties, next])
    } else {
      const copy = properties.slice()
      copy[editingIndex] = next
      onChange(copy)
    }
    setModalOpen(false)
  }

  const handleDelete = () => {
    if (confirmDeleteIndex === null) return
    const copy = properties.slice()
    copy.splice(confirmDeleteIndex, 1)
    onChange(copy)
    setConfirmDeleteIndex(null)
  }

  const deletingProp =
    confirmDeleteIndex !== null ? properties[confirmDeleteIndex] : null

  return (
    <div className="space-y-3">
      {properties.length === 0 ? (
        <p className="px-2 py-4 text-center text-sm font-body italic text-dnd-text-muted">
          {t('homebrew.properties.empty')}
        </p>
      ) : (
        <ul className="space-y-2">
          {properties.map((prop, index) => {
            const label = resolveLabelI18n(prop.label_i18n, locale, prop.key)
            return (
              <li
                key={`${prop.key}-${index}`}
                className="bg-dnd-surface-raised border border-dnd-border rounded-2xl p-3"
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-display font-bold text-dnd-text">
                        {label}
                      </span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-dnd-chip-bg border border-dnd-border text-[11px] font-cinzel uppercase tracking-wider text-dnd-gold-dim">
                        {t(`homebrew.properties.type_badge.${prop.type}`)}
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] text-dnd-text-muted font-body flex items-center gap-2 flex-wrap">
                      <code className="font-mono text-[11px] text-dnd-gold-dim">
                        {prop.key}
                      </code>
                      <span>·</span>
                      <span>
                        {t('homebrew.properties.default_label')}:{' '}
                        <span className="text-dnd-text">
                          {prop.type === 'boolean'
                            ? prop.default
                              ? t('common.yes')
                              : t('common.no')
                            : formatDefault(prop)}
                        </span>
                      </span>
                    </div>
                    {prop.type === 'enum' && prop.values && prop.values.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {prop.values.map((v) => (
                          <span
                            key={v}
                            className="inline-flex items-center px-1.5 py-0.5 rounded-full bg-dnd-chip-bg text-[11px] font-mono text-dnd-text-muted"
                          >
                            {v}
                          </span>
                        ))}
                      </div>
                    )}
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

      <Button
        variant="secondary"
        size="sm"
        icon={<Plus size={16} />}
        onClick={openAdd}
      >
        {t('homebrew.properties.add_button')}
      </Button>

      <PropertyFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        initial={editingIndex !== null ? properties[editingIndex] : null}
        onSave={handleSave}
      />

      <ConfirmSheet
        open={confirmDeleteIndex !== null}
        onClose={() => setConfirmDeleteIndex(null)}
        onConfirm={handleDelete}
        title={t('common.delete')}
        body={
          deletingProp
            ? t('homebrew.properties.delete_confirm', {
                name: resolveLabelI18n(deletingProp.label_i18n, locale, deletingProp.key),
              })
            : ''
        }
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
      />
    </div>
  )
}
