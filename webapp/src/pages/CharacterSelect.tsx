import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { classSummary } from '@/lib/classLabel'
import { m } from 'framer-motion'
import { Plus, Pencil, SkipForward, ScrollText, Upload, BookOpen, Link2 } from 'lucide-react'
import {
  GiPolarStar as Star, GiCheckedShield as Shield, GiHeartPlus as Heart,
  GiCrossedSwords as Swords,
} from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import { cardStatus, effectiveAc, effectiveHpMax } from '@/lib/characterStatus'
import HPGauge from '@/components/ui/HPGauge'
import CampaignSessionBanner from '@/components/ui/CampaignSessionBanner'
import OfflineNotice from '@/components/ui/OfflineNotice'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import PageHelp from '@/components/PageHelp'
import Input from '@/components/ui/Input'
import ChipInput from '@/components/ui/ChipInput'
import Sheet from '@/components/ui/Sheet'
import DdbImportSheet from '@/components/character/DdbImportSheet'
import WizardFooter from '@/components/ui/WizardFooter'
import Reveal from '@/components/ui/Reveal'
import Skeleton from '@/components/ui/Skeleton'
import { WaxSeal } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { resetHubReturn } from '@/lib/hubReturn'
import { useToast } from '@/hooks/useToast'
import { stagger } from '@/styles/motion'
import languagesSrd from '@/data/languages-srd.json'
import SpeciesStep, { type SpeciesChoice } from '@/pages/creation/SpeciesStep'
import AbilityScoresStep from '@/pages/creation/AbilityScoresStep'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import ClassSkillChoice from '@/components/ClassSkillChoice'
import { useClassProficiencies } from '@/hooks/useClassProficiencies'
import { creationExtras, backgroundLanguages, backgroundSkills as mapBackgroundSkills, buildSpecies } from '@/lib/species'
import { localized } from '@/lib/srd/catalog'
import { STANDARD_ARRAY, arrayScores, scoresValid, type ScoreMode, type Scores } from '@/lib/pointBuy'

const LANGUAGE_SUGGESTIONS = [...languagesSrd.common, ...languagesSrd.exotic]

const DND_CLASSES = [
  { key: 'barbarian', hit_die: 12, spellcasting_ability: null },
  { key: 'bard',      hit_die: 8,  spellcasting_ability: 'charisma' },
  { key: 'cleric',    hit_die: 8,  spellcasting_ability: 'wisdom' },
  { key: 'druid',     hit_die: 8,  spellcasting_ability: 'wisdom' },
  { key: 'fighter',   hit_die: 10, spellcasting_ability: null },
  { key: 'rogue',     hit_die: 8,  spellcasting_ability: null },
  { key: 'wizard',    hit_die: 6,  spellcasting_ability: 'intelligence' },
  { key: 'monk',      hit_die: 8,  spellcasting_ability: null },
  { key: 'paladin',   hit_die: 10, spellcasting_ability: 'charisma' },
  { key: 'ranger',    hit_die: 10, spellcasting_ability: 'wisdom' },
  { key: 'sorcerer',  hit_die: 6,  spellcasting_ability: 'charisma' },
  { key: 'warlock',   hit_die: 8,  spellcasting_ability: 'charisma' },
] as const

type SelectedClass = {
  class_name: string
  hit_die: number
  spellcasting_ability: string | null
  /** Abilità di classe scelte (2014 per i personaggi nuovi). */
  skills?: string[]
}

type IdentityPayload = {
  race?: string
  gender?: string
  alignment?: string
  background?: string
  languages?: string[]
  personality?: { traits: string }
}

type Step = 'name' | 'class' | 'species' | 'abilities' | 'identity'

// `detail` e' una stringa (413) oppure la lista di errori pydantic (422): mostriamo i primi msg con il campo.
function importErrorText(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return ''
  return detail
    .slice(0, 3)
    .map((d: { msg?: unknown; loc?: unknown }) => {
      if (typeof d?.msg !== 'string') return ''
      const loc = Array.isArray(d.loc) ? d.loc.filter((x) => x !== 'body').join('.') : ''
      return loc ? `${loc}: ${d.msg}` : d.msg
    })
    .filter(Boolean)
    .join('; ')
}

export default function CharacterSelect() {
  // Riaprire un PG dalla lista rifà le animazioni d'ingresso dell'hub.
  useEffect(() => { resetHubReturn() }, [])
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()

  const [creating, setCreating] = useState(false)
  const [step, setStep] = useState<Step>('name')
  const [newName, setNewName] = useState('')

  // Class: undefined = nessuna scelta ancora; null = "salta classe"; oggetto = scelta.
  const [selectedClass, setSelectedClass] = useState<SelectedClass | null | undefined>(undefined)
  const [showCustom, setShowCustom] = useState(false)
  const [customName, setCustomName] = useState('')
  const [customHitDie, setCustomHitDie] = useState<number>(8)

  // Identità (tutti opzionali).
  const [race, setRace] = useState('')
  const [gender, setGender] = useState('')
  const [alignment, setAlignment] = useState('')
  const [background, setBackground] = useState('')
  const [languages, setLanguages] = useState<string[]>([])
  const [personalityTraits, setPersonalityTraits] = useState('')

  // Specie, punteggi, background dal catalogo (tutti opzionali).
  const [species, setSpecies] = useState<SpeciesChoice>({ race: null, sub: null })
  const [scoreMode, setScoreMode] = useState<ScoreMode>('array')
  const [scores, setScores] = useState<Scores>(arrayScores())
  const [scorePool, setScorePool] = useState<number[]>(STANDARD_ARRAY)
  const [scoresSkipped, setScoresSkipped] = useState(false)
  const [pickBackground, setPickBackground] = useState(false)
  const [backgroundSkills, setBackgroundSkills] = useState<string[]>([])
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const speciesPayload = species.race ? buildSpecies(species.race, species.sub, lang) : null

  const charactersQuery = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
    // Le modifiche sulla scheda (PF, morte, CA) non invalidano la lista: al ritorno in
    // home va sempre riletta, anche entro lo staleTime.
    refetchOnMount: 'always',
  })
  const { isLoading, isError, refetch } = charactersQuery
  // Il default vuoto solo qui: il controllo dell'errore deve vedere l'assenza di dati.
  const characters = charactersQuery.data ?? []

  // Sessione attiva: un errore equivale a nessuna sessione (il pulsante resta quello semplice).
  const { data: activeSession } = useQuery({
    queryKey: ['session-me'],
    queryFn: () => api.sessions.me(),
    retry: false,
  })
  const hasActiveSession = activeSession?.status === 'active'

  const createMutation = useMutation({
    mutationFn: async ({ name, cls, identity, extras }: { name: string; cls: SelectedClass | null; identity: IdentityPayload | null; extras: ReturnType<typeof creationExtras> }) => {
      return api.characters.create(
        name,
        cls
          ? {
              class_name: cls.class_name,
              level: 1,
              hit_die: cls.hit_die,
              spellcasting_ability: cls.spellcasting_ability ?? null,
              ...(cls.skills?.length ? { skill_choices: cls.skills } : {}),
            }
          : null,
        identity,
        extras,
      )
    },
    onSuccess: (char) => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      resetWizard()
      haptic.success()
      navigate(`/char/${char.id}`)
    },
    onError: () => {
      toast.error(t('character.create.create_failed'))
    },
  })

  const fileRef = useRef<HTMLInputElement>(null)
  const [ddbOpen, setDdbOpen] = useState(false)
  const importMutation = useMutation({
    mutationFn: (file: File) => api.characters.import(file),
    onSuccess: (char) => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      haptic.success()
      navigate(`/char/${char.id}`)
    },
    onError: (e) => {
      toast.error((e instanceof ApiError && importErrorText(e.detail)) || t('character.select.import_failed'))
    },
  })

  const resetWizard = () => {
    setCreating(false)
    setStep('name')
    setNewName('')
    setSelectedClass(undefined)
    setShowCustom(false)
    setCustomName('')
    setCustomHitDie(8)
    setRace('')
    setGender('')
    setAlignment('')
    setBackground('')
    setLanguages([])
    setPersonalityTraits('')
    setSpecies({ race: null, sub: null })
    setScoreMode('array')
    setScores(arrayScores())
    setScorePool(STANDARD_ARRAY)
    setScoresSkipped(false)
    setBackgroundSkills([])
    setPickBackground(false)
  }

  const handleNameNext = () => {
    if (!newName.trim()) return
    setStep('class')
  }

  const handleCustomSelect = () => {
    if (!customName.trim()) return
    setSelectedClass({ class_name: customName.trim(), hit_die: customHitDie, spellcasting_ability: null })
    setShowCustom(false)
  }

  const buildIdentityPayload = (): IdentityPayload | null => {
    const p: IdentityPayload = {}
    if (race.trim() && !species.race) p.race = race.trim()
    if (gender.trim()) p.gender = gender.trim()
    if (alignment.trim()) p.alignment = alignment.trim()
    if (background.trim()) p.background = background.trim()
    if (languages.length) p.languages = languages
    if (personalityTraits.trim()) p.personality = { traits: personalityTraits.trim() }
    return Object.keys(p).length ? p : null
  }

  const handleCreate = (identity: IdentityPayload | null) => {
    const extras = creationExtras({ scores, skipped: scoresSkipped, species: speciesPayload, skills: backgroundSkills })
    createMutation.mutate({ name: newName.trim(), cls: selectedClass ?? null, identity, extras })
  }

  // Helpers selezione classe (evidenziazione).
  const isBuiltinSelected = (key: string) =>
    selectedClass != null && selectedClass.class_name === t(`dnd.classes.${key}`)
  const isSkipSelected = selectedClass === null
  const isCustomSelected =
    selectedClass != null &&
    !DND_CLASSES.some((c) => t(`dnd.classes.${c.key}`) === selectedClass.class_name)

  const classProf = useClassProficiencies('2014', selectedClass && !isCustomSelected ? selectedClass.class_name : null, false)
  const classSkillsIncomplete =
    !!selectedClass && !isCustomSelected &&
    (classProf.isLoading || (selectedClass.skills?.length ?? 0) !== (classProf.data?.skills_count ?? 0))

  if (isLoading) {
    return (
      <div className="min-h-screen p-4 space-y-4 pb-safe pt-safe animate-fade-in">
        <Skeleton.Line width="220px" height="32px" />
        <Skeleton.Rect height="140px" />
        <Skeleton.Rect height="140px" delay={100} />
        <Skeleton.Rect height="140px" delay={200} />
      </div>
    )
  }

  if (isError && charactersQuery.data === undefined) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-4">
        <p className="text-dnd-crimson-bright font-body">{t('common.error')}</p>
        <Button onClick={() => refetch()} variant="primary">
          {t('common.retry')}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex w-full flex-col overflow-hidden" style={{ height: 'var(--tg-vh, 100vh)' }}>
      {/* Own scroll container: the home page no longer relies on document/body
          scroll (broken under the global overscroll-behavior + Telegram
          disableVerticalSwipes), it scrolls inside here like every Layout page. */}
      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain px-4 pb-4 pt-safe">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3 pt-3">
          <h1 className="min-w-0 font-display text-2xl font-bold leading-tight text-dnd-gold-bright">
            {t('character.select.title')}
          </h1>
          <PageHelp helpKey="home" title={t('character.select.title')} />
        </div>

        <OfflineNotice query={charactersQuery} />

        <CampaignSessionBanner />

        {/* Session CTA (always available — GM does not need a character) */}
        <Button
          variant="secondary"
          size="md"
          fullWidth
          icon={<Swords size={16} />}
          onClick={() => navigate(hasActiveSession ? `/session/${activeSession!.id}` : '/session')}
        >
          {hasActiveSession ? t('session.resume') : t('session.title')}
        </Button>

        {/* Character roster */}
        {characters.length === 0 ? (
          <div className="flex flex-col items-center gap-4 py-12">
            <WaxSeal size={100} />
            <p className="text-dnd-text-muted text-center font-body italic max-w-[240px]">
              {t('character.select.empty')}
            </p>
          </div>
        ) : (
          <Reveal.Stagger stagger={stagger.list} className="border-y border-dnd-border divide-y divide-dnd-border/60">
            {characters.map((char) => {
              const status = cardStatus(char)
              const isDanger = status === 'dead' || status === 'down'
              const hpMax = effectiveHpMax(char)
              return (
              <Reveal.Item key={char.id}>
                <Pressable
                  onClick={() => navigate(`/char/${char.id}`)}
                  whileTap={{ scale: 0.99 }}
                  className={`my-0.5 block w-full px-1 py-3 text-left transition-colors hover:bg-dnd-surface/60${isDanger ? ' bg-dnd-crimson/10' : ''}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="min-w-0 truncate font-display text-lg font-bold text-dnd-text">
                          {char.name}
                        </h2>
                        {status === 'down' && (
                          <span className="text-xs font-cinzel uppercase tracking-wider px-2 py-0.5 rounded-lg bg-dnd-crimson/10 text-dnd-crimson-bright border border-dnd-crimson-bright/40 shrink-0">
                            {t('character.select.unconscious_badge')}
                          </span>
                        )}
                        {status === 'dead' && (
                          <span className="text-xs font-cinzel uppercase tracking-wider px-2 py-0.5 rounded-lg bg-dnd-crimson/10 text-dnd-crimson-bright border border-dnd-crimson-bright/40 shrink-0">
                            {t('character.select.dead_badge')}
                          </span>
                        )}
                        {status === 'unconfigured' && (
                          <span className="text-xs font-cinzel uppercase tracking-wider px-2 py-0.5 rounded-lg text-dnd-text-muted border border-dnd-border shrink-0">
                            {t('character.select.unconfigured_badge')}
                          </span>
                        )}
                        {char.heroic_inspiration && (
                          <Star
                            size={16}
                            aria-hidden
                            className="text-dnd-amber shrink-0"
                          />
                        )}
                      </div>
                      <p className="text-sm text-dnd-text-muted font-body italic">
                        {char.classes ? classSummary(t, char.classes) : char.class_summary}
                        {char.race ? ` · ${char.race}` : ''}
                      </p>

                      {/* HP + AC row */}
                      <div className="mt-2 flex items-center gap-2">
                        <span className="inline-flex items-center gap-1 text-sm font-bold text-dnd-text font-mono tabular-nums shrink-0">
                          <Heart size={13} aria-hidden className="text-dnd-crimson-bright" />
                          {char.current_hit_points}/{hpMax}
                        </span>
                        <div className="flex-1">
                          <HPGauge
                            current={char.current_hit_points}
                            max={hpMax}
                            temp={char.temp_hp}
                            size="md"
                            segmented
                          />
                        </div>
                        <span className="inline-flex items-center gap-1 text-sm font-bold text-dnd-text font-mono tabular-nums shrink-0">
                          <Shield size={13} aria-hidden className="text-dnd-gold" />
                          {effectiveAc(char)}
                        </span>
                      </div>
                    </div>

                  </div>
                </Pressable>
              </Reveal.Item>
              )
            })}
          </Reveal.Stagger>
        )}

        <input
          ref={fileRef}
          type="file"
          accept=".json,application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) importMutation.mutate(file)
          }}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="min-h-[44px]"
            icon={<Upload size={14} />}
            loading={importMutation.isPending}
            onClick={() => fileRef.current?.click()}
          >
            {t('character.select.import')}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="min-h-[44px]"
            icon={<Link2 size={14} />}
            onClick={() => setDdbOpen(true)}
          >
            {t('character.select.import_ddb')}
          </Button>
        </div>
        <DdbImportSheet open={ddbOpen} onClose={() => setDdbOpen(false)} />

        {/* Version footer — opens the in-app changelog / release notes. */}
        <div className="flex justify-center">
          <Pressable
            onClick={() => { haptic.light(); navigate('/changelog') }}
            className="min-h-[44px] px-3 inline-flex items-center gap-1.5 text-dnd-text-faint hover:text-dnd-gold-bright transition-colors"
            aria-label={t('changelog.view')}
          >
            <ScrollText size={13} className="shrink-0" />
            <span className="font-mono tabular-nums text-xs">v{__APP_VERSION__}</span>
          </Pressable>
        </div>
      </div>
      </div>

      {/* Il pulsante d'oro della pagina: fisso in basso, a portata di pollice. */}
      <div className="shrink-0 border-t border-dnd-border bg-dnd-bg px-4 pt-3 pb-safe-cta">
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={() => setCreating(true)}
          icon={<Plus size={20} />}
          haptic="medium"
        >
          {t('character.select.new')}
        </Button>
      </div>

      {/* Creation wizard — modal Sheet. Flusso: Nome → Classe → Identità → Crea. */}
      <Sheet
        open={creating}
        onClose={() => {
          if (!createMutation.isPending) resetWizard()
        }}
        title={
          step === 'name'
            ? t('character.create.step_name')
            : step === 'class'
            ? t('character.create.step_class')
            : step === 'species'
            ? t('character.create.step_species')
            : step === 'abilities'
            ? t('character.create.step_abilities')
            : t('character.create.step_identity')
        }
        dismissible={!createMutation.isPending}
      >
        <div className="p-5">
          {step === 'name' && (
            <m.div
              key="step-name"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.18 }}
            >
              <Input
                value={newName}
                onChange={setNewName}
                placeholder={t('character.create.name_placeholder')}
                autoFocus
                onCommit={handleNameNext}
              />
              <WizardFooter
                className="mt-4"
                secondaryLabel={t('common.cancel')}
                onSecondary={resetWizard}
                primaryLabel={`${t('common.next')} →`}
                onPrimary={handleNameNext}
                primaryDisabled={!newName.trim()}
                primaryHaptic="medium"
              />
            </m.div>
          )}

          {step === 'class' && (
            <m.div
              key="step-class"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.18 }}
            >
              {/* L'hint della griglia classi nomina già il PG: il sottotitolo serve solo nella vista custom */}
              {showCustom && (
                <p className="text-xs text-dnd-text-faint truncate font-body mb-3">
                  {t('character.create.step_class_subtitle', { name: newName.trim() || '—' })}
                </p>
              )}

              {!showCustom ? (
                <>
                  <p className="text-xs text-dnd-text-muted font-body italic text-center mb-3">
                    {t('character.create.tap_class_hint', { name: newName.trim() || '—' })}
                  </p>

                  <m.div
                    className="grid grid-cols-3 gap-2 mb-3"
                    initial="initial"
                    animate="animate"
                    variants={{
                      initial: {},
                      animate: { transition: { staggerChildren: 0.03 } },
                    }}
                  >
                    {DND_CLASSES.map((cls) => (
                      <Pressable
                        key={cls.key}
                        onClick={() => setSelectedClass({
                          class_name: t(`dnd.classes.${cls.key}`),
                          hit_die: cls.hit_die,
                          spellcasting_ability: cls.spellcasting_ability,
                          skills: isBuiltinSelected(cls.key) ? selectedClass?.skills : [],
                        })}
                        className={`flex flex-col items-center py-2.5 px-1 rounded-xl
                                   border transition-colors duration-200
                                   text-center
                                   ${isBuiltinSelected(cls.key)
                                     ? '!border-dnd-gold bg-dnd-gold/20'
                                     : 'border-dnd-border hover:border-dnd-gold/60'}`}
                        variants={{
                          initial: { opacity: 0, scale: 0.9 },
                          animate: { opacity: 1, scale: 1 },
                        }}
                        whileTap={{ scale: 0.93 }}
                      >
                        <span className="text-sm font-body font-semibold text-dnd-text">
                          {t(`dnd.classes.${cls.key}`)}
                        </span>
                        <span className="text-xs text-dnd-text-faint font-mono mt-0.5">d{cls.hit_die}</span>
                      </Pressable>
                    ))}
                  </m.div>

                  {selectedClass && !isCustomSelected && (
                    <div className="mb-3">
                      <ClassSkillChoice
                        edition="2014"
                        className={selectedClass.class_name}
                        asMulticlass={false}
                        value={selectedClass.skills ?? []}
                        onChange={(skills) => setSelectedClass({ ...selectedClass, skills })}
                      />
                    </div>
                  )}

                  {/* Special options row */}
                  <div className="grid grid-cols-2 gap-2 mb-1">
                    <Pressable
                      onClick={() => setShowCustom(true)}
                      className={`flex flex-col items-center justify-center py-2.5 px-1 rounded-xl
                                 border text-center
                                 ${isCustomSelected ? '!border-dnd-gold bg-dnd-gold/20' : 'border-dnd-border'}`}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.1 }}
                      whileTap={{ scale: 0.93 }}
                    >
                      <Pencil size={14} className="text-dnd-gold-dim mb-0.5" />
                      <span className="text-sm font-body font-semibold text-dnd-text">
                        {isCustomSelected && selectedClass ? selectedClass.class_name : t('character.create.custom_class')}
                      </span>
                      <span className="text-xs text-dnd-text-faint font-mono mt-0.5">
                        {isCustomSelected && selectedClass ? `d${selectedClass.hit_die}` : 'd?'}
                      </span>
                    </Pressable>
                    <Pressable
                      onClick={() => setSelectedClass(null)}
                      className={`flex flex-col items-center justify-center py-2.5 px-1 rounded-xl
                                 border text-center
                                 ${isSkipSelected ? '!border-dnd-gold bg-dnd-gold/20' : 'border-dnd-border'}`}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.15 }}
                      whileTap={{ scale: 0.93 }}
                    >
                      <SkipForward size={14} className="text-dnd-text-faint mb-0.5" />
                      <span className="text-sm font-body font-semibold text-dnd-text">
                        {t('character.create.skip_class')}
                      </span>
                      <span className="text-xs text-dnd-text-faint font-mono mt-0.5">—</span>
                    </Pressable>
                  </div>

                  <WizardFooter
                    className="mt-4"
                    secondaryLabel={t('common.back')}
                    onSecondary={() => setStep('name')}
                    primaryLabel={`${t('common.next')} →`}
                    onPrimary={() => setStep('species')}
                    primaryDisabled={selectedClass === undefined || classSkillsIncomplete}
                    primaryHaptic="medium"
                  />
                </>
              ) : (
                <m.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <Input
                    label={t('character.create.custom_class_name')}
                    value={customName}
                    onChange={setCustomName}
                    placeholder={t('character.create.custom_class_placeholder')}
                    autoFocus
                    onCommit={handleCustomSelect}
                    className="mb-3"
                  />

                  <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5">
                    {t('character.create.hit_die')}
                  </p>
                  <div className="flex gap-2 mb-4">
                    {[6, 8, 10, 12].map((d) => (
                      <Pressable
                        key={d}
                        onClick={() => setCustomHitDie(d)}
                        className={`flex-1 py-2.5 rounded-xl font-cinzel font-bold text-sm transition-colors
                          ${customHitDie === d
                            ? 'border border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright'
                            : 'text-dnd-text border border-dnd-border'}`}
                        whileTap={{ scale: 0.95 }}
                      >
                        d{d}
                      </Pressable>
                    ))}
                  </div>

                  <WizardFooter
                    secondaryLabel={t('common.back')}
                    onSecondary={() => setShowCustom(false)}
                    primaryLabel={t('common.confirm')}
                    onPrimary={handleCustomSelect}
                    primaryDisabled={!customName.trim()}
                    primaryHaptic="medium"
                  />
                </m.div>
              )}
            </m.div>
          )}

          {step === 'species' && (
            <m.div key="step-species" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.18 }}>
              <SpeciesStep choice={species} onChoice={setSpecies} freeText={race} onFreeText={setRace} />
              <WizardFooter
                className="mt-4"
                secondaryLabel={t('common.back')}
                onSecondary={() => setStep('class')}
                primaryLabel={`${t('common.next')} →`}
                onPrimary={() => setStep('abilities')}
                primaryHaptic="medium"
              />
            </m.div>
          )}

          {step === 'abilities' && (
            <m.div key="step-abilities" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.18 }}>
              <AbilityScoresStep
                mode={scoreMode}
                scores={scores}
                pool={scorePool}
                bonuses={speciesPayload?.ability_bonuses ?? {}}
                onChange={(mode, sc, pool) => { setScoreMode(mode); setScores(sc); setScorePool(pool) }}
              />
              <WizardFooter
                className="mt-4"
                secondaryLabel={t('common.back')}
                onSecondary={() => setStep('species')}
                primaryLabel={`${t('common.next')} →`}
                onPrimary={() => { setScoresSkipped(false); setStep('identity') }}
                primaryDisabled={!scoresValid(scoreMode, scores)}
                primaryHaptic="medium"
              />
              <Pressable
                onClick={() => { setScoresSkipped(true); setScoreMode('array'); setScores(arrayScores()); setScorePool(STANDARD_ARRAY); setStep('identity') }}
                className="mt-1 w-full min-h-[44px] text-xs text-dnd-gold-dim underline underline-offset-2"
              >
                {t('character.create.scores_skip')}
              </Pressable>
            </m.div>
          )}

          {step === 'identity' && (
            <m.div
              key="step-identity"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.18 }}
            >
              <div className="flex justify-end mb-1">
                <Pressable
                  onClick={() => handleCreate(null)}
                  pending={createMutation.isPending}
                  className="min-h-[44px] text-xs text-dnd-gold-dim hover:text-dnd-gold-bright font-body underline underline-offset-2 disabled:opacity-40"
                >
                  {t('character.create.identity_skip')}
                </Pressable>
              </div>
              <p className="text-xs text-dnd-text-faint font-body italic text-center mb-3">
                {t('character.create.identity_optional_hint')}
              </p>

              <div className="space-y-3">
                <Input
                  label={t('character.identity.race')}
                  value={race}
                  onChange={setRace}
                  placeholder={t('character.identity.placeholder_race')}
                />
                <Input
                  label={t('character.identity.gender')}
                  value={gender}
                  onChange={setGender}
                  placeholder={t('character.identity.placeholder_gender')}
                />
                <Input
                  label={t('character.identity.alignment')}
                  value={alignment}
                  onChange={setAlignment}
                  placeholder={t('character.identity.placeholder_alignment')}
                />
                <Button variant="secondary" fullWidth icon={<BookOpen size={16} />} onClick={() => setPickBackground(true)}>
                  {t('character.create.background_pick')}
                </Button>
                <Input
                  label={t('character.identity.background')}
                  value={background}
                  onChange={(v) => { setBackground(v); setBackgroundSkills([]) }}
                  placeholder={t('character.identity.placeholder_background')}
                />
                <ChipInput
                  label={t('character.identity.languages')}
                  values={languages}
                  onChange={setLanguages}
                  placeholder={t('character.identity.language_placeholder')}
                  splitOnComma
                  suggestions={LANGUAGE_SUGGESTIONS}
                />
                <Input
                  variant="textarea"
                  label={t('character.identity.personality')}
                  value={personalityTraits}
                  onChange={setPersonalityTraits}
                  rows={3}
                  placeholder={t('character.identity.placeholder_personality_traits')}
                />
              </div>

              <WizardFooter
                className="mt-4"
                secondaryLabel={t('common.back')}
                onSecondary={() => setStep('abilities')}
                primaryLabel={t('character.create.create_cta')}
                onPrimary={() => handleCreate(buildIdentityPayload())}
                primaryDisabled={createMutation.isPending}
                primaryLoading={createMutation.isPending}
                primaryHaptic="success"
              />
            </m.div>
          )}
        </div>
      </Sheet>
      {pickBackground && (
        <CatalogPicker
          kind="backgrounds"
          onClose={() => setPickBackground(false)}
          onPick={(e) => {
            setBackground(localized(e.name, lang).text)
            setBackgroundSkills(mapBackgroundSkills(e.skill_proficiencies as string[] | undefined))
            setLanguages((prev) => [...new Set([...prev, ...backgroundLanguages(e.languages as string[] | undefined, lang)])])
            setPickBackground(false)
          }}
        />
      )}
    </div>
  )
}
