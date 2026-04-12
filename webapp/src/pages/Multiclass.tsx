import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { CharacterClass, ClassResource } from '@/types'

type ClassForm = { class_name: string; level: string; subclass: string; hit_die: string; spellcasting_ability: string }
type ResForm = { name: string; total: string; current: string; restoration_type: string }
const emptyClass: ClassForm = { class_name: '', level: '1', subclass: '', hit_die: '8', spellcasting_ability: '' }
const emptyRes: ResForm = { name: '', total: '1', current: '1', restoration_type: 'long_rest' }

export default function Multiclass() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showAddClass, setShowAddClass] = useState(false)
  const [classForm, setClassForm] = useState<ClassForm>(emptyClass)
  const [showAddRes, setShowAddRes] = useState<number | null>(null)
  const [resForm, setResForm] = useState<ResForm>(emptyRes)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const addClass = useMutation({
    mutationFn: () =>
      api.classes.add(charId, {
        class_name: classForm.class_name.trim(),
        level: Number(classForm.level),
        subclass: classForm.subclass.trim() || undefined,
        hit_die: Number(classForm.hit_die) || 8,
        spellcasting_ability: classForm.spellcasting_ability.trim() || undefined,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAddClass(false)
      setClassForm(emptyClass)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateLevel = useMutation({
    mutationFn: ({ classId, level }: { classId: number; level: number }) =>
      api.classes.update(charId, classId, { level: Math.max(1, level) }),
    onSuccess: (updated) => qc.setQueryData(['character', charId], updated),
  })

  const removeClass = useMutation({
    mutationFn: (classId: number) => api.classes.remove(charId, classId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
    },
  })

  const addResource = useMutation({
    mutationFn: (classId: number) =>
      api.classes.addResource(charId, classId, {
        name: resForm.name.trim(),
        total: Number(resForm.total),
        current: Number(resForm.current),
        restoration_type: resForm.restoration_type,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowAddRes(null)
      setResForm(emptyRes)
      haptic.success()
    },
  })

  const useResource = useMutation({
    mutationFn: ({ classId, resId, current }: { classId: number; resId: number; current: number }) =>
      api.classes.updateResource(charId, classId, resId, { current }),
    onSuccess: (updated) => qc.setQueryData(['character', charId], updated as typeof char),
  })

  const deleteResource = useMutation({
    mutationFn: ({ classId, resId }: { classId: number; resId: number }) =>
      api.classes.deleteResource(charId, classId, resId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  if (!char) return null

  const classes: CharacterClass[] = char.classes ?? []

  return (
    <Layout title={t('character.multiclass.title')} backTo={`/char/${charId}`}>
      <button
        onClick={() => setShowAddClass(true)}
        className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                   text-[var(--tg-theme-button-text-color)] font-semibold"
      >
        + {t('character.multiclass.add_class')}
      </button>

      {classes.length === 0 && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      )}

      {classes.map((cls) => (
        <Card key={cls.id}>
          <div className="flex items-start justify-between mb-2">
            <div>
              <span className="font-semibold text-lg">{cls.class_name}</span>
              {cls.subclass && (
                <span className="text-sm text-[var(--tg-theme-hint-color)] ml-2">({cls.subclass})</span>
              )}
              {cls.hit_die && (
                <p className="text-xs text-[var(--tg-theme-hint-color)]">d{cls.hit_die}{cls.spellcasting_ability ? ` · ${cls.spellcasting_ability}` : ''}</p>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => updateLevel.mutate({ classId: cls.id, level: cls.level - 1 })}
                disabled={cls.level <= 1}
                className="w-7 h-7 rounded-lg bg-white/10 font-bold disabled:opacity-30"
              >−</button>
              <span className="w-8 text-center font-bold">Lv {cls.level}</span>
              <button
                onClick={() => updateLevel.mutate({ classId: cls.id, level: cls.level + 1 })}
                disabled={cls.level >= 20}
                className="w-7 h-7 rounded-lg bg-white/10 font-bold disabled:opacity-30"
              >+</button>
              <button
                onClick={() => removeClass.mutate(cls.id)}
                className="text-xs text-red-400 ml-2"
              >✕</button>
            </div>
          </div>

          {/* Resources */}
          {cls.resources.length > 0 && (
            <div className="space-y-1 mb-2">
              {(cls.resources as ClassResource[]).map((res) => (
                <div key={res.id} className="flex items-center gap-2 text-sm">
                  <span className="flex-1">{res.name}</span>
                  <span className="text-[var(--tg-theme-hint-color)]">
                    {res.current}/{res.total}
                  </span>
                  <button
                    onClick={() => useResource.mutate({ classId: cls.id, resId: res.id, current: Math.max(0, res.current - 1) })}
                    disabled={res.current <= 0}
                    className="w-6 h-6 rounded bg-red-500/20 text-red-300 font-bold disabled:opacity-30"
                  >−</button>
                  <button
                    onClick={() => useResource.mutate({ classId: cls.id, resId: res.id, current: Math.min(res.total, res.current + 1) })}
                    disabled={res.current >= res.total}
                    className="w-6 h-6 rounded bg-green-500/20 text-green-300 font-bold disabled:opacity-30"
                  >+</button>
                  <button
                    onClick={() => deleteResource.mutate({ classId: cls.id, resId: res.id })}
                    className="text-xs text-red-400 ml-1"
                  >✕</button>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={() => { setShowAddRes(cls.id); setResForm(emptyRes) }}
            className="text-xs text-[var(--tg-theme-link-color)]"
          >
            + {t('character.multiclass.add_resource')}
          </button>
        </Card>
      ))}

      {/* Add class sheet */}
      {showAddClass && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full space-y-3">
            <h3 className="font-semibold">{t('character.multiclass.add_class')}</h3>
            <input
              type="text" value={classForm.class_name}
              onChange={(e) => setClassForm((f) => ({ ...f, class_name: e.target.value }))}
              placeholder={t('character.multiclass.class_name')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.multiclass.level')}</p>
                <input type="number" min="1" max="20" value={classForm.level}
                  onChange={(e) => setClassForm((f) => ({ ...f, level: e.target.value }))}
                  className="w-full bg-white/10 rounded-xl px-2 py-2 text-center outline-none"
                />
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.multiclass.hit_die')}</p>
                <select value={classForm.hit_die}
                  onChange={(e) => setClassForm((f) => ({ ...f, hit_die: e.target.value }))}
                  className="w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-2 py-2 outline-none"
                >
                  {[6,8,10,12].map((d) => <option key={d} value={d}>d{d}</option>)}
                </select>
              </div>
            </div>
            <input type="text" value={classForm.subclass}
              onChange={(e) => setClassForm((f) => ({ ...f, subclass: e.target.value }))}
              placeholder={t('character.multiclass.subclass')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none"
            />
            <input type="text" value={classForm.spellcasting_ability}
              onChange={(e) => setClassForm((f) => ({ ...f, spellcasting_ability: e.target.value }))}
              placeholder={t('character.multiclass.spellcasting')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none"
            />
            <div className="flex gap-2">
              <button
                onClick={() => addClass.mutate()}
                disabled={!classForm.class_name.trim() || addClass.isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                           text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
              >
                {addClass.isPending ? '...' : t('common.add')}
              </button>
              <button onClick={() => setShowAddClass(false)} className="flex-1 py-2 rounded-xl bg-white/10">
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* Add resource sheet */}
      {showAddRes !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full space-y-3">
            <h3 className="font-semibold">{t('character.multiclass.add_resource')}</h3>
            <input type="text" value={resForm.name}
              onChange={(e) => setResForm((f) => ({ ...f, name: e.target.value }))}
              placeholder={t('character.multiclass.resource_name')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.multiclass.resource_total')}</p>
                <input type="number" min="1" value={resForm.total}
                  onChange={(e) => setResForm((f) => ({ ...f, total: e.target.value }))}
                  className="w-full bg-white/10 rounded-xl px-2 py-2 text-center outline-none"
                />
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.multiclass.restoration')}</p>
                <select value={resForm.restoration_type}
                  onChange={(e) => setResForm((f) => ({ ...f, restoration_type: e.target.value }))}
                  className="w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-2 py-2 outline-none text-sm"
                >
                  <option value="long_rest">{t('character.abilities.restoration.long_rest')}</option>
                  <option value="short_rest">{t('character.abilities.restoration.short_rest')}</option>
                  <option value="manual">{t('character.abilities.restoration.manual')}</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => addResource.mutate(showAddRes)}
                disabled={!resForm.name.trim() || addResource.isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                           text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
              >
                {addResource.isPending ? '...' : t('common.add')}
              </button>
              <button onClick={() => setShowAddRes(null)} className="flex-1 py-2 rounded-xl bg-white/10">
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}
