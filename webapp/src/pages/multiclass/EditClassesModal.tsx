import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Check, Plus, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import { haptic } from '@/auth/telegram'
import { PREDEFINED_CLASSES, CUSTOM_KEY } from '@/pages/multiclass/AddClassForm'
import type { CharacterFull } from '@/types'

type ExistingEntry = {
  kind: 'existing'
  tempId: string
  classId: number
  className: string
  subclass: string | null
  level: number
}

type NewEntry = {
  kind: 'new'
  tempId: string
  classKey: string
  customName: string
  className: string
  subclass: string
  hitDie: number
  spellcasting?: string
  level: number
}

type Entry = ExistingEntry | NewEntry

interface Props {
  char: CharacterFull
  targetLevel: number
  onClose: () => void
}

function makeTempId(): string {
  return Math.random().toString(36).slice(2)
}

export default function EditClassesModal({ char, targetLevel, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [entries, setEntries] = useState<Entry[]>(() =>
    (char.classes ?? []).map((c) => ({
      kind: 'existing' as const,
      tempId: makeTempId(),
      classId: c.id,
      className: c.class_name,
      subclass: c.subclass ?? null,
      level: c.level,
    })),
  )

  const [showPicker, setShowPicker] = useState(false)
  const [pickerKey, setPickerKey] = useState<string>('')
  const [pickerCustomName, setPickerCustomName] = useState('')
  const [pickerSubclass, setPickerSubclass] = useState('')

  const currentSum = useMemo(
    () => entries.reduce((s, e) => s + (Number.isFinite(e.level) ? e.level : 0), 0),
    [entries],
  )
  const allLevelsValid = entries.every((e) => e.level >= 1 && e.level <= 20)
  const isValid = entries.length > 0 && allLevelsValid && currentSum === targetLevel

  const isDirty = useMemo(() => {
    const initial = new Map((char.classes ?? []).map((c) => [c.id, c.level]))
    if (entries.some((e) => e.kind === 'new')) return true
    return entries.some((e) => e.kind === 'existing' && initial.get(e.classId) !== e.level)
  }, [entries, char.classes])

  const setEntryLevel = (tempId: string, raw: number) => {
    const clamped = Math.max(1, Math.min(20, Math.round(raw)))
    setEntries((es) => es.map((e) => (e.tempId === tempId ? { ...e, level: clamped } : e)))
  }

  const removeNewEntry = (tempId: string) => {
    setEntries((es) => es.filter((e) => !(e.tempId === tempId && e.kind === 'new')))
  }

  const addPickedClass = () => {
    if (!pickerKey) return
    let className: string
    let hitDie: number
    let spellcasting: string | undefined

    if (pickerKey === CUSTOM_KEY) {
      const name = pickerCustomName.trim()
      if (!name) return
      className = name
      hitDie = 8
      spellcasting = undefined
    } else {
      className = t(`dnd.classes.${pickerKey}`)
      const attrs = PREDEFINED_CLASSES[pickerKey]
      hitDie = attrs?.hit_die ?? 8
      spellcasting = attrs?.spellcasting_ability ?? undefined
    }

    setEntries((es) => [
      ...es,
      {
        kind: 'new',
        tempId: makeTempId(),
        classKey: pickerKey,
        customName: pickerCustomName,
        className,
        subclass: pickerSubclass,
        hitDie,
        spellcasting,
        level: 1,
      },
    ])
    setShowPicker(false)
    setPickerKey('')
    setPickerCustomName('')
    setPickerSubclass('')
  }

  const commit = useMutation({
    mutationFn: async () => {
      const newEntries = entries.filter((e): e is NewEntry => e.kind === 'new')
      let updatedChar: CharacterFull = char
      const newIdByTempId = new Map<string, number>()

      for (const ne of newEntries) {
        const previousIds = new Set(updatedChar.classes.map((c) => c.id))
        updatedChar = (await api.classes.add(char.id, {
          class_name: ne.className,
          level: 1,
          hit_die: ne.hitDie,
          spellcasting_ability: ne.spellcasting,
          subclass: ne.subclass.trim() || undefined,
        })) as CharacterFull
        const newId = updatedChar.classes.find((c) => !previousIds.has(c.id))?.id
        if (newId == null) throw new Error('new class id missing after add')
        newIdByTempId.set(ne.tempId, newId)
      }

      const payload = entries.map((e) => {
        if (e.kind === 'existing') return { class_id: e.classId, level: e.level }
        const id = newIdByTempId.get(e.tempId)
        if (id == null) throw new Error('new class id lookup failed')
        return { class_id: id, level: e.level }
      })
      return api.classes.distribute(char.id, payload)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      onClose()
    },
    onError: () => {
      haptic.error()
      toast.error(t('character.multiclass.edit.error_server'))
    },
  })

  const classPickerKeys = Object.keys(PREDEFINED_CLASSES)

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-end sm:items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <m.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto"
      >
        <Surface variant="tome" ornamented className="space-y-6 p-6">
          <div className="text-center">
            <h2 className="font-display text-2xl font-black text-dnd-gold-bright uppercase tracking-widest">
              {t('character.multiclass.edit.title')}
            </h2>
            <p className="text-xs text-dnd-text-muted mt-1 font-body italic">
              {t('character.multiclass.edit.hint', { target: targetLevel })}
            </p>
          </div>

          {/* Sum indicator */}
          <div
            className={`text-center py-3 rounded-xl border transition-colors ${
              isValid
                ? 'bg-dnd-surface border-dnd-gold text-dnd-gold-bright'
                : 'bg-dnd-surface border-[var(--dnd-crimson)]/60 text-[var(--dnd-crimson-bright)]'
            }`}
          >
            <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] opacity-80">
              {t('character.multiclass.edit.sum_label')}
            </p>
            <p className="font-display font-black text-3xl">
              {t('character.multiclass.edit.sum_display', { current: currentSum, target: targetLevel })}
            </p>
          </div>

          {/* Entries + add class (grouped section) */}
          <div className="space-y-4">
            <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim text-center">
              {t('character.multiclass.edit.classes_label')}
            </p>
            {entries.map((e) => (
              <Surface key={e.tempId} variant="elevated" className="flex items-center gap-4 !py-3 !px-4">
                <div className="flex-1 min-w-0">
                  <p className="font-display font-bold text-dnd-gold-bright truncate">
                    {e.className}
                    {e.kind === 'new' && (
                      <span className="ml-2 text-[10px] font-cinzel uppercase tracking-widest text-dnd-amber">
                        {t('character.multiclass.edit.new_tag')}
                      </span>
                    )}
                  </p>
                  {e.subclass && (
                    <p className="text-xs text-dnd-text-muted italic truncate">{e.subclass}</p>
                  )}
                </div>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={20}
                  value={e.level}
                  onChange={(ev) => setEntryLevel(e.tempId, Number(ev.target.value))}
                  className="w-20 min-h-[44px] rounded-lg bg-dnd-surface border border-dnd-border text-dnd-gold-bright font-mono text-center"
                  aria-label={`${e.className} level`}
                />
                {e.kind === 'new' && (
                  <button
                    type="button"
                    onClick={() => removeNewEntry(e.tempId)}
                    className="w-9 h-9 rounded-lg text-[var(--dnd-crimson-bright)] flex items-center justify-center hover:bg-[var(--dnd-crimson)]/10"
                    aria-label={t('character.multiclass.edit.remove_new')}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </Surface>
            ))}

            {/* Add class trigger (inside classes section, separated by pt-2) */}
            <div className="pt-2">
              <Button
                variant="secondary"
                size="md"
                fullWidth
                icon={<Plus size={16} />}
                onClick={() => setShowPicker(true)}
                haptic="light"
              >
                {t('character.multiclass.add_class')}
              </Button>
            </div>
          </div>

          {/* Footer — visually separated */}
          <div className="pt-5 border-t border-dnd-border/50 grid grid-cols-2 gap-3">
            <Button variant="ghost" size="md" fullWidth onClick={onClose}>
              {t('character.multiclass.edit.cancel')}
            </Button>
            <Button
              variant="primary"
              size="md"
              fullWidth
              disabled={!isValid || !isDirty}
              loading={commit.isPending}
              icon={<Check size={16} />}
              haptic="success"
              onClick={() => commit.mutate()}
            >
              {t('character.multiclass.edit.confirm')}
            </Button>
          </div>
        </Surface>
      </m.div>

      {/* Nested picker overlay — higher z-index sits above the edit modal */}
      {showPicker && (
        <div
          className="fixed inset-0 bg-black/75 z-[60] flex items-end sm:items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          onClick={(ev) => {
            if (ev.target === ev.currentTarget) {
              setShowPicker(false)
              setPickerKey('')
              setPickerCustomName('')
              setPickerSubclass('')
            }
          }}
        >
          <m.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="w-full max-w-md max-h-[90vh] overflow-y-auto"
          >
            <Surface variant="arcane" ornamented className="space-y-5 p-6">
              <div className="text-center">
                <h3 className="font-display text-xl font-black text-dnd-gold-bright uppercase tracking-widest">
                  {t('character.multiclass.add_class')}
                </h3>
              </div>

              <div className="space-y-3">
                <select
                  value={pickerKey}
                  onChange={(ev) => setPickerKey(ev.target.value)}
                  className="w-full bg-dnd-surface rounded-xl px-3 py-2 min-h-[44px] outline-none"
                >
                  <option value="" disabled>
                    {t('character.multiclass.class_name')}
                  </option>
                  {classPickerKeys.map((k) => (
                    <option key={k} value={k}>
                      {t(`dnd.classes.${k}`)}
                    </option>
                  ))}
                  <option value={CUSTOM_KEY}>{t('character.multiclass.custom_class')}</option>
                </select>

                {pickerKey === CUSTOM_KEY && (
                  <input
                    type="text"
                    value={pickerCustomName}
                    onChange={(ev) => setPickerCustomName(ev.target.value)}
                    placeholder={t('character.multiclass.custom_class_name')}
                    className="w-full bg-dnd-surface rounded-xl px-3 py-2 min-h-[44px] outline-none"
                  />
                )}

                <input
                  type="text"
                  value={pickerSubclass}
                  onChange={(ev) => setPickerSubclass(ev.target.value)}
                  placeholder={t('character.multiclass.subclass')}
                  className="w-full bg-dnd-surface rounded-xl px-3 py-2 min-h-[44px] outline-none"
                />
              </div>

              <div className="pt-4 border-t border-dnd-border/50 grid grid-cols-2 gap-3">
                <Button
                  variant="danger"
                  size="md"
                  fullWidth
                  icon={<X size={16} />}
                  onClick={() => {
                    setShowPicker(false)
                    setPickerKey('')
                    setPickerCustomName('')
                    setPickerSubclass('')
                  }}
                >
                  {t('character.multiclass.edit.cancel')}
                </Button>
                <Button
                  variant="arcane"
                  size="md"
                  fullWidth
                  disabled={!pickerKey || (pickerKey === CUSTOM_KEY && !pickerCustomName.trim())}
                  onClick={addPickedClass}
                  icon={<Plus size={16} />}
                  haptic="light"
                >
                  {t('common.add')}
                </Button>
              </div>
            </Surface>
          </m.div>
        </div>
      )}
    </div>
  )
}
