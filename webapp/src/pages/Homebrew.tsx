import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Plus, CheckCircle2, BookOpenCheck, Zap, Trash2, Loader2 } from 'lucide-react'
import { GiScrollUnfurled, GiPotionBall, GiCauldron } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import SwitchToggle from '@/components/ui/SwitchToggle'
import SectionDivider from '@/components/ui/SectionDivider'
import Skeleton from '@/components/Skeleton'
import Reveal from '@/components/ui/Reveal'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import {
  showHomebrewNotifications,
  type NotificationLike,
} from '@/components/homebrew/HomebrewNotification'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import type { HomebrewRule, TemplateRead } from '@/lib/homebrew/types'

interface RuleCardProps {
  rule: HomebrewRule
  dimmed?: boolean
  onToggle: (enabled: boolean) => void
  onClick: () => void
  onManualTrigger?: () => void
  onDelete: () => void
  isFiring?: boolean
  isDeleting?: boolean
  manualTriggerLabel: string
  deleteLabel: string
}

function RuleCard({
  rule,
  dimmed = false,
  onToggle,
  onClick,
  onManualTrigger,
  onDelete,
  isFiring = false,
  isDeleting = false,
  manualTriggerLabel,
  deleteLabel,
}: RuleCardProps) {
  return (
    <m.div
      onClick={onClick}
      whileTap={{ scale: 0.99 }}
      transition={spring.press}
      className={`group flex items-center gap-3 p-3 rounded-2xl
                  bg-dnd-surface-raised border border-dnd-border
                  hover:border-dnd-gold/60 cursor-pointer
                  transition-[border-color] duration-200 min-h-[64px]
                  ${dimmed ? 'opacity-70' : ''}`}
    >
      <div className="shrink-0 w-10 h-10 rounded-xl bg-dnd-surface border border-dnd-gold-dim/30
                      flex items-center justify-center text-dnd-gold-bright">
        <GiScrollUnfurled size={20} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-display font-bold text-dnd-text truncate">{rule.name}</p>
        {rule.description && (
          <p className="text-xs text-dnd-text-muted font-body italic line-clamp-2 mt-0.5">
            {rule.description}
          </p>
        )}
      </div>
      <div
        onClick={(e) => e.stopPropagation()}
        className="shrink-0 flex items-center gap-1"
      >
        <SwitchToggle checked={rule.enabled} onChange={onToggle} />
        {onManualTrigger && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onManualTrigger()
            }}
            disabled={isFiring}
            title={manualTriggerLabel}
            aria-label={manualTriggerLabel}
            className="w-11 h-11 flex items-center justify-center rounded-xl
                       text-dnd-gold-bright hover:bg-dnd-gold-bright/10
                       active:bg-dnd-gold-bright/20 transition-colors
                       disabled:opacity-50 disabled:cursor-wait"
          >
            {isFiring ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Zap size={18} />
            )}
          </button>
        )}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          disabled={isDeleting}
          title={deleteLabel}
          aria-label={deleteLabel}
          className="w-11 h-11 flex items-center justify-center rounded-xl
                     text-dnd-text-muted hover:text-dnd-crimson hover:bg-dnd-crimson/10
                     active:bg-dnd-crimson/20 transition-colors
                     disabled:opacity-50 disabled:cursor-wait"
        >
          {isDeleting ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Trash2 size={18} />
          )}
        </button>
      </div>
    </m.div>
  )
}

interface TemplateCardProps {
  template: TemplateRead
  installed: boolean
  installing: boolean
  onInstall: () => void
  t: (key: string) => string
}

function TemplateCard({ template, installed, installing, onInstall, t }: TemplateCardProps) {
  const surfaceClasses = installed
    ? 'bg-dnd-emerald/5 border-dashed border-dnd-emerald/40'
    : 'bg-dnd-gold-bright/5 border-dashed border-dnd-gold-bright/30'

  return (
    <div className={`flex flex-col gap-2 p-3 rounded-2xl border ${surfaceClasses}`}>
      <div className="flex items-start gap-2">
        <span className="text-2xl leading-none shrink-0" aria-hidden>
          {template.icon}
        </span>
        <p className="font-display font-bold text-dnd-text leading-tight flex-1 min-w-0">
          {template.name}
        </p>
      </div>
      <p className="text-xs text-dnd-text-muted font-body italic line-clamp-3 min-h-[3.6em]">
        {template.description}
      </p>
      {installed ? (
        <Button
          variant="ghost"
          size="sm"
          disabled
          icon={<CheckCircle2 size={14} />}
          fullWidth
        >
          {t('homebrew.installed_state')}
        </Button>
      ) : (
        <Button
          variant="secondary"
          size="sm"
          loading={installing}
          onClick={onInstall}
          icon={<Plus size={14} />}
          fullWidth
          haptic="success"
        >
          {t('homebrew.install_template')}
        </Button>
      )}
    </div>
  )
}

export default function Homebrew() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  const { data: rules, error: rulesError } = useQuery({
    queryKey: ['homebrew-rules', charId],
    queryFn: () => api.homebrew.listRules(charId),
  })
  const { data: templates, error: templatesError } = useQuery({
    queryKey: ['homebrew-templates'],
    queryFn: () => api.homebrew.listTemplates(),
  })

  const installMut = useMutation({
    mutationFn: (templateId: string) => api.homebrew.installTemplate(charId, templateId),
    onSuccess: () => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['homebrew-rules', charId] })
    },
    onError: () => haptic.error(),
  })

  const toggleMut = useMutation({
    mutationFn: ({ ruleId, enabled }: { ruleId: number; enabled: boolean }) =>
      api.homebrew.toggleEnabled(charId, ruleId, enabled),
    onMutate: async ({ ruleId, enabled }) => {
      // cancel in-flight refetches so they can't clobber the optimistic write
      await qc.cancelQueries({ queryKey: ['homebrew-rules', charId] })
      // optimistic update keeps the switch flicker-free
      const previous = qc.getQueryData<HomebrewRule[]>(['homebrew-rules', charId])
      if (previous) {
        qc.setQueryData<HomebrewRule[]>(
          ['homebrew-rules', charId],
          previous.map((r) => (r.id === ruleId ? { ...r, enabled } : r)),
        )
      }
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(['homebrew-rules', charId], ctx.previous)
      haptic.error()
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['homebrew-rules', charId] }),
  })

  // Manual trigger — same `{notifications: [...]}` shape as turn-start, so the
  // global MutationCache handler (keyed on `homebrew_notifications`) skips it.
  // We surface notifications by hand; empty list → neutral info toast so the
  // tap is always acknowledged. The Phase 3 dispatcher fires ALL enabled rules
  // with a `manual_trigger`, not just the one whose card was tapped — the
  // response's `rule_id` is informative only.
  const manualTriggerMut = useMutation({
    mutationFn: (ruleId: number) => api.homebrew.manualTrigger(charId, ruleId),
    onSuccess: (resp) => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['homebrew-resources', charId] })
      const list = resp?.notifications
      if (Array.isArray(list) && list.length > 0) {
        showHomebrewNotifications(list as NotificationLike[])
      } else {
        toast.info(t('homebrew.manual_trigger_no_effect'))
      }
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const deleteMut = useMutation({
    mutationFn: (ruleId: number) => api.homebrew.deleteRule(charId, ruleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['homebrew-rules', charId] })
      setConfirmDeleteId(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (rulesError || templatesError) {
    return (
      <Layout title={t('homebrew.page_title')}>
        <div className="p-4">
          <Surface variant="ember">
            <p className="text-sm font-body text-dnd-text">{t('homebrew.load_error')}</p>
          </Surface>
        </div>
      </Layout>
    )
  }

  if (!rules || !templates) {
    return (
      <Layout title={t('homebrew.page_title')}>
        <Skeleton.Ornament />
        <Skeleton.Rect height="72px" />
        <Skeleton.Rect height="72px" delay={80} />
        <Skeleton.Rect height="72px" delay={160} />
        <Skeleton.Ornament delay={200} />
        <div className="grid grid-cols-2 gap-3">
          <Skeleton.Rect height="140px" delay={240} />
          <Skeleton.Rect height="140px" delay={300} />
          <Skeleton.Rect height="140px" delay={360} />
          <Skeleton.Rect height="140px" delay={420} />
        </div>
      </Layout>
    )
  }

  const active = rules.filter((r) => r.enabled)
  const disabled = rules.filter((r) => !r.enabled)
  const installedIds = new Set(
    rules.map((r) => r.template_id).filter((v): v is string => Boolean(v)),
  )

  return (
    <Layout title={t('homebrew.page_title')}>
      {/* Active rules */}
      <m.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={spring.drift}
      >
        <div className="flex items-center justify-between gap-2 mb-2">
          <SectionDivider icon={<GiCauldron size={11} />}>
            <span className="flex items-center gap-1.5">
              {t('homebrew.sections.active')}
              <span className="font-mono tabular-nums text-dnd-text-faint">· {active.length}</span>
            </span>
          </SectionDivider>
        </div>
        <Button
          variant="primary"
          size="sm"
          icon={<Plus size={14} />}
          fullWidth
          onClick={() => navigate(`/char/${charId}/homebrew/new`)}
        >
          {t('homebrew.create_new')}
        </Button>

        {active.length === 0 ? (
          <Surface variant="flat" className="text-center py-5 mt-3">
            <p className="text-dnd-text-muted font-body italic">
              {t('homebrew.no_rules_yet')}
            </p>
          </Surface>
        ) : (
          <Reveal.Stagger stagger={stagger.listTight} delay={0.05} className="space-y-2 mt-3">
            {active.map((r) => {
              const hasManualTrigger = (r.dsl.triggers ?? []).some(
                (tr) => tr.event === 'manual_trigger',
              )
              const showManual = r.enabled && hasManualTrigger
              return (
                <Reveal.Item key={r.id}>
                  <RuleCard
                    rule={r}
                    onToggle={(enabled) => toggleMut.mutate({ ruleId: r.id, enabled })}
                    onClick={() => navigate(`/char/${charId}/homebrew/${r.id}`)}
                    onManualTrigger={
                      showManual ? () => manualTriggerMut.mutate(r.id) : undefined
                    }
                    onDelete={() => setConfirmDeleteId(r.id)}
                    isFiring={
                      manualTriggerMut.isPending && manualTriggerMut.variables === r.id
                    }
                    isDeleting={deleteMut.isPending && deleteMut.variables === r.id}
                    manualTriggerLabel={t('homebrew.manual_trigger')}
                    deleteLabel={t('common.delete')}
                  />
                </Reveal.Item>
              )
            })}
          </Reveal.Stagger>
        )}
      </m.section>

      {/* Disabled rules — only rendered when present */}
      {disabled.length > 0 && (
        <m.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring.drift, delay: 0.05 }}
        >
          <SectionDivider icon={<GiPotionBall size={11} />}>
            <span className="flex items-center gap-1.5">
              {t('homebrew.sections.disabled')}
              <span className="font-mono tabular-nums text-dnd-text-faint">
                · {disabled.length}
              </span>
            </span>
          </SectionDivider>
          <Reveal.Stagger stagger={stagger.listTight} delay={0.05} className="space-y-2">
            {disabled.map((r) => (
              <Reveal.Item key={r.id}>
                <RuleCard
                  rule={r}
                  dimmed
                  onToggle={(enabled) => toggleMut.mutate({ ruleId: r.id, enabled })}
                  onClick={() => navigate(`/char/${charId}/homebrew/${r.id}`)}
                  onDelete={() => setConfirmDeleteId(r.id)}
                  isDeleting={deleteMut.isPending && deleteMut.variables === r.id}
                  manualTriggerLabel={t('homebrew.manual_trigger')}
                  deleteLabel={t('common.delete')}
                />
              </Reveal.Item>
            ))}
          </Reveal.Stagger>
        </m.section>
      )}

      {/* Templates library */}
      <m.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring.drift, delay: 0.1 }}
      >
        <SectionDivider icon={<BookOpenCheck size={11} />} align="center">
          {t('homebrew.sections.library')}
        </SectionDivider>
        <Reveal.Stagger stagger={stagger.listTight} delay={0.05} className="grid grid-cols-2 gap-3">
          {templates.map((tpl) => (
            <Reveal.Item key={tpl.id}>
              <TemplateCard
                template={tpl}
                installed={installedIds.has(tpl.id)}
                installing={installMut.isPending && installMut.variables === tpl.id}
                onInstall={() => installMut.mutate(tpl.id)}
                t={t}
              />
            </Reveal.Item>
          ))}
        </Reveal.Stagger>
      </m.section>

      <ConfirmSheet
        open={confirmDeleteId !== null}
        onClose={() => setConfirmDeleteId(null)}
        title={t('homebrew.delete_title')}
        body={t('homebrew.delete_confirm', {
          name: rules.find((r) => r.id === confirmDeleteId)?.name ?? '',
        })}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        confirmVariant="danger"
        loading={deleteMut.isPending}
        onConfirm={() => confirmDeleteId !== null && deleteMut.mutate(confirmDeleteId)}
      />
    </Layout>
  )
}
