import { useState, useEffect, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Save, Lock, Share2 } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Sheet from '@/components/ui/Sheet'
import SwitchToggle from '@/components/ui/SwitchToggle'
import ExpandChevron from '@/components/ui/ExpandChevron'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import ChipInput from '@/components/ui/ChipInput'
import Pressable from '@/components/ui/Pressable'
import { canonicalDamageType, damageTypeLabel } from '@/lib/damageModifier'
import SectionDivider from '@/components/ui/SectionDivider'
import { LEDGER_LABEL, LEDGER_ROW } from '@/styles/ledger'
import { canShareMessage, haptic } from '@/auth/telegram'
import { useShareMessage } from '@/hooks/useShareMessage'
import { useUnitSettings, formatLength, oppositeSystem, feetToDisplay, displayToFeet, unitLabel, type UnitSystem } from '@/store/unitSettings'
import languagesSrd from '@/data/languages-srd.json'
import { DAMAGE_TYPES } from '@/pages/inventory/itemMetadata'
import IdentitySkeleton from '@/components/skeletons/IdentitySkeleton'
import ToolProficiencyEditor from '@/components/character/ToolProficiencyEditor'
import type { ToolLevel } from '@/lib/tools'

const LANGUAGE_SUGGESTIONS = [...languagesSrd.common, ...languagesSrd.exotic]

const PROF_KEYS = ['armor', 'weapons', 'tools', 'other'] as const
type Proficiencies = Record<(typeof PROF_KEYS)[number], string[]>
const APPEARANCE_KEYS = ['age', 'height', 'weight', 'eyes', 'hair', 'skin'] as const

const PROF_SUGGESTIONS: Record<'it' | 'en', Record<'armor' | 'weapons' | 'tools', string[]>> = {
  it: {
    armor: ['Armature leggere', 'Armature medie', 'Armature pesanti', 'Scudi'],
    weapons: ['Armi semplici', 'Armi da guerra'],
    tools: ["Strumenti da ladro", "Strumenti da alchimista", "Strumenti da fabbro", "Strumenti da erborista", "Strumenti musicali", "Set da giocatore d'azzardo", "Strumenti da navigatore"],
  },
  en: {
    armor: ['Light armor', 'Medium armor', 'Heavy armor', 'Shields'],
    weapons: ['Simple weapons', 'Martial weapons'],
    tools: ["Thieves' tools", "Alchemist's supplies", "Smith's tools", 'Herbalism kit', 'Musical instruments', 'Gaming set', "Navigator's tools"],
  },
}

// Legacy: lista piatta -> "other" (il server fa lo stesso in lettura).
function normalizeProfs(v: unknown): Proficiencies {
  const o = (Array.isArray(v) ? { other: v } : v ?? {}) as Partial<Proficiencies>
  return { armor: o.armor ?? [], weapons: o.weapons ?? [], tools: o.tools ?? [], other: o.other ?? [] }
}

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
  speeds: Record<string, string> // volo/nuoto/scalata/scavo, come i sensi
  personality_traits: string; ideals: string; bonds: string; flaws: string
  languages: string[]; general_proficiencies: Proficiencies
  tools: Record<string, ToolLevel>
  appearance: Record<(typeof APPEARANCE_KEYS)[number], string>
  damageModifiers: DamageModifiers
}

// Stesso significato della Semantic Triad: l'oro è il selezionato neutro, il cobalto
// protegge, il cremisi è il pericolo. Classi intere perché Tailwind le mantenga.
const DMG_TEXT: Record<keyof DamageModifiers, string> = {
  resistances: 'text-dnd-cobalt-bright',
  immunities: 'text-dnd-gold-bright',
  vulnerabilities: 'text-dnd-crimson-bright',
}
const DMG_TONES: Record<keyof DamageModifiers, string> = {
  resistances: 'bg-dnd-cobalt/5 border-dnd-cobalt',
  immunities: 'bg-dnd-gold/20 border-dnd-gold',
  vulnerabilities: 'bg-dnd-crimson/10 border-dnd-crimson',
}

const SENSE_TYPES = ['darkvision', 'blindsight', 'truesight', 'tremorsense'] as const
const SPEED_TYPES = ['fly', 'swim', 'climb', 'burrow'] as const

type Ranged = { type: string; range_ft: number }
const toDraft = (list: Ranged[] | undefined, unit: UnitSystem) =>
  Object.fromEntries((list ?? []).map((s) => [s.type, String(feetToDisplay(s.range_ft, unit))]))
const fromDraft = (keys: readonly string[], d: Record<string, string>, unit: UnitSystem) =>
  keys.filter((k) => d[k] !== undefined).map((k) => ({ type: k, range_ft: displayToFeet(Number(d[k]) || 0, unit) }))

/** Righe interruttore + distanza: usate per sensi e velocità extra. */
function RangeToggles({ keys, labelKey, field, values, errors, defaultFt, unitSystem, onChange }: {
  keys: readonly string[]; labelKey: string; field: string; values: Record<string, string>; errors: Record<string, string>
  defaultFt: number; unitSystem: UnitSystem; onChange: (next: Record<string, string>) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="divide-y divide-dnd-border/60 border-b border-dnd-border/60">
      {keys.map((k) => {
        const on = values[k] !== undefined
        const label = t(`${labelKey}.${k}`)
        const set = (next: boolean) => {
          const nextValues = { ...values }
          if (next) nextValues[k] = String(feetToDisplay(defaultFt, unitSystem))
          else delete nextValues[k]
          onChange(nextValues)
        }
        return (
          <div key={k} data-field={`${field}.${k}`} className="flex items-center gap-3 py-1.5">
            <div className="flex-1 min-w-0">
              <SwitchToggle checked={on} onChange={set} label={<span className="font-normal text-sm">{label}</span>} aria-label={label} />
            </div>
            {on && (
              <div className="w-24 shrink-0">
                <Input
                  type="number"
                  min={0}
                  inputMode="decimal"
                  aria-label={`${label} (${unitLabel(unitSystem)})`}
                  value={values[k]}
                  error={errors[`${field}.${k}`]}
                  onChange={(v) => onChange({ ...values, [k]: v })}
                  trailingAction={<span className="text-dnd-text-muted text-sm font-cinzel pr-1">{unitLabel(unitSystem)}</span>}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** Riga che apre un gruppo di campi usato di rado. */
function Disclosure({ title, defaultOpen, children }: { title: string; defaultOpen: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <Pressable
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={`${LEDGER_ROW} !px-0 border-b border-dnd-border/60`}
      >
        <span className={LEDGER_LABEL}>{title}</span>
        <ExpandChevron open={open} />
      </Pressable>
      {open && <div className="mt-3 space-y-3">{children}</div>}
    </div>
  )
}

const DMG_KEYS: Array<keyof DamageModifiers> = ['resistances', 'immunities', 'vulnerabilities']
const DMG_SLUGS = DAMAGE_TYPES.filter((d) => d !== 'dmg_other').map((d) => d.replace(/^dmg_/, ''))

// Etichette legacy ("Fuoco") -> slug; il testo non riconosciuto (homebrew) resta com'è.
function normalizeDmg(values: string[] | undefined): string[] {
  return [...new Set((values ?? []).map((v) => canonicalDamageType(v) ?? v))]
}

function snapshot(d: Draft): string {
  return JSON.stringify(d)
}

// La bozza sopravvive se Telegram chiude la Mini App a metà modifica. Le distanze sono
// nell'unità corrente: con un'altra unità la bozza non vale più.
const draftKey = (charId: number) => `identity-draft-${charId}`

function readStoredDraft(charId: number, unit: UnitSystem): Partial<Draft> | null {
  try {
    const stored = JSON.parse(localStorage.getItem(draftKey(charId)) ?? 'null')
    return stored?.unit === unit ? stored.draft : null
  } catch {
    return null
  }
}

function writeStoredDraft(charId: number, unit: UnitSystem, draft: Draft | null) {
  try {
    if (draft) localStorage.setItem(draftKey(charId), JSON.stringify({ unit, draft }))
    else localStorage.removeItem(draftKey(charId))
  } catch {
    // Storage pieno o negato: si perde solo la protezione dalle interruzioni.
  }
}

const invalidDistance = (v: string) => v.trim() === '' || !(Number(v) >= 0)

export default function Identity() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t, i18n } = useTranslation()
  const profSuggestions = PROF_SUGGESTIONS[i18n.language === 'en' ? 'en' : 'it']
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [pristine, setPristine] = useState<string>('')
  const [restored, setRestored] = useState(false)
  // Gli errori compaiono al primo tentativo di salvare, poi seguono la bozza.
  const [showErrors, setShowErrors] = useState(false)
  const [leaving, setLeaving] = useState<(() => void) | null>(null)
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
        senses: toDraft(char.settings?.senses as Ranged[] | undefined, unitSystem),
        speeds: toDraft(char.settings?.speeds as Ranged[] | undefined, unitSystem),
        personality_traits: personality.traits ?? '',
        ideals: personality.ideals ?? '',
        bonds: personality.bonds ?? '',
        flaws: personality.flaws ?? '',
        languages: (char.languages as string[]) ?? [],
        general_proficiencies: normalizeProfs(char.general_proficiencies),
        tools: char.tool_proficiencies ?? {},
        appearance: Object.fromEntries(APPEARANCE_KEYS.map((k) => [k, personality[k] ?? ''])) as Draft['appearance'],
        damageModifiers: {
          resistances: normalizeDmg(raw.resistances),
          immunities: normalizeDmg(raw.immunities),
          vulnerabilities: normalizeDmg(raw.vulnerabilities),
        },
      }
      const stored = readStoredDraft(charId, unitSystem)
      const start = stored ? { ...initial, ...stored } : initial
      setDraft(start)
      setPristine(snapshot(initial))
      setRestored(snapshot(start) !== snapshot(initial))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [char])

  useEffect(() => {
    if (draft) writeStoredDraft(charId, unitSystem, snapshot(draft) !== pristine ? draft : null)
  }, [draft, pristine, charId, unitSystem])

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
        speed: displayToFeet(Number(draft.speed), unitSystem),
        // personality is replaced server-side: keep every existing key.
        personality: {
          ...char?.personality,
          ...draft.appearance,
          traits: draft.personality_traits.trim(),
          ideals: draft.ideals.trim(),
          bonds: draft.bonds.trim(),
          flaws: draft.flaws.trim(),
        },
        languages: draft.languages,
        general_proficiencies: draft.general_proficiencies,
        tool_proficiencies: draft.tools,
        damage_modifiers: draft.damageModifiers,
        // settings replaces the whole dict server-side: always merge.
        settings: {
          ...char?.settings,
          senses: fromDraft(SENSE_TYPES, draft.senses, unitSystem),
          speeds: fromDraft(SPEED_TYPES, draft.speeds, unitSystem),
        },
      })
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
      if (draft) setPristine(snapshot(draft))
      setShowErrors(false)
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

  const findErrors = (d: Draft): Record<string, string> => {
    const found: Record<string, string> = {}
    if (!d.name.trim()) found.name = t('character.identity.name_required')
    if (invalidDistance(d.speed)) found.speed = t('character.identity.distance_invalid')
    for (const [field, values] of [['speeds', d.speeds], ['senses', d.senses]] as const) {
      for (const [k, v] of Object.entries(values)) {
        if (invalidDistance(v)) found[`${field}.${k}`] = t('character.identity.distance_invalid')
      }
    }
    return found
  }
  const errors = showErrors ? findErrors(draft) : {}

  const save = (then?: () => void) => {
    const firstInvalid = Object.keys(findErrors(draft))[0]
    if (firstInvalid) {
      setShowErrors(true)
      setLeaving(null)
      // Dopo il render, quando l'errore è in pagina.
      requestAnimationFrame(() => {
        const field = document.querySelector(`[data-field="${firstInvalid}"]`)
        field?.scrollIntoView({ block: 'center' })
        field?.querySelector('input')?.focus({ preventScroll: true })
      })
      return
    }
    mutation.mutate(undefined, { onSuccess: () => then?.() })
  }

  const discard = () => {
    setDraft(JSON.parse(pristine) as Draft)
    setRestored(false)
    setShowErrors(false)
  }

  const leaveWithoutSaving = () => {
    const proceed = leaving
    writeStoredDraft(charId, unitSystem, null)
    setLeaving(null)
    proceed?.()
  }

  const set = (key: keyof Draft) => (v: string) =>
    setDraft((d) => d ? { ...d, [key]: v } : d)

  // null = nessuna lista. Una riga per tipo: non può stare in due liste.
  const setDmg = (slug: string, key: keyof DamageModifiers | null) =>
    setDraft((d) => {
      if (!d) return d
      const next = { ...d.damageModifiers }
      for (const k of DMG_KEYS) next[k] = next[k].filter((v) => v !== slug)
      if (key) next[key] = [...next[key], slug]
      return { ...d, damageModifiers: next }
    })

  // Testo libero: gli alias canonici ("fuoco", "Fire") diventano il tipo (e si applicano), il resto resta homebrew.
  const setCustomDmg = (key: keyof DamageModifiers, entries: string[]) =>
    setDraft((d) => {
      if (!d) return d
      const next = { ...d.damageModifiers }
      const customs: string[] = []
      for (const v of entries) {
        const slug = canonicalDamageType(v)
        if (!slug) { customs.push(v); continue }
        for (const k of DMG_KEYS) next[k] = next[k].filter((x) => x !== slug)
        next[key] = [...next[key], slug]
      }
      next[key] = [...next[key].filter((v) => DMG_SLUGS.includes(v)), ...customs]
      return { ...d, damageModifiers: next }
    })

  const personalitySections = [
    { key: 'personality_traits' as const, label: t('character.identity.personality') },
    { key: 'ideals' as const, label: t('character.identity.ideals') },
    { key: 'bonds' as const, label: t('character.identity.bonds') },
    { key: 'flaws' as const, label: t('character.identity.flaws') },
  ]

  const sectionTitle = '!pl-0 !text-sm !text-dnd-gold-bright'
  const hasCustomDmg = DMG_KEYS.some((k) => draft.damageModifiers[k].some((v) => !DMG_SLUGS.includes(v)))
  const activeDmg = DMG_KEYS.filter((k) => draft.damageModifiers[k].length > 0)

  return (
    <Layout
      title={t('character.identity.title')}
      backTo={`/char/${charId}`}
      group="character"
      page="identity"
      leaveGuard={dirty ? (proceed) => setLeaving(() => proceed) : undefined}
      bottomAction={dirty ? (
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={() => save()}
          loading={mutation.isPending}
          icon={<Save size={20} />}
          haptic="success"
        >
          {t('character.identity.save_changes')}
        </Button>
      ) : undefined}
    >
      {restored && dirty && (
        <div className="flex items-center justify-between gap-3 border-b border-dnd-amber/60 pb-2">
          <span className="text-sm font-body text-dnd-text">{t('character.identity.draft_restored')}</span>
          <Button variant="ghost" size="sm" onClick={discard}>{t('character.identity.draft_discard')}</Button>
        </div>
      )}

      <div data-field="name">
        <Input
          label={t('character.identity.name')}
          value={draft.name}
          onChange={set('name')}
          error={errors.name}
          className="[&_input]:text-xl [&_input]:font-display [&_input]:font-bold"
        />
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <Input label={t('character.identity.race')} value={draft.race} onChange={set('race')} placeholder={t('character.identity.placeholder_race')} />
        <Input label={t('character.identity.gender')} value={draft.gender} onChange={set('gender')} placeholder={t('character.identity.placeholder_gender')} />
        <div className="col-span-2 md:col-span-1">
          <Input label={t('character.identity.alignment')} value={draft.alignment} onChange={set('alignment')} placeholder={t('character.identity.placeholder_alignment')} />
        </div>
      </div>

      {/* In gioco: movimento e sensi */}
      <SectionDivider className={sectionTitle}>
        {t('character.identity.movement_senses')}
      </SectionDivider>

      <div data-field="speed">
        <Input
          label={t('character.identity.speed')}
          type="number"
          min={0}
          value={draft.speed}
          onChange={set('speed')}
          error={errors.speed}
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
      </div>

      <RangeToggles
        keys={SPEED_TYPES} labelKey="character.speeds" field="speeds" values={draft.speeds} errors={errors} defaultFt={30} unitSystem={unitSystem}
        onChange={(speeds) => setDraft((d) => d ? { ...d, speeds } : d)}
      />

      <p className={`mt-4 ${LEDGER_LABEL}`}>{t('character.identity.senses')}</p>
      <RangeToggles
        keys={SENSE_TYPES} labelKey="character.senses" field="senses" values={draft.senses} errors={errors} defaultFt={60} unitSystem={unitSystem}
        onChange={(senses) => setDraft((d) => d ? { ...d, senses } : d)}
      />

      {/* In gioco: modificatori del danno */}
      <SectionDivider className={sectionTitle}>
        {t('character.identity.damage_modifiers')}
      </SectionDivider>

      <p className="text-sm font-body text-dnd-text">
        {activeDmg.length === 0 ? t('character.identity.damage_none') : activeDmg.map((k) => (
          <span key={k} className="block">
            <span className={`font-semibold ${DMG_TEXT[k]}`}>{t(`character.identity.${k}`)}: </span>
            {draft.damageModifiers[k].map((v) => (DMG_SLUGS.includes(v) ? damageTypeLabel(t, v) : v)).join(', ')}
          </span>
        ))}
      </p>
      <p className="text-xs text-dnd-text-faint italic">{t('character.identity.damage_vuln_wins_hint')}</p>

      <div className="divide-y divide-dnd-border/60 border-y border-dnd-border/60">
        {DMG_SLUGS.map((slug) => {
          const label = damageTypeLabel(t, slug)
          const current = DMG_KEYS.find((k) => draft.damageModifiers[k].includes(slug)) ?? null
          const choose = (key: keyof DamageModifiers | null) => { setDmg(slug, key); haptic.selection() }
          const cell = 'h-11 w-11 shrink-0 rounded-lg border text-xs font-cinzel transition-colors'
          const idle = 'border-dnd-border text-dnd-text-muted'
          return (
            <div key={slug} className="flex items-center justify-between gap-2 py-0.5">
              <span className="min-w-0 text-sm font-body text-dnd-text">{label}</span>
              <div className="flex gap-1 shrink-0" role="group" aria-label={label}>
                <Pressable
                  type="button"
                  onClick={() => choose(null)}
                  aria-pressed={current === null}
                  aria-label={`${label}: ${t('character.identity.damage_normal')}`}
                  className={`${cell} ${current === null ? 'border-dnd-border-strong bg-dnd-surface-raised text-dnd-text' : idle}`}
                >
                  –
                </Pressable>
                {DMG_KEYS.map((key) => (
                  <Pressable
                    key={key}
                    type="button"
                    onClick={() => choose(key)}
                    aria-pressed={current === key}
                    aria-label={`${label}: ${t(`character.identity.${key}`)}`}
                    className={`${cell} ${current === key ? `${DMG_TONES[key]} ${DMG_TEXT[key]}` : idle}`}
                  >
                    {t(`character.identity.${key}_short`)}
                  </Pressable>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <Disclosure title={t('character.identity.damage_custom_title')} defaultOpen={hasCustomDmg}>
        {DMG_KEYS.map((key) => {
          const customs = draft.damageModifiers[key].filter((v) => !DMG_SLUGS.includes(v))
          return (
            <ChipInput
              key={key}
              label={t(`character.identity.${key}`)}
              values={customs}
              onChange={(next) => setCustomDmg(key, next)}
              placeholder={t('character.identity.damage_custom_placeholder')}
              hint={customs.length ? t('character.identity.damage_custom_hint') : undefined}
            />
          )
        })}
      </Disclosure>

      {/* Culture */}
      <SectionDivider className={sectionTitle}>
        {t('character.identity.culture')}
      </SectionDivider>

      <ChipInput
        label={t('character.identity.languages')}
        values={draft.languages}
        onChange={(next) => setDraft((d) => d ? { ...d, languages: next } : d)}
        placeholder={t('character.identity.language_placeholder')}
        splitOnComma
        suggestions={LANGUAGE_SUGGESTIONS}
      />
      <ToolProficiencyEditor
        values={draft.tools ?? {}}
        onChange={(next) => setDraft((d) => d ? { ...d, tools: next } : d)}
      />
      {PROF_KEYS.filter((k) => k !== 'tools' || draft.general_proficiencies.tools.length > 0).map((k) => (
        <ChipInput
          key={k}
          label={t(`character.identity.proficiencies_${k}`)}
          values={draft.general_proficiencies[k]}
          onChange={(next) => setDraft((d) => d ? { ...d, general_proficiencies: { ...d.general_proficiencies, [k]: next } } : d)}
          placeholder={t('character.identity.proficiency_placeholder')}
          splitOnComma
          suggestions={k === 'other' ? undefined : profSuggestions[k]}
        />
      ))}

      {/* Biografia */}
      <SectionDivider className={sectionTitle}>
        {t('character.identity.biography')}
      </SectionDivider>

      <p className="flex items-start gap-1.5 text-xs text-dnd-text-faint font-body italic">
        <Lock size={12} className="mt-0.5 shrink-0" />
        {t('character.identity.private_hint')}
      </p>

      <Input
        label={t('character.identity.background')}
        value={draft.background}
        onChange={set('background')}
        placeholder={t('character.identity.placeholder_background')}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {personalitySections.map(({ key, label }) => (
          <Input
            key={key}
            label={label}
            variant="textarea"
            value={draft[key] as string}
            onChange={set(key)}
            rows={2}
            placeholder={t(`character.identity.placeholder_${key}`)}
            // Parte bassa e cresce col testo; dove field-sizing non c'è resta ridimensionabile a mano.
            className="[&_textarea]:min-h-[72px] [&_textarea]:[field-sizing:content]"
          />
        ))}
      </div>

      <Disclosure
        title={t('character.identity.appearance')}
        defaultOpen={APPEARANCE_KEYS.some((k) => draft.appearance[k].trim() !== '')}
      >
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {APPEARANCE_KEYS.map((k) => (
            <Input
              key={k}
              label={t(`character.identity.appearance_${k}`)}
              value={draft.appearance[k]}
              onChange={(v) => setDraft((d) => d ? { ...d, appearance: { ...d.appearance, [k]: v } } : d)}
            />
          ))}
        </div>
      </Disclosure>

      {canShareMessage() && (
        <Button
          variant="ghost"
          fullWidth
          onClick={() => shareCard.mutate()}
          loading={shareCard.isPending}
          icon={<Share2 size={16} />}
          haptic="light"
        >
          {t('share.card')}
        </Button>
      )}

      <Sheet open={leaving !== null} onClose={() => setLeaving(null)} title={t('character.identity.leave_title')}>
        <div className="p-5 space-y-3">
          <p className="text-center font-body text-dnd-text">{t('character.identity.leave_body')}</p>
          <Button variant="primary" size="lg" fullWidth loading={mutation.isPending} icon={<Save size={20} />} haptic="success" onClick={() => save(leaveWithoutSaving)}>
            {t('character.identity.leave_save')}
          </Button>
          <Button variant="danger" fullWidth disabled={mutation.isPending} onClick={leaveWithoutSaving}>
            {t('character.identity.leave_discard')}
          </Button>
        </div>
      </Sheet>
    </Layout>
  )
}
