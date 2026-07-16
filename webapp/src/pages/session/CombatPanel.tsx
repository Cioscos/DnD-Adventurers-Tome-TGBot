import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { GiCrossedSwords as Swords } from 'react-icons/gi'
import { Plus, RefreshCw, Flag, ChevronRight } from 'lucide-react'
import Button from '@/components/ui/Button'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import SectionDivider from '@/components/ui/SectionDivider'
import CombatantRow from '@/components/session/CombatantRow'
import TurnBar from '@/components/session/TurnBar'
import InitiativeCta from '@/pages/session/InitiativeCta'
import EncounterCreateSheet from '@/pages/session/EncounterCreateSheet'
import AddMonsterSheet from '@/pages/session/AddMonsterSheet'
import CombatantSheet from '@/pages/session/CombatantSheet'
import { api, ApiError } from '@/api/client'
import { haptic, telegramConfirm } from '@/auth/telegram'
import type { CombatantLive, GameSessionLive } from '@/types'

interface Props {
  live: GameSessionLive
  sessionId: number
  amGm: boolean
  myUserId: number
}

export default function CombatPanel({ live, sessionId, amGm, myUserId }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const enc = live.encounter ?? null
  const [showCreate, setShowCreate] = useState(false)
  const [showAddMonster, setShowAddMonster] = useState(false)
  const [sheetTarget, setSheetTarget] = useState<CombatantLive | null>(null)
  const [confirmSkip, setConfirmSkip] = useState(false)

  const snapshotsById = useMemo(() => {
    const map = new Map<number, GameSessionLive['live_characters'][number]>()
    live.live_characters.forEach((c) => map.set(c.id, c))
    return map
  }, [live])

  // Toast «tocca a te» quando il puntatore passa al mio PG.
  const prevActiveRef = useRef<number | null>(null)
  useEffect(() => {
    const activeId = enc?.status === 'active' ? enc.active_combatant_id : null
    if (activeId !== null && activeId !== prevActiveRef.current) {
      const active = enc?.combatants.find((c) => c.id === activeId)
      if (active?.kind === 'pc' && active.owner_user_id === myUserId) {
        haptic.success()
        toast.success(t('session.combat.your_turn'), { duration: 3000 })
      }
    }
    prevActiveRef.current = activeId
  }, [enc, myUserId, t])

  const invalidate = () => qc.invalidateQueries({ queryKey: ['session-live', sessionId] })
  const onError = () => {
    haptic.error()
    toast.error(t('session.combat.action_failed'))
  }

  const startMutation = useMutation({
    mutationFn: (autoRoll: boolean) => api.sessions.encounter.start(sessionId, autoRoll),
    onSuccess: () => { haptic.success(); invalidate() },
    onError: (err: unknown) => {
      const detail = err instanceof ApiError ? (err.detail as { code?: string; names?: string[] }) : null
      if (detail?.code === 'missing_initiative') {
        const names = (detail.names ?? []).join(', ')
        telegramConfirm(
          t('session.combat.auto_roll_confirm', { names }),
          (ok) => ok && startMutation.mutate(true),
        )
        return
      }
      onError()
    },
  })

  const turnMutation = useMutation({
    mutationFn: (dir: 'next' | 'prev') =>
      dir === 'next'
        ? api.sessions.encounter.nextTurn(sessionId)
        : api.sessions.encounter.prevTurn(sessionId),
    onSuccess: () => { haptic.light(); invalidate() },
    onError: (err: unknown, dir) => {
      // Stale "end turn": the pointer already moved on (e.g. the GM skipped
      // the player's turn first). Refresh instead of showing a hard error.
      if (dir === 'next' && err instanceof ApiError && err.status === 403) {
        haptic.warning()
        toast.info(t('session.combat.turn_already_advanced'))
        invalidate()
        return
      }
      onError()
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => api.sessions.encounter.syncPcs(sessionId),
    onSuccess: () => { haptic.light(); invalidate() },
    onError,
  })

  const endMutation = useMutation({
    mutationFn: () => api.sessions.encounter.end(sessionId),
    onSuccess: () => { haptic.warning(); invalidate() },
    onError,
  })

  // --- Nessun incontro: solo il bottone del GM -----------------------------
  if (!enc) {
    if (!amGm) return null
    return (
      <>
        <Button
          variant="secondary"
          size="md"
          fullWidth
          icon={<Swords size={16} />}
          onClick={() => setShowCreate(true)}
        >
          {t('session.combat.start_encounter')}
        </Button>
        {showCreate && (
          <EncounterCreateSheet sessionId={sessionId} onClose={() => setShowCreate(false)} />
        )}
      </>
    )
  }

  const myCombatant = enc.combatants.find(
    (c) => c.kind === 'pc' && c.owner_user_id === myUserId,
  )
  const activeCombatant =
    enc.combatants.find((c) => c.id === enc.active_combatant_id) ?? null
  const isMyTurn =
    enc.status === 'active' &&
    activeCombatant?.kind === 'pc' &&
    activeCombatant.owner_user_id === myUserId &&
    !activeCombatant.is_dead
  const activeIsLivingPc =
    activeCombatant?.kind === 'pc' && !activeCombatant.is_dead
  const monstersAllDown =
    enc.combatants.some((c) => c.kind === 'monster') &&
    enc.combatants.filter((c) => c.kind === 'monster').every((c) => c.is_dead)

  const rows = enc.combatants.map((c) => (
    <CombatantRow
      key={c.id}
      combatant={c}
      snapshot={c.character_id ? snapshotsById.get(c.character_id) : undefined}
      isActive={enc.status === 'active' && c.id === enc.active_combatant_id}
      amGm={amGm}
      mode={enc.mode}
      onTap={amGm ? () => setSheetTarget(c) : undefined}
    />
  ))

  return (
    <>
      <SectionDivider>
        {enc.status === 'setup'
          ? t('session.combat.setup_title')
          : t('session.combat.encounter_title')}
      </SectionDivider>

      {enc.status === 'active' && (
        <TurnBar
          round={enc.round}
          activeName={activeCombatant?.name ?? null}
          amGm={amGm}
          pending={turnMutation.isPending}
          onPrev={() => turnMutation.mutate('prev')}
          onNext={() =>
            activeIsLivingPc ? setConfirmSkip(true) : turnMutation.mutate('next')
          }
        />
      )}

      {!amGm && isMyTurn && (
        <Button
          variant="primary"
          size="md"
          fullWidth
          icon={<ChevronRight size={16} />}
          loading={turnMutation.isPending}
          onClick={() => turnMutation.mutate('next')}
        >
          {t('session.combat.end_my_turn')}
        </Button>
      )}

      {enc.status === 'setup' && !amGm && myCombatant && (
        <InitiativeCta sessionId={sessionId} combatant={myCombatant} />
      )}

      <div className="space-y-2">{rows}</div>

      {amGm && monstersAllDown && enc.status === 'active' && (
        <p className="text-center text-xs text-dnd-text-muted font-body italic">
          {t('session.combat.all_monsters_down')}
        </p>
      )}

      {amGm && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={<Plus size={14} />}
              onClick={() => setShowAddMonster(true)}
              className="flex-1"
            >
              {t('session.combat.add_monster')}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={14} />}
              onClick={() => syncMutation.mutate()}
              loading={syncMutation.isPending}
              className="flex-1"
            >
              {t('session.combat.sync_pcs')}
            </Button>
          </div>
          {enc.status === 'setup' ? (
            <Button
              variant="primary"
              size="md"
              fullWidth
              icon={<Swords size={16} />}
              loading={startMutation.isPending}
              onClick={() => startMutation.mutate(false)}
            >
              {t('session.combat.start')}
            </Button>
          ) : (
            <Button
              variant="danger"
              size="sm"
              fullWidth
              icon={<Flag size={14} />}
              loading={endMutation.isPending}
              onClick={() =>
                telegramConfirm(
                  t('session.combat.end_confirm'),
                  (ok) => ok && endMutation.mutate(),
                )
              }
            >
              {t('session.combat.end')}
            </Button>
          )}
        </div>
      )}

      {showAddMonster && (
        <AddMonsterSheet
          sessionId={sessionId}
          mode={enc.mode}
          onClose={() => setShowAddMonster(false)}
        />
      )}
      {sheetTarget && amGm && (
        <CombatantSheet
          sessionId={sessionId}
          encounter={enc}
          combatant={enc.combatants.find((c) => c.id === sheetTarget.id) ?? sheetTarget}
          onClose={() => setSheetTarget(null)}
        />
      )}
      <ConfirmSheet
        open={confirmSkip}
        onClose={() => setConfirmSkip(false)}
        onConfirm={() => {
          setConfirmSkip(false)
          turnMutation.mutate('next')
        }}
        title={t('session.combat.skip_pc_confirm_title')}
        body={t('session.combat.skip_pc_confirm_body', { name: activeCombatant?.name ?? '' })}
        confirmLabel={t('session.combat.skip_pc_confirm_cta')}
        cancelLabel={t('common.cancel')}
        confirmVariant="primary"
        loading={turnMutation.isPending}
      />
    </>
  )
}
