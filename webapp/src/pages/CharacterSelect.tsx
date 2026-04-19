import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Trash2, Sparkles, Shield, Heart, ArrowLeft, Pencil } from 'lucide-react'
import { api } from '@/api/client'
import type { CharacterSummary } from '@/types'
import HPGauge from '@/components/ui/HPGauge'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import FancyHeader from '@/components/ui/FancyHeader'
import Reveal from '@/components/ui/Reveal'
import Skeleton from '@/components/ui/Skeleton'
import { WaxSeal } from '@/components/ui/Ornament'
import { haptic, telegramConfirm } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'

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

type Step = 'name' | 'class'

export default function CharacterSelect() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [step, setStep] = useState<Step>('name')
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [showCustom, setShowCustom] = useState(false)
  const [customName, setCustomName] = useState('')
  const [customHitDie, setCustomHitDie] = useState<number>(8)

  const { data: characters = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
  })

  const createMutation = useMutation({
    mutationFn: async ({ name, cls }: { name: string; cls: SelectedClass | null }) => {
      const char = await api.characters.create(name)
      if (cls) {
        await api.classes.add(char.id, {
          class_name: cls.class_name,
          level: 1,
          hit_die: cls.hit_die,
          spellcasting_ability: cls.spellcasting_ability ?? undefined,
        })
      }
      return char
    },
    onSuccess: (char) => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      resetWizard()
      haptic.success()
      navigate(`/char/${char.id}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.characters.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      haptic.success()
    },
  })

  const resetWizard = () => {
    setCreating(false)
    setStep('name')
    setNewName('')
    setShowCustom(false)
    setCustomName('')
    setCustomHitDie(8)
  }

  const handleNameNext = () => {
    if (!newName.trim()) return
    setStep('class')
  }

  const handleCreate = (cls: SelectedClass | null) => {
    createMutation.mutate({ name: newName.trim(), cls })
  }

  const handleCustomCreate = () => {
    if (!customName.trim()) return
    handleCreate({ class_name: customName.trim(), hit_die: customHitDie, spellcasting_ability: null })
  }

  const handleDelete = (char: CharacterSummary) => {
    telegramConfirm(
      t('character.select.delete_confirm', { name: char.name }),
      (confirmed) => {
        if (confirmed) deleteMutation.mutate(char.id)
      }
    )
  }

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
        <p className="text-[var(--dnd-crimson-bright)] font-body">{t('common.error')}</p>
        <Button onClick={() => refetch()} variant="primary">
          {t('common.retry')}
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 pt-safe pb-safe relative">
      {/* Hero halo behind title */}
      <div
        className="absolute top-0 left-0 right-0 h-60 pointer-events-none"
        style={{ background: 'var(--gradient-hero-halo)' }}
      />

      <div className="relative space-y-5">
        <div className="pt-4">
          <FancyHeader
            title={t('character.select.title')}
            subtitle={t('character.select.subtitle', { defaultValue: 'Scegli un eroe per la tua avventura' })}
            align="center"
            size="xl"
          />
        </div>

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
            {characters.map((char) => (
              <Reveal.Item key={char.id}>
                <Surface
                  variant="tome"
                  interactive
                  ornamented
                  layoutId={`char-hero-${char.id}`}
                  onClick={() => navigate(`/char/${char.id}`)}
                  className="overflow-hidden"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0 space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="font-display font-bold text-lg text-dnd-gold-bright truncate">
                          {char.name}
                        </h2>
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
                          <Heart size={12} className="text-[var(--dnd-crimson-bright)]" />
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
                      className="p-2 rounded-lg text-[var(--dnd-crimson-bright)] shrink-0 hover:bg-[var(--dnd-crimson)]/10"
                      aria-label="Elimina"
                      whileTap={{ scale: 0.9 }}
                    >
                      <Trash2 size={16} />
                    </m.button>
                  </div>
                </Surface>
              </Reveal.Item>
            ))}
          </Reveal.Stagger>
        )}

        {/* Creation wizard */}
        <AnimatePresence mode="wait">
          {creating ? (
            <m.div
              key="wizard"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              transition={spring.drift}
            >
              <Surface variant="elevated" ornamented className="mt-2">
                <AnimatePresence mode="wait" initial={false}>
                  {step === 'name' ? (
                    <m.div
                      key="step-name"
                      initial={{ opacity: 0, x: -16 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -16 }}
                      transition={{ duration: 0.2 }}
                    >
                      <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold mb-3">
                        {t('character.create.step_name')}
                      </p>
                      <Input
                        value={newName}
                        onChange={setNewName}
                        placeholder={t('character.create.name_placeholder', { defaultValue: 'Il nome del tuo eroe' })}
                        autoFocus
                        onCommit={handleNameNext}
                      />
                      <div className="flex gap-2 mt-4">
                        <Button
                          variant="primary"
                          fullWidth
                          onClick={handleNameNext}
                          disabled={!newName.trim()}
                          haptic="medium"
                        >
                          {t('common.confirm')} →
                        </Button>
                        <Button variant="secondary" fullWidth onClick={resetWizard}>
                          {t('common.cancel')}
                        </Button>
                      </div>
                    </m.div>
                  ) : (
                    <m.div
                      key="step-class"
                      initial={{ opacity: 0, x: 16 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 16 }}
                      transition={{ duration: 0.2 }}
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <m.button
                          onClick={() => setStep('name')}
                          className="w-8 h-8 rounded-full bg-dnd-surface border border-dnd-gold-dim/30 flex items-center justify-center text-dnd-gold"
                          whileTap={{ scale: 0.9 }}
                        >
                          <ArrowLeft size={16} />
                        </m.button>
                        <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold flex-1">
                          {t('character.create.step_class')}
                        </p>
                      </div>

                      {!showCustom ? (
                        <>
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
                                onClick={() => handleCreate({
                                  class_name: t(`dnd.classes.${cls.key}`),
                                  hit_die: cls.hit_die,
                                  spellcasting_ability: cls.spellcasting_ability,
                                })}
                                disabled={createMutation.isPending}
                                className="flex flex-col items-center py-2.5 px-1 rounded-xl
                                           bg-dnd-surface border border-dnd-border
                                           hover:border-dnd-gold/60 hover:shadow-halo-gold
                                           transition-[box-shadow,border-color] duration-200
                                           text-center disabled:opacity-40"
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
                            <m.button
                              onClick={() => setShowCustom(true)}
                              className="flex flex-col items-center justify-center py-2.5 px-1 rounded-xl
                                         bg-gradient-arcane-mist border border-dnd-arcane/30
                                         text-center"
                              variants={{
                                initial: { opacity: 0, scale: 0.9 },
                                animate: { opacity: 1, scale: 1 },
                              }}
                              whileTap={{ scale: 0.93 }}
                            >
                              <Pencil size={14} className="text-dnd-arcane-bright mb-0.5" />
                              <span className="text-[10px] text-dnd-arcane-bright font-cinzel uppercase tracking-wider">
                                {t('character.create.custom_class')}
                              </span>
                            </m.button>
                          </m.div>

                          <Button
                            variant="ghost"
                            fullWidth
                            onClick={() => handleCreate(null)}
                            disabled={createMutation.isPending}
                            className="text-dnd-text-muted text-xs"
                          >
                            ◈ {t('character.create.skip_class')} ◈
                          </Button>
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
                            placeholder="Artificer..."
                            autoFocus
                            onCommit={handleCustomCreate}
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

                          <div className="flex gap-2">
                            <Button
                              variant="primary"
                              fullWidth
                              onClick={handleCustomCreate}
                              disabled={!customName.trim() || createMutation.isPending}
                              loading={createMutation.isPending}
                              haptic="success"
                            >
                              {t('common.confirm')}
                            </Button>
                            <Button variant="secondary" fullWidth onClick={() => setShowCustom(false)}>
                              {t('common.back')}
                            </Button>
                          </div>
                        </m.div>
                      )}
                    </m.div>
                  )}
                </AnimatePresence>
              </Surface>
            </m.div>
          ) : (
            <m.div
              key="create-button"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={spring.snappy}
            >
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
            </m.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
