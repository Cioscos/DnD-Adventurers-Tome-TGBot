import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { GiCrossedSwords as Swords } from 'react-icons/gi'
import { Plus, RefreshCw, Flag, ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react'
import Button from '@/components/ui/Button'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import CombatantRow from '@/components/session/CombatantRow'
import RoundRibbon from '@/components/session/RoundRibbon'
import MyCombatantCard from '@/components/session/MyCombatantCard'
import InitiativeCta from '@/pages/session/InitiativeCta'
import AddMonsterSheet from '@/pages/session/AddMonsterSheet'
import CombatantSheet from '@/pages/session/CombatantSheet'
import SaveRollSheet from '@/components/SaveRollSheet'
import { api, ApiError } from '@/api/client'
import { haptic, telegramConfirm } from '@/auth/telegram'
import { useYourTurnToast } from '@/hooks/useYourTurnToast'
import type { CombatantLive, GameSessionLive, PendingSave } from '@/types'

interface Props {
  live: GameSessionLive
  sessionId: number
  amGm: boolean
  myUserId: number
}

/** Contenuto della pagina Combattimento: richiede un incontro aperto in `live`. */
export default function CombatPanel({ live, sessionId, amGm, myUserId }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const enc = live.encounter ?? null
  const [showMenu, setShowMenu] = useState(false)
  const [showAddMonster, setShowAddMonster] = useState(false)
  const [sheetTarget, setSheetTarget] = useState<CombatantLive | null>(null)
  const [confirmSkip, setConfirmSkip] = useState(false)
  // TS nati a fine del mio turno: si aprono subito dopo «Termina turno».
  const [savesToRoll, setSavesToRoll] = useState<PendingSave[] | null>(null)

  const snapshotsById = useMemo(() => {
    const map = new Map<number, GameSessionLive['live_characters'][number]>()
    live.live_characters.forEach((c) => map.set(c.id, c))
    return map
  }, [live])

  useYourTurnToast(enc, myUserId)

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

  // Il TS di fine turno nasce solo quando il turno passa: lo leggo e lo apro subito.
  const endMyTurnMutation = useMutation({
    mutationFn: async (charId: number) => {
      await api.sessions.encounter.nextTurn(sessionId)
      return qc.fetchQuery({
        queryKey: ['turn-state', charId],
        queryFn: () => api.characters.turnState(charId),
        staleTime: 0, // la cache del polling è di prima del cambio turno: serve il dato nuovo
      })
    },
    onSuccess: (turn) => {
      haptic.light()
      invalidate()
      const pending = (turn?.pending_saves ?? []).filter((s) => s.status === 'pending')
      if (pending.length > 0) setSavesToRoll(pending)
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError && err.status === 403) {
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

  const resolveSaveMutation = useMutation({
    mutationFn: ({ saveId, passed }: { saveId: number; passed: boolean }) =>
      api.sessions.encounter.resolveSave(sessionId, saveId, passed),
    onSuccess: () => { haptic.light(); invalidate() },
    onError,
  })

  const endMutation = useMutation({
    mutationFn: () => api.sessions.encounter.end(sessionId),
    onSuccess: () => { haptic.warning(); invalidate() },
    onError,
  })

  if (!enc) return null

  const isActivePhase = enc.status === 'active'
  const myCombatant = enc.combatants.find(
    (c) => c.kind === 'pc' && c.owner_user_id === myUserId,
  )
  const activeCombatant =
    enc.combatants.find((c) => c.id === enc.active_combatant_id) ?? null
  const isMyTurn =
    isActivePhase &&
    activeCombatant?.kind === 'pc' &&
    activeCombatant.owner_user_id === myUserId &&
    !activeCombatant.is_dead
  const activeIsLivingPc =
    activeCombatant?.kind === 'pc' && !activeCombatant.is_dead
  const snapOf = (c: CombatantLive) =>
    c.character_id ? snapshotsById.get(c.character_id) : undefined
  const monstersAllDown =
    enc.combatants.some((c) => c.kind === 'monster') &&
    enc.combatants.filter((c) => c.kind === 'monster').every((c) => c.is_dead)

  // «Tocca a te tra N»: posizioni vive dall'attivo al mio PG, in giro.
  const living = enc.combatants.filter((c) => !c.is_dead)
  const fromActive = living.findIndex((c) => c.id === activeCombatant?.id)
  const toMe = living.findIndex((c) => c.id === myCombatant?.id)
  const turnsUntilMine =
    isActivePhase && fromActive >= 0 && toMe >= 0
      ? (toMe - fromActive + living.length) % living.length
      : null

  // Tracciato: morti in fondo, ordine relativo invariato.
  const tracked = [...living, ...enc.combatants.filter((c) => c.is_dead)]

  const menuItem = (icon: React.ReactNode, label: string, onClick: () => void, danger = false) => (
    <Button
      variant={danger ? 'danger' : 'secondary'}
      size="md"
      fullWidth
      icon={icon}
      onClick={() => { setShowMenu(false); onClick() }}
    >
      {label}
    </Button>
  )

  let dock: React.ReactNode = null
  if (amGm && isActivePhase) {
    dock = (
      <div className="flex gap-2">
        <Pressable
          onClick={() => turnMutation.mutate('prev')}
          disabled={turnMutation.isPending}
          aria-label={t('session.combat.prev')}
          className="w-14 min-h-[48px] inline-flex items-center justify-center rounded-xl
                     bg-dnd-surface border border-dnd-gold-dim/60 text-dnd-gold-bright
                     active:scale-95 disabled:opacity-40"
        >
          <ChevronLeft size={20} />
        </Pressable>
        <Button
          variant="primary"
          size="md"
          className="flex-1"
          icon={<ChevronRight size={16} />}
          loading={turnMutation.isPending}
          onClick={() => (activeIsLivingPc ? setConfirmSkip(true) : turnMutation.mutate('next'))}
        >
          {t('session.combat.next_turn')}
        </Button>
      </div>
    )
  } else if (amGm) {
    dock = (
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
    )
  } else if (isMyTurn && myCombatant?.character_id) {
    const charId = myCombatant.character_id
    dock = (
      <Button
        variant="primary"
        size="md"
        fullWidth
        icon={<ChevronRight size={16} />}
        loading={endMyTurnMutation.isPending}
        onClick={() => endMyTurnMutation.mutate(charId)}
      >
        {t('session.combat.end_my_turn')}
      </Button>
    )
  }

  return (
    <>
      <div className="flex items-center justify-between gap-2 min-h-[44px]">
        <p className="font-cinzel uppercase tracking-widest text-sm text-dnd-gold-dim">
          {isActivePhase ? (
            <span className="tabular-nums">{t('session.combat.round_label', { n: enc.round })}</span>
          ) : (
            t('session.combat.setup_title')
          )}
        </p>
        {amGm && (
          <Pressable
            onClick={() => setShowMenu(true)}
            aria-label={t('session.combat.menu')}
            className="w-11 h-11 inline-flex items-center justify-center rounded-full
                       bg-dnd-surface border border-dnd-gold-dim/50 text-dnd-gold-bright active:scale-95"
          >
            <MoreHorizontal size={20} />
          </Pressable>
        )}
      </div>

      {isActivePhase && (
        <RoundRibbon
          combatants={enc.combatants}
          activeId={enc.active_combatant_id}
          myUserId={myUserId}
        />
      )}

      {!amGm && myCombatant && enc.status === 'setup' && (
        <InitiativeCta sessionId={sessionId} combatant={myCombatant} />
      )}
      {!amGm && myCombatant && isActivePhase && (
        <MyCombatantCard
          combatant={myCombatant}
          snapshot={snapOf(myCombatant)}
          isMyTurn={isMyTurn}
          turnsUntilMine={turnsUntilMine}
          onOpenTurn={
            myCombatant.character_id
              ? () => navigate(`/char/${myCombatant.character_id}/turn`)
              : undefined
          }
        />
      )}

      {amGm && isActivePhase && activeCombatant && (
        <div data-testid="active-combatant-card" className="space-y-1">
          <p className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright">
            {t('session.combat.acting')}
          </p>
          <CombatantRow
            combatant={activeCombatant}
            snapshot={snapOf(activeCombatant)}
            isActive
            amGm
            mode={enc.mode}
          />
        </div>
      )}

      <div className="space-y-1.5">
        <p className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-dim">
          {t('session.combat.initiative')}
        </p>
        {tracked.map((c) => (
          <CombatantRow
            key={c.id}
            compact
            combatant={c}
            snapshot={snapOf(c)}
            isActive={isActivePhase && c.id === enc.active_combatant_id}
            amGm={amGm}
            mode={enc.mode}
            onTap={amGm ? () => setSheetTarget(c) : undefined}
            onResolveSave={amGm ? (saveId, passed) => resolveSaveMutation.mutate({ saveId, passed }) : undefined}
            resolvingSaveId={resolveSaveMutation.isPending ? resolveSaveMutation.variables?.saveId : null}
          />
        ))}
      </div>

      {amGm && monstersAllDown && isActivePhase && (
        <p className="text-center text-xs text-dnd-text-muted font-body italic">
          {t('session.combat.all_monsters_down')}
        </p>
      )}

      {dock && (
        <div className="sticky bottom-0 z-10 -mx-4 px-4 pt-3 pb-3 bg-dnd-bg border-t border-dnd-border">
          {dock}
        </div>
      )}

      <Sheet open={showMenu} onClose={() => setShowMenu(false)} title={t('session.combat.menu')}>
        <div className="p-5 space-y-2">
          {menuItem(<Plus size={16} />, t('session.combat.add_monster'), () => setShowAddMonster(true))}
          {menuItem(<RefreshCw size={16} />, t('session.combat.sync_pcs'), () => syncMutation.mutate())}
          {isActivePhase &&
            menuItem(
              <Flag size={16} />,
              t('session.combat.end'),
              () => telegramConfirm(t('session.combat.end_confirm'), (ok) => ok && endMutation.mutate()),
              true,
            )}
        </div>
      </Sheet>

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
          liveCharacters={live.live_characters}
          onClose={() => setSheetTarget(null)}
        />
      )}
      {savesToRoll && myCombatant?.character_id && (
        <SaveRollSheet
          charId={myCombatant.character_id}
          saves={savesToRoll}
          onClose={() => setSavesToRoll(null)}
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
