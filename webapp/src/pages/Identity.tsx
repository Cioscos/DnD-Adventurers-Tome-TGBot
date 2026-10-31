import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { User, Globe2, Save, Lock, Share2 } from 'lucide-react'
import {
  GiFeather as Feather, GiCheckedShield as Shield, GiLightningTrio as Zap,
  GiFlame as Flame,
} from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import ChipInput from '@/components/ui/ChipInput'
import Pressable from '@/components/ui/Pressable'
import { canonicalDamageType, damageTypeLabel } from '@/lib/damageModifier'
import SectionDivider from '@/components/ui/SectionDivider'
import { canShareMessage, haptic } from '@/auth/telegram'
import { useShareMessage } from '@/hooks/useShareMessage'
import { useUnitSettings, formatLength, oppositeSystem, feetToDisplay, displayToFeet, unitLabel } from '@/store/unitSettings'
import languagesSrd from '@/data/languages-srd.json'
import { DAMAGE_TYPES } from '@/pages/inventory/itemMetadata'
import IdentitySkeleton from '@/components/skeletons/IdentitySkeleton'

const LANGUAGE_SUGGESTIONS = [...languagesSrd.common, ...languagesSrd.exotic]

type DamageModifiers = {
  resistances: string[]
  immunities: string[]
  vulnerabilities: string[]
}

type Draft = {
  name: string; race: string; gender: string; background: string
  alignment: string; speed: string
  // tipo -> distanza nell'unità scelta; assente = senso non posseduto
  senses: Record<string, string>
  personality_traits: string; ideals: string; bonds: string; flaws: string
  languages: string[]; general_proficiencies: string[]
  damageModifiers: DamageModifiers
}

const DMG_TONES: Record<keyof DamageModifiers, { text: string; icon: typeof Shield }> = {
  resistances: { text: 'text-dnd-cobalt-bright', icon: Shield },
  immunities: { text: 'text-dnd-gold-bright', icon: Zap },
  vulnerabilities: { text: 'text-dnd-crimson-bright', icon: Flame },
}

const SENSE_TYPES = ['darkvision', 'blindsight', 'truesight', 'tremorsense'] as const

const DMG_KEYS: Array<keyof DamageModifiers> = ['resistances', 'immunities', 'vulnerabilities']
const DMG_SLUGS = DAMAGE_TYPES.filter((d) => d !== 'dmg_other').map((d) => d.replace(/^dmg_/, ''))

// Etichette legacy ("Fuoco") -> slug; il testo non riconosciuto (homebrew) resta com'è.
function normalizeDmg(values: string[] | undefined): string[] {
  return [...new Set((values ?? []).map((v) => canonicalDamageType(v) ?? v))]
}

function snapshot(d: Draft): string {
  return JSON.stringify(d)
}

export default function Identity() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [pristine, setPristine] = useState<string>('')
  const unitSystem = useUnitSettings((s) => s.system)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  useEffect(() => {
    if (char && !draft) {
      const personality = (char.personality as Record<string, string>) ?? {}
      const raw = (char.damage_modifiers as Record<string, string[]>) ?? {}
      const initial: Draft = {
        name: char.name ?? '',
        race: char.race ?? '',
        gender: char.gender ?? '',
        background: char.background ?? '',
        alignment: char.alignment ?? '',
        speed: String(feetToDisplay(char.speed ?? 30, unitSystem)),
        senses: Object.fromEntries(
          ((char.settings?.senses as { type: string; range_ft: number }[] | undefined) ?? [])
            .map((s) => [s.type, String(feetToDisplay(s.range_ft, unitSystem))]),
        ),
        personality_traits: personality.traits ?? '',
        ideals: personality.ideals ?? '',
        bonds: personality.bonds ?? '',
        flaws: personality.flaws ?? '',
        languages: (char.languages as string[]) ?? [],
        general_proficiencies: (char.general_proficiencies as string[]) ?? [],
        damageModifiers: {
          resistances: normalizeDmg(raw.resistances),
          immunities: normalizeDmg(raw.immunities),
          vulnerabilities: normalizeDmg(raw.vulnerabilities),
        },
      }
      setDraft(initial)
      setPristine(snapshot(initial))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [char])

  const shareCard = useShareMessage(() => api.share.card(charId))

  const mutation = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error('No draft')
      return api.characters.update(charId, {
        name: draft.name.trim(),
        race: draft.race.trim() || null,
        gender: draft.gender.trim() || null,
        background: draft.background.trim() || null,
        alignment: draft.alignment.trim() || null,
        speed: displayToFeet(Number(draft.speed) || 0, unitSystem) || 30,
        personality: {
          traits: draft.personality_traits.trim(),
          ideals: draft.ideals.trim(),
          bonds: draft.bonds.trim(),
          flaws: draft.flaws.trim(),
        },
        languages: draft.languages,
        general_proficiencies: draft.general_proficiencies,
        damage_modifiers: draft.damageModifiers,
        // settings replaces the whole dict server-side: always merge.
        settings: {
          ...char?.settings,
          senses: SENSE_TYPES.filter((k) => draft.senses[k] !== undefined).map((k) => ({
            type: k,
            range_ft: displayToFeet(Number(draft.senses[k]) || 0, unitSystem),
          })),
        },
      })
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
      if (draft) setPristine(snapshot(draft))
    },
  })

  if (!char || !draft) {
    return (
      <Layout title={t('character.identity.title')} backTo={`/char/${charId}`} group="character" page="identity">
        <IdentitySkeleton />
      </Layout>
    )
  }

  const dirty = snapshot(draft) !== pristine

  const set = (key: keyof Draft) => (v: string) =>
    setDraft((d) => d ? { ...d, [key]: v } : d)

  // Un tipo sta in una sola lista: sceglierlo altrove lo sposta.
  const toggleDmg = (key: keyof DamageModifiers, slug: string) =>
    setDraft((d) => {
      if (!d) return d
      const had = d.damageModifiers[key].includes(slug)
      const next = { ...d.damageModifiers }
      for (const k of DMG_KEYS) next[k] = next[k].filter((v) => v !== slug)
      if (!had) next[key] = [...next[key], slug]
      return { ...d, damageModifiers: next }
    })

  const personalitySections = [
    { key: 'personality_traits' as const, label: t('character.identity.personality') },
    { key: 'ideals' as const, label: t('character.identity.ideals') },
    { key: 'bonds' as const, label: t('character.identity.bonds') },
    { key: 'flaws' as const, label: t('character.identity.flaws') },
  ]

  return (
    <Layout title={t('character.identity.title')} backTo={`/char/${charId}`} group="character" page="identity">
      {/* Avviso, non pericolo: ambra (Candle Amber), non la variante ember che
          il giocatore legge come crisi HP (Semantic Triad). */}
      {dirty && (
        <Surface
          variant="elevated"
          className="sticky top-2 z-20 flex items-center justify-between gap-3 !py-2.5 !px-3 !border-dnd-amber/60"
        >
          <span className="text-xs font-body text-dnd-text">
            {t('character.identity.unsaved_changes')}
          </span>
          <Button
            variant="primary"
            size="sm"
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            icon={<Save size={14} />}
            haptic="success"
          >
            {t('character.identity.save_now')}
          </Button>
        </Surface>
      )}

      {/* Hero name */}
      <Surface variant="tome" ornamented>
        <Input
          label={t('character.identity.name')}
          value={draft.name}
          onChange={set('name')}
          className="[&_input]:text-xl [&_input]:font-display [&_input]:font-bold"
        />
      </Surface>

      {/* Physicality */}
      <SectionDivider icon={<User size={11} />} align="center">
        {t('character.identity.physicality')}
      </SectionDivider>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Surface variant="elevated" className="!p-3">
          <Input label={t('character.identity.race')} value={draft.race} onChange={set('race')} placeholder={t('character.identity.placeholder_race')} />
        </Surface>
        <Surface variant="elevated" className="!p-3">
          <Input label={t('character.identity.gender')} value={draft.gender} onChange={set('gender')} placeholder={t('character.identity.placeholder_gender')} />
        </Surface>
        <Surface variant="elevated" className="!p-3">
          <Input label={t('character.identity.alignment')} value={draft.alignment} onChange={set('alignment')} placeholder={t('character.identity.placeholder_alignment')} />
        </Surface>
        <Surface variant="elevated" className="!p-3">
          <Input
            label={t('character.identity.speed')}
            type="number"
            min={0}
            value={draft.speed}
            onChange={set('speed')}
            inputMode="decimal"
            trailingAction={
              <span className="text-dnd-text-muted text-sm font-cinzel pr-1">
                {unitLabel(unitSystem)}
              </span>
            }
          />
          {Number(draft.speed) > 0 && (
            <p className="mt-1 text-xs font-mono text-dnd-text-faint tabular-nums">
              ≈ {formatLength(displayToFeet(Number(draft.speed) || 0, unitSystem), oppositeSystem(unitSystem))}
            </p>
          )}
        </Surface>
      </div>

      {/* Senses */}
      <Surface variant="elevated" className="mt-3 space-y-2">
        <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
          {t('character.identity.senses')}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {SENSE_TYPES.map((k) => {
            const on = draft.senses[k] !== undefined
            const toggleSense = () =>
              setDraft((d) => {
                if (!d) return d
                const next = { ...d.senses }
                if (on) delete next[k]
                else next[k] = String(feetToDisplay(60, unitSystem))
                return { ...d, senses: next }
              })
            return (
              <div key={k} className="flex items-center gap-2">
                <Pressable
                  type="button"
                  onClick={toggleSense}
                  aria-pressed={on}
                  className={`min-h-11 flex-1 px-3 rounded-xl border text-sm font-body text-left ${
                    on ? 'bg-dnd-gold/15 border-dnd-gold text-dnd-gold-bright' : 'bg-dnd-surface border-dnd-border text-dnd-text'
                  }`}
                >
                  {t(`character.senses.${k}`)}
                </Pressable>
                {on && (
                  <div className="w-24 shrink-0">
                    <Input
                      type="number"
                      min={0}
                      inputMode="decimal"
                      aria-label={`${t(`character.senses.${k}`)} (${unitLabel(unitSystem)})`}
                      value={draft.senses[k]}
                      onChange={(v) => setDraft((d) => d ? { ...d, senses: { ...d.senses, [k]: v } } : d)}
                      trailingAction={<span className="text-dnd-text-muted text-sm font-cinzel pr-1">{unitLabel(unitSystem)}</span>}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </Surface>

      {/* Personality */}
      <SectionDivider icon={<Feather size={11} />} align="center">
        {t('character.identity.personality')}
      </SectionDivider>

      <div className="flex flex-col items-center gap-1 -mt-2 mb-3 text-dnd-gold-dim">
        <div className="flex items-center gap-1">
          <Lock size={10} />
          <span className="text-xs font-cinzel uppercase tracking-wider">
            {t('character.identity.private_badge')}
          </span>
        </div>
        <p className="text-xs text-dnd-text-faint font-body italic max-w-[300px] text-center">
          {t('character.identity.private_hint')}
        </p>
      </div>

      <Surface variant="parchment" className="!pt-5 !px-4 !pb-4 relative !mt-8 !mb-6">
        <span className="absolute -top-2.5 left-4 px-2 bg-dnd-surface-raised text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim rounded">
          {t('character.identity.background')}
        </span>
        <Input
          value={draft.background}
          onChange={set('background')}
          placeholder={t('character.identity.placeholder_background')}
          className="[&_input]:!border-transparent [&_input]:!bg-transparent"
        />
      </Surface>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 !mt-6">
        {personalitySections.map(({ key, label }) => (
          <Surface key={key} variant="parchment" className="!pt-5 !px-4 !pb-4 relative">
            <span className="absolute -top-2.5 left-4 px-2 bg-dnd-surface-raised text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim rounded">
              {label}
            </span>
            <Input
              variant="textarea"
              value={draft[key] as string}
              onChange={set(key)}
              rows={3}
              placeholder={t(`character.identity.placeholder_${key}`)}
              className="[&_textarea]:!border-transparent [&_textarea]:!bg-transparent [&_textarea]:italic"
            />
          </Surface>
        ))}
      </div>

      {/* Culture */}
      <SectionDivider icon={<Globe2 size={11} />} align="center">
        {t('character.identity.culture')}
      </SectionDivider>

      <Surface variant="elevated">
        <ChipInput
          label={t('character.identity.languages')}
          values={draft.languages}
          onChange={(next) => setDraft((d) => d ? { ...d, languages: next } : d)}
          placeholder={t('character.identity.language_placeholder')}
          splitOnComma
          suggestions={LANGUAGE_SUGGESTIONS}
        />
      </Surface>
      <Surface variant="elevated">
        <ChipInput
          label={t('character.identity.proficiencies')}
          values={draft.general_proficiencies}
          onChange={(next) => setDraft((d) => d ? { ...d, general_proficiencies: next } : d)}
          placeholder={t('character.identity.proficiency_placeholder')}
          splitOnComma
        />
      </Surface>

      {/* Damage Modifiers */}
      <SectionDivider icon={<Shield size={11} />} align="center">
        {t('character.identity.damage_modifiers')}
      </SectionDivider>

      <p className="text-xs uppercase tracking-widest text-dnd-text-faint italic text-center -mt-2 mb-2">
        {t('character.identity.damage_vuln_wins_hint')}
      </p>

      <Surface variant="elevated">
        <div className="space-y-4">
          {DMG_KEYS.map((key) => {
            const tone = DMG_TONES[key]
            const ToneIcon = tone.icon
            return (
              <div key={key}>
                <div className="flex items-center gap-2 mb-2">
                  <ToneIcon size={12} className={tone.text} />
                  <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">
                    {t(`character.identity.${key}`)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {[...DMG_SLUGS, ...draft.damageModifiers[key].filter((v) => !DMG_SLUGS.includes(v))].map((slug) => {
                    const on = draft.damageModifiers[key].includes(slug)
                    return (
                      <Pressable
                        key={slug}
                        onClick={() => { toggleDmg(key, slug); haptic.selection() }}
                        aria-pressed={on}
                        className={`min-h-[44px] px-3 rounded-xl border text-sm font-medium transition-colors
                          ${on
                            ? 'bg-dnd-gold text-dnd-ink border-transparent'
                            : 'bg-dnd-surface-raised text-dnd-text border-dnd-border'}`}
                      >
                        {damageTypeLabel(t, slug)}
                      </Pressable>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </Surface>

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        disabled={!dirty}
        icon={<Save size={18} />}
        haptic="success"
      >
        {t('common.save')}
      </Button>

      {canShareMessage() && (
        <Button
          variant="secondary"
          size="lg"
          fullWidth
          onClick={() => shareCard.mutate()}
          loading={shareCard.isPending}
          icon={<Share2 size={18} />}
          haptic="light"
        >
          {t('share.card')}
        </Button>
      )}
    </Layout>
  )
}
