import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { X, Edit3, Plus } from 'lucide-react'
import { GiCrossedSwords as Swords, GiScrollUnfurled as Scroll } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { FlourishDivider } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { levelFromXp } from '@/lib/xpThresholds'
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import EditClassesModal from '@/pages/multiclass/EditClassesModal'
import type { CharacterClass } from '@/types'
import MulticlassSkeleton from '@/components/skeletons/MulticlassSkeleton'

export default function Multiclass() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showLevelUpModal, setShowLevelUpModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<CharacterClass | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const removeClass = useMutation({
    mutationFn: (classId: number) => api.classes.remove(charId, classId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
      setRemoveTarget(null)
    },
  })

  const classes: CharacterClass[] = char?.classes ?? []

  if (!char) {
    return (
      <Layout title={t('character.multiclass.title')} backTo={`/char/${charId}`} group="character" page="class">
        <MulticlassSkeleton />
      </Layout>
    )
  }

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
          {levelUpAvailable && (
            <p className="mt-1 text-[10px] font-mono text-dnd-text-muted tabular-nums">
              {t('character.xp.level_distributed_hint', {
                distributed: classLevelSum,
                pending: targetLevel - classLevelSum,
              })}
            </p>
          )}
        </Surface>
      )}

      {levelUpAvailable && (
        <LevelUpBanner
          onOpen={() => setShowLevelUpModal(true)}
          labelKey="character.xp.level_up_available_short"
        />
      )}

      {classes.length > 0 && (
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={() => setShowEditModal(true)}
          icon={<Edit3 size={18} />}
          haptic="medium"
        >
          {t('character.multiclass.manage_classes')}
        </Button>
      )}

      {classes.length === 0 && (
        <EmptyState
          icon={<Swords size={32} />}
          title={t('character.multiclass.empty_state_title')}
          action={{
            label: t('character.multiclass.empty_cta'),
            onClick: () => setShowEditModal(true),
            icon: <Plus size={14} />,
          }}
        />
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
                      <StatPill
                        tone="arcane"
                        size="sm"
                        value={t(`common.abilities.${cls.spellcasting_ability.toLowerCase()}`, {
                          defaultValue: cls.spellcasting_ability,
                        })}
                      />
                    )}
                  </div>
                </div>
                <m.button
                  onClick={() => setRemoveTarget(cls)}
                  className="w-11 h-11 rounded-lg text-[var(--dnd-crimson-bright)] flex items-center justify-center hover:bg-dnd-crimson/10 shrink-0"
                  whileTap={{ scale: 0.9 }}
                  aria-label="Remove"
                >
                  <X size={16} />
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

      <ConfirmSheet
        open={removeTarget !== null}
        onClose={() => setRemoveTarget(null)}
        onConfirm={() => {
          if (removeTarget) removeClass.mutate(removeTarget.id)
        }}
        title={t('character.multiclass.remove_class_title')}
        body={
          removeTarget
            ? t('character.multiclass.remove_class_body', { name: removeTarget.class_name })
            : ''
        }
        confirmLabel={t('common.delete')}
        confirmVariant="danger"
        loading={removeClass.isPending}
      />
    </Layout>
  )
}
