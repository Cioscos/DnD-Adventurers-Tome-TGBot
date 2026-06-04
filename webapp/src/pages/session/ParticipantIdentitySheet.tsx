import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { EyeOff, Lock, User, Globe2 } from 'lucide-react'
import {
  GiFeather as Feather,
  GiHeartPlus as Heart,
  GiCheckedShield as Shield,
  GiPerspectiveDiceSixFacesRandom as Dices,
} from 'react-icons/gi'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import SectionDivider from '@/components/ui/SectionDivider'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import ConditionBadge from '@/components/ui/ConditionBadge'
import { useUnitSettings, formatLength } from '@/store/unitSettings'
import type { CharacterLiveSnapshot, ParticipantIdentity, SessionParticipant } from '@/types'

interface Props {
  code: string
  target: SessionParticipant | null
  snapshot?: CharacterLiveSnapshot
  myUserId: number
  onClose: () => void
  onStartWhisper?: (target: SessionParticipant) => void
}

function conditionEntries(
  conditions: Record<string, unknown> | null | undefined,
): Array<[string, unknown]> {
  if (!conditions) return []
  return Object.entries(conditions).filter(([, v]) => Boolean(v))
}

interface FieldRowProps {
  label: string
  value: string | number | null
}

function FieldRow({ label, value }: FieldRowProps) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim shrink-0">
        {label}
      </span>
      <span className="text-sm text-dnd-text text-right">{value}</span>
    </div>
  )
}

function BlockRow({ label, value }: FieldRowProps) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="py-2">
      <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
        {label}
      </p>
      <p className="text-sm text-dnd-text italic whitespace-pre-wrap">{value}</p>
    </div>
  )
}

export default function ParticipantIdentitySheet({
  code,
  target,
  snapshot,
  myUserId,
  onClose,
  onStartWhisper,
}: Props) {
  const { t } = useTranslation()
  const unitSystem = useUnitSettings((s) => s.system)

  const hasCharacter = !!target?.character_id
  const { data, isLoading, isError } = useQuery<ParticipantIdentity>({
    queryKey: ['session-identity', code, target?.user_id],
    queryFn: () => api.sessions.getParticipantIdentity(code, target!.user_id),
    enabled: !!target && hasCharacter,
    staleTime: 30_000,
  })

  const redacted = !!snapshot && snapshot.hit_points === null
  const conds = conditionEntries(snapshot?.conditions)
  const hpPct = snapshot && !redacted && (snapshot.hit_points ?? 0) > 0
    ? Math.max(0, Math.min(100, Math.round(
        ((snapshot.current_hit_points ?? 0) / (snapshot.hit_points ?? 1)) * 100,
      )))
    : 0
  const bucketColor: Record<string, string> = {
    healthy:          'bg-[var(--dnd-emerald-bright)]',
    lightly_wounded:  'bg-dnd-gold-bright',
    badly_wounded:    'bg-[var(--dnd-amber)]',
    dying:            'bg-[var(--dnd-crimson-bright)]',
    dead:             'bg-black',
  }
  const canWhisper = !!target && !!onStartWhisper && target.user_id !== myUserId

  return (
    <Sheet
      open={!!target}
      onClose={onClose}
      title={data?.name ?? t('session.identity.title')}
    >
      <div className="space-y-3 p-1">
        {canWhisper && (
          <Button
            variant="secondary"
            size="sm"
            fullWidth
            icon={<Lock size={14} />}
            onClick={() => {
              if (target && onStartWhisper) {
                onStartWhisper(target)
                onClose()
              }
            }}
          >
            {t('session.whisper.button', {
              name: target?.display_name ?? `#${target?.user_id ?? ''}`,
            })}
          </Button>
        )}

        {snapshot && (
          <>
            <SectionDivider icon={<Heart size={11} />} align="center">
              {t('session.detail.stats_title')}
            </SectionDivider>
            <Surface variant="elevated">
              {redacted ? (
                <>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-cinzel">
                      <Heart size={12} className="text-[var(--dnd-crimson-bright)]" />
                      <span className="uppercase tracking-wider">
                        {snapshot.hp_bucket
                          ? t(`session.hp_bucket.${snapshot.hp_bucket}`)
                          : t('session.detail.hp_redacted')}
                      </span>
                    </div>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden">
                    <div
                      className={`h-full ${bucketColor[snapshot.hp_bucket ?? 'healthy']}`}
                      style={{ width: '100%' }}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2 text-sm font-mono">
                    <div className="flex items-center gap-1.5">
                      <Heart size={14} className="text-[var(--dnd-crimson-bright)]" />
                      <span>
                        {t('session.detail.hp_label')}: {snapshot.current_hit_points}/{snapshot.hit_points}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 justify-end">
                      <Shield size={14} className="text-dnd-gold-bright" />
                      <span>
                        {t('session.detail.ac_label')}: {snapshot.ac ?? t('session.detail.ac_hidden')}
                      </span>
                    </div>
                  </div>
                  {(snapshot.temp_hp ?? 0) > 0 && (
                    <p className="text-xs text-dnd-arcane-bright font-mono mt-1">
                      {t('session.detail.temp_hp_label')}: +{snapshot.temp_hp}
                    </p>
                  )}
                  <div className="mt-2 h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-[var(--dnd-crimson)] via-[var(--dnd-amber)] to-[var(--dnd-emerald-bright)]"
                      style={{ width: `${hpPct}%` }}
                    />
                  </div>
                </>
              )}

              <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mt-3 mb-1">
                {t('session.detail.conditions_label')}
              </p>
              {conds.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {conds.map(([key, val]) => (
                    <ConditionBadge key={key} conditionKey={key} value={val} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-dnd-text-muted italic">
                  {t('session.detail.no_conditions')}
                </p>
              )}

              {snapshot.last_roll && (
                <div className="mt-3 flex items-center gap-1.5 text-xs text-dnd-text-muted border-t border-dnd-border pt-2">
                  <Dices size={12} />
                  <span className="font-cinzel uppercase tracking-wider text-[10px] text-dnd-gold-dim">
                    {t('session.detail.last_roll_label')}:
                  </span>
                  <span className="font-mono">
                    {snapshot.last_roll.notation} → {snapshot.last_roll.total}
                  </span>
                </div>
              )}
            </Surface>
          </>
        )}

        {isLoading && (
          <p className="text-center text-sm text-dnd-text-muted py-8">
            {t('session.identity.loading')}
          </p>
        )}

        {isError && (
          <p className="text-center text-sm text-[var(--dnd-crimson-bright)] py-8">
            {t('session.identity.error')}
          </p>
        )}

        {data && (
          <>
            {/* Public — Fisicità */}
            <SectionDivider icon={<User size={11} />} align="center">
              {t('session.identity.fisicita')}
            </SectionDivider>
            <Surface variant="elevated">
              <FieldRow label={t('character.identity.race')} value={data.race} />
              <FieldRow label={t('character.identity.gender')} value={data.gender} />
              <FieldRow label={t('character.identity.alignment')} value={data.alignment} />
              <FieldRow label={t('character.identity.speed')} value={data.speed !== null ? formatLength(data.speed, unitSystem) : null} />
            </Surface>

            {/* Public — Cultura */}
            <SectionDivider icon={<Globe2 size={11} />} align="center">
              {t('session.identity.cultura')}
            </SectionDivider>
            <Surface variant="elevated">
              <FieldRow label={t('character.identity.languages')} value={data.languages} />
              <FieldRow label={t('character.identity.proficiencies')} value={data.general_proficiencies} />
            </Surface>

            {/* Private — Personalità */}
            <SectionDivider icon={<Feather size={11} />} align="center">
              {t('session.identity.personalita')}
            </SectionDivider>
            <div className="flex items-center justify-center gap-1 -mt-2 mb-2 text-dnd-gold-dim">
              <Lock size={10} />
              <span className="text-[10px] font-cinzel uppercase tracking-wider">
                {t('character.identity.private_badge')}
              </span>
            </div>

            {data.show_private ? (
              <Surface variant="parchment">
                <BlockRow label={t('character.identity.background')} value={data.background} />
                <BlockRow label={t('character.identity.personality')} value={data.personality_traits} />
                <BlockRow label={t('character.identity.ideals')} value={data.ideals} />
                <BlockRow label={t('character.identity.bonds')} value={data.bonds} />
                <BlockRow label={t('character.identity.flaws')} value={data.flaws} />
              </Surface>
            ) : (
              <Surface variant="elevated" className="text-center !py-6">
                <EyeOff size={24} className="mx-auto text-dnd-text-muted mb-2" />
                <p className="text-sm text-dnd-text-muted italic">
                  {t('session.identity.private_hidden')}
                </p>
              </Surface>
            )}
          </>
        )}
      </div>
    </Sheet>
  )
}
