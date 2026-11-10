import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { classLabel } from '@/lib/classLabel'
import { m } from 'framer-motion'
import { X, Edit3, Plus } from 'lucide-react'
import { GiCrossedSwords as Swords } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import EmptyState from '@/components/ui/EmptyState'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import { haptic } from '@/auth/telegram'
import { LEDGER_LABEL } from '@/styles/ledger'
import { displayedTotalLevel, levelFromXp } from '@/lib/xpThresholds'
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import EditClassesModal from '@/pages/multiclass/EditClassesModal'
import ClassOptionGroups from '@/pages/multiclass/ClassOptionGroups'
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
  // Milestone: no XP cap, the user raises levels freely (up to 20 total).
  const milestone = char.settings?.advancement === 'milestone'
  const targetLevel = milestone ? Math.min(20, classLevelSum + 1) : levelFromXp(char.experience_points ?? 0)
  const levelUpAvailable = classes.length > 0 && targetLevel > classLevelSum

  return (
    <Layout title={t('character.multiclass.title')} backTo={`/char/${charId}`} group="character" page="class">
      {/* Total level hero (only if has classes) */}
      {classes.length > 0 && (
        <div className="flex items-baseline justify-between gap-3 px-1">
          <p className={LEDGER_LABEL}>
            {t('character.multiclass.total_level', { defaultValue: 'Livello totale' })}
          </p>
          <p className="text-right font-display text-5xl font-black leading-none text-dnd-gold-bright">
            {displayedTotalLevel(classLevelSum, milestone, char.experience_points ?? 0)}
          </p>
        </div>
      )}
      {classes.length > 0 && levelUpAvailable && !milestone && (
        <p className="-mt-1 px-1 text-right text-xs font-mono text-dnd-text-muted tabular-nums">
          {t('character.xp.level_distributed_hint', {
            distributed: classLevelSum,
            pending: targetLevel - classLevelSum,
          })}
        </p>
      )}

      {levelUpAvailable && (
        <LevelUpBanner
          onOpen={() => setShowLevelUpModal(true)}
          labelKey="character.xp.level_up_available_short"
        />
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

      {classes.length > 0 && (
        <div className="border-y border-dnd-border divide-y divide-dnd-border/60">
          {classes.map((cls, idx) => (
            <m.div
              key={cls.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="flex min-h-[64px] items-center gap-3 py-2 pl-1"
            >
              <div className="min-w-0 flex-1">
                <p className="font-display text-lg font-bold leading-tight text-dnd-text">
                  {classLabel(t, cls.class_name)}
                  {cls.subclass && (
                    <span className="ml-2 text-sm font-normal italic font-body text-dnd-text-muted">{cls.subclass}</span>
                  )}
                </p>
                <p className="mt-0.5 text-xs font-body text-dnd-text-muted">
                  {cls.hit_die && <span className="font-mono tabular-nums">d{cls.hit_die}</span>}
                  {cls.hit_die && cls.spellcasting_ability && ' · '}
                  {cls.spellcasting_ability && t(`common.abilities.${cls.spellcasting_ability.toLowerCase()}`, {
                    defaultValue: cls.spellcasting_ability,
                  })}
                </p>
              </div>
              {/* Livello in sola lettura: si cambia dai modali. */}
              <span
                aria-label={`${t('character.multiclass.level')} ${cls.level}`}
                className="font-display text-2xl font-black tabular-nums leading-none text-dnd-gold-bright"
              >
                {cls.level}
              </span>
              <Pressable
                onClick={() => setRemoveTarget(cls)}
                className="w-11 h-11 text-dnd-crimson-bright flex items-center justify-center hover:bg-dnd-crimson/10 shrink-0"
                whileTap={{ scale: 0.9 }}
                aria-label={`${t('common.remove')} ${classLabel(t, cls.class_name)}`}
              >
                <X size={16} />
              </Pressable>
            </m.div>
          ))}
        </div>
      )}

      {classes.map((cls) => <ClassOptionGroups key={cls.id} char={char} cls={cls} />)}

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
          targetLevel={milestone ? 20 : targetLevel}
          milestone={milestone}
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
            ? t('character.multiclass.remove_class_body', { name: classLabel(t, removeTarget.class_name) })
            : ''
        }
        confirmLabel={t('common.delete')}
        confirmVariant="danger"
        loading={removeClass.isPending}
      />
    </Layout>
  )
}
