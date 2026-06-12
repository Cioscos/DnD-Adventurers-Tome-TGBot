import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Plus, Trash2, Pencil, SkipForward, ScrollText } from 'lucide-react'
import {
  GiSparkles as Sparkles, GiCheckedShield as Shield, GiHeartPlus as Heart,
  GiCrossedSwords as Swords,
} from 'react-icons/gi'
import { api } from '@/api/client'
import type { CharacterSummary } from '@/types'
import HPGauge from '@/components/ui/HPGauge'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ChipInput from '@/components/ui/ChipInput'
import Sheet from '@/components/ui/Sheet'
import WizardFooter from '@/components/ui/WizardFooter'
import FancyHeader from '@/components/ui/FancyHeader'
import Reveal from '@/components/ui/Reveal'
import Skeleton from '@/components/ui/Skeleton'
import { WaxSeal } from '@/components/ui/Ornament'
import { haptic, telegramConfirm } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { spring, stagger } from '@/styles/motion'
import languagesSrd from '@/data/languages-srd.json'
import { currentVersion } from '@/lib/version'

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
}

type IdentityPayload = {
  race?: string
  gender?: string
  alignment?: string
  background?: string
  languages?: string[]
  personality?: { traits: string }
}

type Step = 'name' | 'class' | 'identity'

export default function CharacterSelect() {
  const { t } = useTranslation()
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

  const { data: characters = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  const createMutation = useMutation({
    mutationFn: async ({ name, cls, identity }: { name: string; cls: SelectedClass | null; identity: IdentityPayload | null }) => {
      return api.characters.create(
        name,
        cls
          ? {
              class_name: cls.class_name,
              level: 1,
              hit_die: cls.hit_die,
              spellcasting_ability: cls.spellcasting_ability ?? null,
            }
          : null,
        identity,
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

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.characters.delete(id),
    onSuccess: (_, id) => {
      qc.setQueryData<CharacterSummary[]>(['characters'], (old) =>
        old ? old.filter((c) => c.id !== id) : old
      )
      qc.removeQueries({ queryKey: ['character', id] })
      haptic.success()
    },
    onError: () => {
      haptic.error()
      toast.error(t('character.select.delete_failed'))
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
    if (race.trim()) p.race = race.trim()
    if (gender.trim()) p.gender = gender.trim()
    if (alignment.trim()) p.alignment = alignment.trim()
    if (background.trim()) p.background = background.trim()
    if (languages.length) p.languages = languages
    if (personalityTraits.trim()) p.personality = { traits: personalityTraits.trim() }
    return Object.keys(p).length ? p : null
  }

  const handleCreate = (identity: IdentityPayload | null) => {
    createMutation.mutate({ name: newName.trim(), cls: selectedClass ?? null, identity })
  }

  const handleDelete = (char: CharacterSummary) => {
    telegramConfirm(
      t('character.select.delete_confirm', { name: char.name }),
      (confirmed) => {
        if (confirmed) deleteMutation.mutate(char.id)
      }
    )
  }

  // Helpers selezione classe (evidenziazione).
  const isBuiltinSelected = (key: string) =>
    selectedClass != null && selectedClass.class_name === t(`dnd.classes.${key}`)
  const isSkipSelected = selectedClass === null
  const isCustomSelected =
    selectedClass != null &&
    !DND_CLASSES.some((c) => t(`dnd.classes.${c.key}`) === selectedClass.class_name)

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

  if (isError) {
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
    <div className="w-full overflow-hidden" style={{ height: 'var(--tg-vh, 100vh)' }}>
      {/* Own scroll container: the home page no longer relies on document/body
          scroll (broken under the global overscroll-behavior + Telegram
          disableVerticalSwipes), it scrolls inside here like every Layout page. */}
      <div className="h-full overflow-y-auto overflow-x-hidden overscroll-contain p-4 pt-safe pb-safe relative">
      {/* Hero halo behind title */}
      <div
        className="absolute top-0 left-0 right-0 h-60 pointer-events-none"
        style={{ background: 'var(--gradient-hero-halo)' }}
      />

      <div className="relative space-y-5">
        <div className="pt-4">
          <FancyHeader
            title={t('character.select.title')}
            subtitle={t('character.select.subtitle')}
            align="center"
            size="xl"
          />
        </div>

        {/* Session CTA (always available — GM does not need a character) */}
        <Button
          variant="secondary"
          size="md"
          fullWidth
          icon={<Swords size={16} />}
          onClick={() => navigate('/session')}
        >
          {t('session.title')}
        </Button>

        {/* Character roster */}
        {characters.length === 0 ? (
          <m.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ ...spring.elastic, delay: 0.2 }}
            className="flex flex-col items-center gap-4 py-12"
          >
            <m.div
              animate={{ rotate: [0, -3, 3, -2, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
            >
              <WaxSeal size={100} />
            </m.div>
            <p className="text-dnd-text-muted text-center font-body italic max-w-[240px]">
              {t('character.select.empty')}
            </p>
          </m.div>
        ) : (
          <Reveal.Stagger stagger={stagger.list} className="space-y-3">
            {characters.map((char) => {
              const isDown = char.current_hit_points === 0
              return (
              <Reveal.Item key={char.id}>
                <Surface
                  variant="tome"
                  interactive
                  ornamented
                  layoutId={`char-hero-${char.id}`}
                  onClick={() => navigate(`/char/${char.id}`)}
                  className={`overflow-hidden${isDown ? ' !border-dnd-crimson-bright/70 shadow-halo-danger' : ''}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0 space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="font-display font-bold text-lg text-dnd-gold-bright truncate">
                          {char.name}
                        </h2>
                        {isDown && (
                          <span className="text-[10px] font-cinzel uppercase tracking-wider px-2 py-0.5 rounded-full bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson-bright/40 shrink-0">
                            {t('character.select.unconscious_badge')}
                          </span>
                        )}
                        {char.heroic_inspiration && (
                          <Sparkles
                            size={16}
                            className="text-dnd-amber animate-shimmer shrink-0"
                          />
                        )}
                      </div>
                      <p className="text-sm text-dnd-text-muted font-body italic">
                        {char.class_summary}
                        {char.race ? ` · ${char.race}` : ''}
                      </p>

                      {/* HP + AC row */}
                      <div className="mt-2.5 flex items-center gap-2">
                        <span className="inline-flex items-center gap-1 text-xs text-dnd-text-muted font-mono w-[70px] shrink-0">
                          <Heart size={12} className="text-dnd-crimson-bright" />
                          {char.current_hit_points}/{char.hit_points}
                        </span>
                        <div className="flex-1">
                          <HPGauge
                            current={char.current_hit_points}
                            max={char.hit_points}
                            temp={char.temp_hp}
                            size="md"
                            segmented
                          />
                        </div>
                        <span className="inline-flex items-center gap-1 text-xs text-dnd-gold font-mono shrink-0">
                          <Shield size={12} />
                          {char.ac}
                        </span>
                      </div>
                    </div>

                    <m.button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(char)
                      }}
                      className="w-11 h-11 flex items-center justify-center rounded-lg text-dnd-crimson-bright shrink-0 hover:bg-dnd-crimson/10"
                      aria-label={t('common.delete')}
                      whileTap={{ scale: 0.9 }}
                    >
                      <Trash2 size={16} />
                    </m.button>
                  </div>
                </Surface>
              </Reveal.Item>
              )
            })}
          </Reveal.Stagger>
        )}

        {/* New character CTA — always visible, opens wizard Sheet. */}
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

        {/* Version footer — opens the in-app changelog / release notes. */}
        <div className="pt-2 flex justify-center">
          <button
            type="button"
            onClick={() => { haptic.light(); navigate('/changelog') }}
            className="min-h-[44px] px-3 inline-flex items-center gap-1.5 text-dnd-text-faint hover:text-dnd-gold-bright transition-colors"
            aria-label={t('changelog.view')}
          >
            <ScrollText size={13} className="shrink-0" />
            <span className="font-mono tabular-nums text-xs">v{currentVersion()}</span>
          </button>
        </div>
      </div>
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
              <p className="text-[11px] text-dnd-text-faint truncate font-body mb-3">
                {t('character.create.step_class_subtitle', { name: newName.trim() || '—' })}
              </p>

              {!showCustom ? (
                <>
                  <p className="text-[12px] text-dnd-gold-bright font-body italic text-center mb-3">
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
                      <m.button
                        key={cls.key}
                        onClick={() => setSelectedClass({
                          class_name: t(`dnd.classes.${cls.key}`),
                          hit_die: cls.hit_die,
                          spellcasting_ability: cls.spellcasting_ability,
                        })}
                        className={`flex flex-col items-center py-2.5 px-1 rounded-xl
                                   bg-dnd-surface border transition-[box-shadow,border-color] duration-200
                                   text-center
                                   ${isBuiltinSelected(cls.key)
                                     ? '!border-dnd-gold shadow-halo-gold'
                                     : 'border-dnd-border hover:border-dnd-gold/60 hover:shadow-halo-gold'}`}
                        variants={{
                          initial: { opacity: 0, scale: 0.9 },
                          animate: { opacity: 1, scale: 1 },
                        }}
                        whileTap={{ scale: 0.93 }}
                      >
                        <span className="text-[13px] font-display font-bold text-dnd-gold-bright">
                          {t(`dnd.classes.${cls.key}`)}
                        </span>
                        <span className="text-[10px] text-dnd-text-faint font-mono mt-0.5">d{cls.hit_die}</span>
                      </m.button>
                    ))}
                  </m.div>

                  {/* Special options row */}
                  <div className="grid grid-cols-2 gap-2 mb-1">
                    <m.button
                      onClick={() => setShowCustom(true)}
                      className={`flex flex-col items-center justify-center py-2.5 px-1 rounded-xl
                                 bg-dnd-surface-raised border text-center
                                 ${isCustomSelected ? '!border-dnd-gold shadow-halo-gold' : 'border-dnd-gold-dim/40'}`}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.1 }}
                      whileTap={{ scale: 0.93 }}
                    >
                      <Pencil size={14} className="text-dnd-gold-dim mb-0.5" />
                      <span className="text-[13px] font-display font-bold text-dnd-text">
                        {isCustomSelected && selectedClass ? selectedClass.class_name : t('character.create.custom_class')}
                      </span>
                      <span className="text-[10px] text-dnd-text-faint font-mono mt-0.5">
                        {isCustomSelected && selectedClass ? `d${selectedClass.hit_die}` : 'd?'}
                      </span>
                    </m.button>
                    <m.button
                      onClick={() => setSelectedClass(null)}
                      className={`flex flex-col items-center justify-center py-2.5 px-1 rounded-xl
                                 bg-dnd-surface border text-center
                                 ${isSkipSelected ? '!border-dnd-gold shadow-halo-gold' : 'border-dnd-border'}`}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.15 }}
                      whileTap={{ scale: 0.93 }}
                    >
                      <SkipForward size={14} className="text-dnd-text-faint mb-0.5" />
                      <span className="text-[13px] font-display font-bold text-dnd-text">
                        {t('character.create.skip_class')}
                      </span>
                      <span className="text-[10px] text-dnd-text-faint font-mono mt-0.5">—</span>
                    </m.button>
                  </div>

                  <WizardFooter
                    className="mt-4"
                    secondaryLabel={t('common.back')}
                    onSecondary={() => setStep('name')}
                    primaryLabel={`${t('common.next')} →`}
                    onPrimary={() => setStep('identity')}
                    primaryDisabled={selectedClass === undefined}
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

                  <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5">
                    {t('character.create.hit_die')}
                  </p>
                  <div className="flex gap-2 mb-4">
                    {[6, 8, 10, 12].map((d) => (
                      <m.button
                        key={d}
                        onClick={() => setCustomHitDie(d)}
                        className={`flex-1 py-2.5 rounded-xl font-cinzel font-bold text-sm transition-colors
                          ${customHitDie === d
                            ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                            : 'bg-dnd-surface text-dnd-text border border-dnd-border'}`}
                        whileTap={{ scale: 0.95 }}
                      >
                        d{d}
                      </m.button>
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

          {step === 'identity' && (
            <m.div
              key="step-identity"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.18 }}
            >
              <div className="flex justify-end mb-1">
                <button
                  onClick={() => handleCreate(null)}
                  disabled={createMutation.isPending}
                  className="text-[12px] text-dnd-gold-dim hover:text-dnd-gold-bright font-body underline underline-offset-2 disabled:opacity-40"
                >
                  {t('character.create.identity_skip')}
                </button>
              </div>
              <p className="text-[11px] text-dnd-text-faint font-body italic text-center mb-3">
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
                <Input
                  label={t('character.identity.background')}
                  value={background}
                  onChange={setBackground}
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
                onSecondary={() => setStep('class')}
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
    </div>
  )
}
