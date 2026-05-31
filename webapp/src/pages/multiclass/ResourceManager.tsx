import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import { useRegisterOverlay } from '@/store/overlayStore'
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
  useRegisterOverlay(showForm)

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
      {/* Existing resources — skip 0/0 entries (typically locked class features
          like Channel Divinity at lv1 Paladin that unlock at higher levels). */}
      {resources.length > 0 && (
        <div className="space-y-3 mb-3">
          {resources.filter((r) => r.total > 0).map((res) => (
            <div key={res.id} className="space-y-1">
              {/* Stepper row: name · current/total · −/+ da 44px ben distanziati */}
              <div className="flex items-center gap-3 text-sm">
                <span className="flex-1 min-w-0 truncate">{res.name}</span>
                <button
                  onClick={() => onUseResource(classId, res.id, Math.max(0, res.current - 1))}
                  disabled={res.current <= 0}
                  aria-label={t('character.multiclass.use_resource')}
                  className="w-11 h-11 shrink-0 rounded-lg bg-[var(--dnd-danger)]/20 text-[var(--dnd-danger)] text-xl font-bold leading-none disabled:opacity-30"
                >-</button>
                <span className="font-mono tabular-nums text-base min-w-[44px] text-center">
                  {res.current}/{res.total}
                </span>
                <button
                  onClick={() => onUseResource(classId, res.id, Math.min(res.total, res.current + 1))}
                  disabled={res.current >= res.total}
                  aria-label={t('character.multiclass.restore_resource')}
                  className="w-11 h-11 shrink-0 rounded-lg bg-dnd-success/20 text-dnd-success-text text-xl font-bold leading-none disabled:opacity-30"
                >+</button>
              </div>
              {/* Destructive action on its own row, no longer adjacent to + */}
              <div className="flex justify-end">
                <button
                  onClick={() => onDeleteResource(classId, res.id)}
                  className="inline-flex items-center min-h-[44px] px-2 text-xs text-[var(--dnd-danger)] opacity-70"
                >
                  {t('character.multiclass.remove_resource')}
                </button>
              </div>
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
