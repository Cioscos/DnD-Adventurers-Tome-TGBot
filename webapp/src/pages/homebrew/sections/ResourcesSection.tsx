import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import Button from '@/components/ui/Button'
import IconButton from '@/components/ui/IconButton'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import type { ResourceDef } from '@/lib/homebrew/types'
import ResourceFormModal from './ResourceFormModal'

export interface ResourcesSectionProps {
  resources: ResourceDef[]
  onChange: (resources: ResourceDef[]) => void
}

/**
 * Resources list editor (#5 / F3-9). Lets the author declare ResourceDef rows
 * (key, name, max, restoration_type) that the backend materializes into
 * HomebrewResource. Without this the `resources` array stayed empty and custom
 * resources were only obtainable through templates. List orchestration only;
 * field validation lives in <ResourceFormModal>.
 */
export default function ResourcesSection({ resources, onChange }: ResourcesSectionProps) {
  const { t } = useTranslation()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [confirmDeleteIndex, setConfirmDeleteIndex] = useState<number | null>(null)

  const openAdd = () => { setEditingIndex(null); setModalOpen(true) }
  const openEdit = (index: number) => { setEditingIndex(index); setModalOpen(true) }

  const handleSave = (next: ResourceDef) => {
    if (editingIndex === null) {
      onChange([...resources, next])
    } else {
      const copy = resources.slice()
      copy[editingIndex] = next
      onChange(copy)
    }
    setModalOpen(false)
  }

  const handleDelete = () => {
    if (confirmDeleteIndex === null) return
    const copy = resources.slice()
    copy.splice(confirmDeleteIndex, 1)
    onChange(copy)
    setConfirmDeleteIndex(null)
  }

  const deleting = confirmDeleteIndex !== null ? resources[confirmDeleteIndex] : null

  return (
    <div className="space-y-3">
      {resources.length === 0 ? (
        <p className="px-2 py-4 text-center text-sm font-body italic text-dnd-text-muted">
          {t('homebrew.resources.empty')}
        </p>
      ) : (
        <ul className="space-y-2">
          {resources.map((res, index) => (
            <li
              key={`${res.key}-${index}`}
              className="bg-dnd-surface-raised border border-dnd-border rounded-2xl p-3"
            >
              <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-display font-bold text-dnd-text break-words">
                      {res.name}
                    </span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-dnd-chip-bg border border-dnd-border text-[11px] font-cinzel uppercase tracking-wider text-dnd-gold-dim">
                      {t('homebrew.resources.max_badge', { max: res.max })}
                    </span>
                  </div>
                  <div className="mt-1 text-[11px] text-dnd-text-muted font-body flex items-center gap-2 flex-wrap">
                    <code className="font-mono text-[11px] text-dnd-gold-dim">{res.key}</code>
                    <span>·</span>
                    <span>{t(`homebrew.resources.modal.restoration_${res.restoration_type}`)}</span>
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
          ))}
        </ul>
      )}

      <Button variant="secondary" size="sm" icon={<Plus size={16} />} onClick={openAdd}>
        {t('homebrew.resources.add_button')}
      </Button>

      <ResourceFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        initial={editingIndex !== null ? resources[editingIndex] : null}
        onSave={handleSave}
      />

      <ConfirmSheet
        open={confirmDeleteIndex !== null}
        onClose={() => setConfirmDeleteIndex(null)}
        onConfirm={handleDelete}
        title={t('common.delete')}
        body={deleting ? t('homebrew.resources.delete_confirm', { name: deleting.name }) : ''}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
      />
    </div>
  )
}
