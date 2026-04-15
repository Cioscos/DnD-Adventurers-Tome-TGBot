import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import { haptic } from '@/auth/telegram'
import AddClassForm, { resolveClassName, PREDEFINED_CLASSES, CUSTOM_KEY, type ClassForm } from '@/pages/multiclass/AddClassForm'
import ResourceManager from '@/pages/multiclass/ResourceManager'
import type { CharacterClass } from '@/types'

export default function Multiclass() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showAddClass, setShowAddClass] = useState(false)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const addClass = useMutation({
    mutationFn: (form: ClassForm) => {
      const rawKey = resolveClassName(form)
      const class_name = (form.class_key !== CUSTOM_KEY && PREDEFINED_CLASSES[rawKey])
        ? t(`dnd.classes.${rawKey}`)
        : rawKey
      return api.classes.add(charId, {
        class_name,
        level: Number(form.level),
        subclass: form.subclass.trim() || undefined,
        hit_die: Number(form.hit_die) || 8,
        spellcasting_ability: form.spellcasting_ability.trim() || undefined,
      })
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAddClass(false)
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
    mutationFn: ({ classId, payload }: { classId: number; payload: { name: string; total: number; current: number; restoration_type: string } }) =>
      api.classes.addResource(charId, classId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
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
    <Layout title={t('character.multiclass.title')} backTo={`/char/${charId}`} group="character" page="class">
      <DndButton onClick={() => setShowAddClass(true)} className="w-full">
        + {t('character.multiclass.add_class')}
      </DndButton>

      {classes.length === 0 && (
        <Card>
          <p className="text-center text-dnd-text-secondary">{t('common.none')}</p>
        </Card>
      )}

      {classes.map((cls) => (
        <Card key={cls.id}>
          <div className="flex items-start justify-between mb-2">
            <div>
              <span className="font-semibold text-lg">{cls.class_name}</span>
              {cls.subclass && (
                <span className="text-sm text-dnd-text-secondary ml-2">({cls.subclass})</span>
              )}
              {cls.hit_die && (
                <p className="text-xs text-dnd-text-secondary">d{cls.hit_die}{cls.spellcasting_ability ? ` \u00b7 ${cls.spellcasting_ability}` : ''}</p>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => updateLevel.mutate({ classId: cls.id, level: cls.level - 1 })}
                disabled={cls.level <= 1}
                className="w-7 h-7 rounded-lg bg-dnd-surface font-bold disabled:opacity-30"
              >&minus;</button>
              <span className="w-8 text-center font-bold">Lv {cls.level}</span>
              <button
                onClick={() => updateLevel.mutate({ classId: cls.id, level: cls.level + 1 })}
                disabled={cls.level >= 20}
                className="w-7 h-7 rounded-lg bg-dnd-surface font-bold disabled:opacity-30"
              >+</button>
              <button
                onClick={() => removeClass.mutate(cls.id)}
                className="text-xs text-[var(--dnd-danger)] ml-2"
              >&#x2715;</button>
            </div>
          </div>

          <ResourceManager
            classId={cls.id}
            resources={cls.resources}
            onUseResource={(classId, resId, current) =>
              useResource.mutate({ classId, resId, current })
            }
            onDeleteResource={(classId, resId) =>
              deleteResource.mutate({ classId, resId })
            }
            onAddResource={(classId, payload) =>
              addResource.mutate({ classId, payload })
            }
            addPending={addResource.isPending}
          />
        </Card>
      ))}

      {showAddClass && (
        <AddClassForm
          onAdd={(form) => addClass.mutate(form)}
          onCancel={() => setShowAddClass(false)}
          isPending={addClass.isPending}
        />
      )}
    </Layout>
  )
}
