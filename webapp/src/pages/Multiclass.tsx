import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { X, Edit3 } from 'lucide-react'
import { GiCrossedSwords as Swords, GiScrollUnfurled as Scroll } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import { FlourishDivider } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { levelFromXp } from '@/lib/xpThresholds'
import ResourceManager from '@/pages/multiclass/ResourceManager'
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import EditClassesModal from '@/pages/multiclass/EditClassesModal'
import type { CharacterClass } from '@/types'

export default function Multiclass() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showLevelUpModal, setShowLevelUpModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
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
  const classLevelSum = classes.reduce((s, c) => s + c.level, 0)
  const targetLevel = levelFromXp(char.experience_points ?? 0)
  const levelUpAvailable = classes.length > 0 && targetLevel > classLevelSum

  return (
    <Layout title={t('character.multiclass.title')} backTo={`/char/${charId}`} group="character" page="class">
      {/* Total level hero (only if has classes) */}
      {classes.length > 0 && (
        <Surface variant="tome" ornamented className="text-center">
          <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim mb-1">
            {t('character.multiclass.total_level', { defaultValue: 'Livello totale' })}
          </p>
          <p className="text-5xl font-display font-black text-dnd-gold-bright"
             style={{ textShadow: '0 2px 8px var(--dnd-gold-glow)' }}>
            {targetLevel}
          </p>
        </Surface>
      )}

      {levelUpAvailable && (
        <LevelUpBanner
          onOpen={() => setShowLevelUpModal(true)}
          labelKey="character.xp.level_up_available_short"
        />
      )}

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => setShowEditModal(true)}
        icon={<Edit3 size={18} />}
        haptic="medium"
      >
        {t('character.multiclass.edit_classes')}
      </Button>

      {classes.length === 0 && (
        <Surface variant="flat" className="text-center py-8">
          <Swords className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('common.none')}</p>
        </Surface>
      )}

      {classes.map((cls, idx) => (
        <m.div
          key={cls.id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: idx * 0.05 }}
        >
          <Surface variant="elevated" ornamented>
            {/* Class banner */}
            <div className="mb-3">
              <div className="flex items-start gap-2 mb-1">
                <Scroll size={16} className="text-dnd-gold shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="font-display font-bold text-lg text-dnd-gold-bright">{cls.class_name}</span>
                    {cls.subclass && (
                      <span className="text-sm text-dnd-text-muted italic font-body">({cls.subclass})</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    {cls.hit_die && <StatPill tone="gold" size="sm" value={`d${cls.hit_die}`} />}
                    {cls.spellcasting_ability && (
                      <StatPill tone="arcane" size="sm" value={cls.spellcasting_ability} />
                    )}
                  </div>
                </div>
                <m.button
                  onClick={() => removeClass.mutate(cls.id)}
                  className="w-7 h-7 rounded-lg text-[var(--dnd-crimson-bright)] flex items-center justify-center hover:bg-[var(--dnd-crimson)]/10 shrink-0"
                  whileTap={{ scale: 0.9 }}
                  aria-label="Remove"
                >
                  <X size={14} />
                </m.button>
              </div>
              <div className="text-dnd-gold-dim my-2">
                <FlourishDivider />
              </div>

              {/* Level display (read-only; change via modals) */}
              <div className="flex items-center gap-2">
                <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
                  {t('character.multiclass.level')}
                </p>
                <span className="font-display font-black text-2xl text-dnd-gold-bright">
                  {cls.level}
                </span>
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
          </Surface>
        </m.div>
      ))}

      {showLevelUpModal && (
        <LevelUpModal
          char={char}
          xpLevel={targetLevel}
          onClose={() => setShowLevelUpModal(false)}
        />
      )}

      {showEditModal && (
        <EditClassesModal
          char={char}
          targetLevel={targetLevel}
          onClose={() => setShowEditModal(false)}
        />
      )}
    </Layout>
  )
}
