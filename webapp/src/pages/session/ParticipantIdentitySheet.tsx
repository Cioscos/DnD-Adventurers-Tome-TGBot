import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { EyeOff, Lock, User, Globe2 } from 'lucide-react'
import { GiFeather as Feather } from 'react-icons/gi'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import SectionDivider from '@/components/ui/SectionDivider'
import Surface from '@/components/ui/Surface'
import type { ParticipantIdentity, SessionParticipant } from '@/types'

interface Props {
  code: string
  target: SessionParticipant | null
  onClose: () => void
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

export default function ParticipantIdentitySheet({ code, target, onClose }: Props) {
  const { t } = useTranslation()

  const { data, isLoading, isError } = useQuery<ParticipantIdentity>({
    queryKey: ['session-identity', code, target?.user_id],
    queryFn: () => api.sessions.getParticipantIdentity(code, target!.user_id),
    enabled: !!target,
    staleTime: 30_000,
  })

  return (
    <Sheet
      open={!!target}
      onClose={onClose}
      title={data?.name ?? t('session.identity.title')}
    >
      <div className="space-y-3 p-1">
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
              <FieldRow label={t('character.identity.speed')} value={data.speed !== null ? `${data.speed} ft` : null} />
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
