import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronRight } from 'lucide-react'
import { GiCrossedSwords as Swords } from 'react-icons/gi'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import EncounterCreateSheet from '@/pages/session/EncounterCreateSheet'
import type { GameSessionLive } from '@/types'

interface Props {
  live: GameSessionLive
  sessionId: number
  amGm: boolean
}

/** Ingresso dalla sessione alla pagina Combattimento (o avvio, per il GM). */
export default function CombatEntryCard({ live, sessionId, amGm }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const enc = live.encounter ?? null
  const toCombat = () => navigate(`/session/${sessionId}/combat`)

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
          <EncounterCreateSheet
            sessionId={sessionId}
            onClose={() => setShowCreate(false)}
            onCreated={toCombat}
          />
        )}
      </>
    )
  }

  const active = enc.status === 'active'
  const actor = enc.combatants.find((c) => c.id === enc.active_combatant_id)

  return (
    <div data-testid="combat-entry-card">
      <Pressable
        haptic="light"
        onClick={toCombat}
        className={`w-full min-h-[64px] flex items-center gap-3 rounded-2xl border p-4 text-left
          bg-dnd-surface-raised active:scale-[0.98] transition-transform
          ${active
            ? 'border-dnd-gold ring-2 ring-dnd-gold-bright/30 shadow-dnd-glow'
            : 'border-dnd-gold-dim/60'}`}
      >
        <Swords size={26} className="shrink-0 text-dnd-gold-bright" />
        <div className="min-w-0 flex-1">
          <p className="font-display font-bold text-dnd-gold-bright">
            {t(active ? 'session.combat.entry_active' : 'session.combat.entry_setup')}
          </p>
          <p className="text-sm text-dnd-text-muted font-body tabular-nums break-words">
            {active
              ? [
                  t('session.combat.round_label', { n: enc.round }),
                  actor ? t('session.combat.turn_of', { name: actor.name }) : null,
                ].filter(Boolean).join(' · ')
              : t(amGm ? 'session.combat.entry_setup_gm' : 'session.combat.entry_setup_player')}
          </p>
        </div>
        <ChevronRight size={20} className="shrink-0 text-dnd-gold-dim" />
      </Pressable>
    </div>
  )
}
