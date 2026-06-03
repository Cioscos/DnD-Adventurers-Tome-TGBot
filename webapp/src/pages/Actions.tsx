import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { GiFist, GiCrossedSwords } from 'react-icons/gi'
import { Target } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import { unarmedDamageDice } from '@/lib/unarmedStrike'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import WeaponAttackModal from '@/components/WeaponAttackModal'
import type { WeaponAttackResult } from '@/components/WeaponAttackModal'
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'

type AttackSource = { type: 'weapon'; itemId: number } | { type: 'unarmed' }
type AttackState = { result: WeaponAttackResult; source: AttackSource; wasRerolled: boolean }

export default function Actions() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [attackState, setAttackState] = useState<AttackState | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const weaponAttack = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId),
    onSuccess: (result, itemId) => {
      setAttackState({ result, source: { type: 'weapon', itemId }, wasRerolled: false })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const unarmedAttack = useMutation({
    mutationFn: () => api.items.attackUnarmed(charId),
    onSuccess: (result) => {
      setAttackState({ result, source: { type: 'unarmed' }, wasRerolled: false })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const rerollAttack = useMutation({
    mutationFn: (source: AttackSource) =>
      source.type === 'weapon'
        ? api.items.attack(charId, source.itemId, true)
        : api.items.attackUnarmed(charId, true),
    onSuccess: (result) => {
      setAttackState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        haptic.error()
      }
    },
  })

  if (!char) {
    return (
      <Layout title={t('character.actions.title')} backTo={`/char/${charId}`} group="combat" page="actions">
        <ActionsSkeleton />
      </Layout>
    )
  }

  const weapons = (char.items ?? []).filter((i) => i.item_type === 'weapon' && i.is_equipped)
  const unarmedDamage = unarmedDamageDice(char.classes)

  return (
    <Layout title={t('character.actions.title')} backTo={`/char/${charId}`} group="combat" page="actions">
      <Surface variant="elevated" ornamented>
        <div className="flex items-center gap-3">
          <GiFist size={28} className="text-dnd-gold-bright shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-cinzel text-dnd-gold">{t('character.actions.unarmed')}</p>
            <p className="text-xs text-dnd-text-muted">{t('character.actions.unarmed_desc', { damage: unarmedDamage })}</p>
          </div>
          <m.button
            onClick={() => unarmedAttack.mutate()}
            disabled={unarmedAttack.isPending}
            whileTap={{ scale: 0.93 }}
            className="flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson/30 disabled:opacity-50"
          >
            <Target size={14} />
            {t('character.actions.attack')}
          </m.button>
        </div>
      </Surface>

      <SectionDivider icon={<GiCrossedSwords size={11} />} align="center">
        {t('character.actions.weapons_section')}
      </SectionDivider>

      {weapons.length === 0 ? (
        <p className="text-center text-sm text-dnd-text-muted py-2">{t('character.actions.no_weapons')}</p>
      ) : (
        <div className="space-y-2">
          {weapons.map((w) => (
            <Surface key={w.id} variant="elevated">
              <div className="flex items-center gap-3">
                <GiCrossedSwords size={22} className="text-dnd-gold shrink-0" />
                <span className="flex-1 min-w-0 truncate">{w.name}</span>
                <m.button
                  onClick={() => weaponAttack.mutate(w.id)}
                  disabled={weaponAttack.isPending}
                  whileTap={{ scale: 0.93 }}
                  className="flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson/30 disabled:opacity-50"
                >
                  <Target size={14} />
                  {t('character.actions.attack')}
                </m.button>
              </div>
            </Surface>
          ))}
        </div>
      )}

      {attackState && (
        <WeaponAttackModal
          result={attackState.result}
          onClose={() => setAttackState(null)}
          inspirationAvailable={!!char.heroic_inspiration}
          isRerolling={rerollAttack.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => rerollAttack.mutate(attackState.source)}
        />
      )}
    </Layout>
  )
}
