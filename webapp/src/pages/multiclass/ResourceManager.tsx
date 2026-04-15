import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import type { ClassResource } from '@/types'

type ResForm = { name: string; total: string; current: string; restoration_type: string }

const emptyRes: ResForm = { name: '', total: '1', current: '1', restoration_type: 'long_rest' }

interface ResourceManagerProps {
  classId: number
  resources: ClassResource[]
  onUseResource: (classId: number, resId: number, current: number) => void
  onDeleteResource: (classId: number, resId: number) => void
  onAddResource: (classId: number, form: { name: string; total: number; current: number; restoration_type: string }) => void
  addPending: boolean
}

export default function ResourceManager({
  classId,
  resources,
  onUseResource,
  onDeleteResource,
  onAddResource,
  addPending,
}: ResourceManagerProps) {
  const { t } = useTranslation()
  const [showForm, setShowForm] = useState(false)
  const [resForm, setResForm] = useState<ResForm>(emptyRes)

  const handleAdd = () => {
    onAddResource(classId, {
      name: resForm.name.trim(),
      total: Number(resForm.total),
      current: Number(resForm.current),
      restoration_type: resForm.restoration_type,
    })
    setShowForm(false)
    setResForm(emptyRes)
  }

  return (
    <>
      {/* Existing resources */}
      {resources.length > 0 && (
        <div className="space-y-1 mb-2">
          {resources.map((res) => (
            <div key={res.id} className="flex items-center gap-2 text-sm">
              <span className="flex-1">{res.name}</span>
              <span className="text-dnd-text-secondary">
                {res.current}/{res.total}
              </span>
              <button
                onClick={() => onUseResource(classId, res.id, Math.max(0, res.current - 1))}
                disabled={res.current <= 0}
                className="w-6 h-6 rounded bg-[var(--dnd-danger)]/20 text-[var(--dnd-danger)] font-bold disabled:opacity-30"
              >-</button>
              <button
                onClick={() => onUseResource(classId, res.id, Math.min(res.total, res.current + 1))}
                disabled={res.current >= res.total}
                className="w-6 h-6 rounded bg-dnd-success/20 text-[#2ecc71] font-bold disabled:opacity-30"
              >+</button>
              <button
                onClick={() => onDeleteResource(classId, res.id)}
                className="text-xs text-[var(--dnd-danger)] ml-1"
              >&#x2715;</button>
            </div>
          ))}
        </div>
      )}

      {/* Add resource trigger */}
      <button
        onClick={() => { setShowForm(true); setResForm(emptyRes) }}
        className="text-xs text-dnd-gold"
      >
        + {t('character.multiclass.add_resource')}
      </button>

      {/* Add resource sheet */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full space-y-3">
            <h3 className="font-semibold">{t('character.multiclass.add_resource')}</h3>
            <DndInput
              value={resForm.name}
              onChange={(v) => setResForm((f) => ({ ...f, name: v }))}
              placeholder={t('character.multiclass.resource_name')}
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <DndInput
                  label={t('character.multiclass.resource_total')}
                  type="number"
                  min={1}
                  value={resForm.total}
                  onChange={(v) => setResForm((f) => ({ ...f, total: v }))}
                />
              </div>
              <div className="flex-1">
                <p className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
                  {t('character.multiclass.restoration')}
                </p>
                <select
                  value={resForm.restoration_type}
                  onChange={(e) => setResForm((f) => ({ ...f, restoration_type: e.target.value }))}
                  className="w-full bg-dnd-surface rounded-xl px-2 py-3 min-h-[48px] outline-none text-sm"
                >
                  <option value="long_rest">{t('character.abilities.restoration.long_rest')}</option>
                  <option value="short_rest">{t('character.abilities.restoration.short_rest')}</option>
                  <option value="manual">{t('character.abilities.restoration.manual')}</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <DndButton
                onClick={handleAdd}
                disabled={!resForm.name.trim()}
                loading={addPending}
                className="flex-1"
              >
                {t('common.add')}
              </DndButton>
              <DndButton
                variant="secondary"
                onClick={() => setShowForm(false)}
                className="flex-1"
              >
                {t('common.cancel')}
              </DndButton>
            </div>
          </Card>
        </div>
      )}
    </>
  )
}
