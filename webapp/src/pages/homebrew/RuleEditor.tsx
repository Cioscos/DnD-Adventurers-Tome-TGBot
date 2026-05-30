import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronDown } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/Skeleton'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import type { HomebrewRule, RuleDSL } from '@/lib/homebrew/types'
import IdentitySection from './sections/IdentitySection'
import SubjectSection from './sections/SubjectSection'
import PropertiesSection from './sections/PropertiesSection'
import TablesSection from './sections/TablesSection'
import PassiveModifiersSection from './sections/PassiveModifiersSection'
import TriggersSection from './sections/TriggersSection'

// -----------------------------------------------------------------------------
// Pydantic 422 detail can be a plain string ("Rule must declare at least one
// trigger or passive_modifier") or a list of `{ loc, msg, type }` items from
// the framework's RequestValidationError. Format both pragmatically.
// -----------------------------------------------------------------------------
function formatPydanticError(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d: unknown) => {
        const item = d as { loc?: unknown[]; msg?: string }
        const loc = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
        const msg = item.msg ?? ''
        return loc ? `${loc}: ${msg}` : msg
      })
      .filter(Boolean)
      .join('; ')
  }
  return null
}

// -----------------------------------------------------------------------------
// Empty DSL skeleton — declared at module scope so it isn't re-created on every
// render. Won't pass backend strict validation (no triggers/modifiers yet);
// that's fine — Task 4.12 validates only at Save time.
// -----------------------------------------------------------------------------
function emptyDsl(): RuleDSL {
  return {
    version: 1,
    subject: { type: 'item' },
    properties: [],
    tables: [],
    passive_modifiers: [],
    resources: [],
    triggers: [],
  }
}

// -----------------------------------------------------------------------------
// Collapsible panel — native <details>/<summary> with custom chevron, matching
// DESIGN.md (Two Inks, Inscription header, Warm-Shadow border).
// -----------------------------------------------------------------------------
interface CollapsiblePanelProps {
  title: string
  defaultOpen?: boolean
  children: ReactNode
}

function CollapsiblePanel({ title, defaultOpen = true, children }: CollapsiblePanelProps) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-2xl border border-dnd-border bg-dnd-surface-raised
                 shadow-parchment-md overflow-hidden
                 [&[open]>summary>svg]:rotate-180"
    >
      <summary
        className="flex items-center justify-between gap-3 px-4 py-3 cursor-pointer select-none
                   marker:hidden [&::-webkit-details-marker]:hidden
                   hover:bg-dnd-surface/40 transition-colors"
      >
        <span className="font-display font-bold text-dnd-gold-bright text-sm tracking-wide">
          {title}
        </span>
        <ChevronDown
          size={18}
          className="text-dnd-gold-dim transition-transform duration-200 shrink-0"
          aria-hidden
        />
      </summary>
      <div className="px-3 pb-3 pt-1">{children}</div>
    </details>
  )
}

// -----------------------------------------------------------------------------
// RuleEditor — shell for /char/:id/homebrew/new and /char/:id/homebrew/:ruleId
// -----------------------------------------------------------------------------
export default function RuleEditor() {
  const { id, ruleId } = useParams<{ id: string; ruleId?: string }>()
  const charId = Number(id)
  const isNew = !ruleId || ruleId === 'new'
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()

  const { data: rule, isLoading } = useQuery({
    queryKey: ['homebrew-rule', charId, ruleId],
    queryFn: () => api.homebrew.getRule(charId, Number(ruleId)),
    enabled: !isNew,
  })

  const [dsl, setDsl] = useState<RuleDSL>(emptyDsl)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [nameError, setNameError] = useState<string | undefined>(undefined)
  const nameInputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null)

  // Hydrate local state on first successful fetch only — guard against
  // refetches clobbering in-progress user edits.
  const hasHydratedRef = useRef(false)
  useEffect(() => {
    if (rule && !hasHydratedRef.current) {
      setDsl(rule.dsl)
      setName(rule.name)
      setDescription(rule.description ?? '')
      hasHydratedRef.current = true
    }
  }, [rule])

  // Reset hydration flag when navigating between rules. When the new route is
  // the "create" form, also clear any draft left over from a previously edited
  // rule — React Router reuses the same component instance (no key), so local
  // state would otherwise leak across the navigation. For an existing rule we
  // only clear the flag here; the hydration effect (which runs on [rule]) then
  // re-populates the form once the query resolves.
  useEffect(() => {
    hasHydratedRef.current = false
    setNameError(undefined)
    if (isNew) {
      setDsl(emptyDsl())
      setName('')
      setDescription('')
    }
  }, [ruleId, isNew])

  // ---------------------------------------------------------------------------
  // Mutations — create (POST) or update (PATCH). Both go through the same
  // success path: invalidate caches, success toast, navigate back to the list.
  // ---------------------------------------------------------------------------
  const onMutationSuccess = (_data: HomebrewRule) => {
    queryClient.invalidateQueries({ queryKey: ['homebrew-rules', charId] })
    if (!isNew && ruleId) {
      queryClient.invalidateQueries({ queryKey: ['homebrew-rule', charId, ruleId] })
    }
    toast.success(t('homebrew.editor.save_success'))
    navigate(`/char/${charId}/homebrew`)
  }

  const onMutationError = (err: unknown) => {
    if (err instanceof ApiError && err.status === 422) {
      const formatted = formatPydanticError(err.detail)
      toast.error(t('homebrew.editor.save_error_title'), {
        description: formatted ?? t('homebrew.editor.save_error_generic'),
      })
      return
    }
    const description =
      err instanceof ApiError && typeof err.detail === 'string' ? err.detail : undefined
    toast.error(t('homebrew.editor.save_error_title'), {
      description: description ?? t('homebrew.editor.save_error_generic'),
    })
  }

  const createMut = useMutation({
    mutationFn: () =>
      api.homebrew.createRule(charId, {
        name: name.trim(),
        description: description.trim() || null,
        dsl,
        enabled: true,
      }),
    onSuccess: onMutationSuccess,
    onError: onMutationError,
  })

  const updateMut = useMutation({
    mutationFn: () =>
      api.homebrew.updateRule(charId, Number(ruleId), {
        name: name.trim(),
        description: description.trim() || null,
        dsl,
      }),
    onSuccess: onMutationSuccess,
    onError: onMutationError,
  })

  const isSaving = createMut.isPending || updateMut.isPending

  const handleSave = () => {
    if (isSaving) return
    // Name is required — surface the error inline on the field (crimson +
    // shake), scroll it into view and focus it. The identity panel may be
    // scrolled off-screen when the user taps Save at the bottom of the form.
    if (!name.trim()) {
      setNameError(t('homebrew.editor.validation.name_required'))
      haptic.error()
      nameInputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      nameInputRef.current?.focus()
      return
    }
    // Behaviour gate — backend's Pydantic is the source of truth for nested
    // validation (subject, properties, tables, etc.); this is a cheap pre-check.
    const triggerCount = dsl.triggers?.length ?? 0
    const modifierCount = dsl.passive_modifiers?.length ?? 0
    if (triggerCount === 0 && modifierCount === 0) {
      toast.error(t('homebrew.editor.validation.no_behavior'))
      haptic.error()
      return
    }
    if (isNew) {
      createMut.mutate()
    } else {
      updateMut.mutate()
    }
  }

  const handleCancel = () => {
    if (isSaving) return
    navigate(-1)
  }

  const title = isNew ? t('homebrew.editor.new_title') : (name || t('homebrew.editor.edit_title'))

  if (!isNew && isLoading) {
    return (
      <Layout title={title}>
        <Skeleton.Rect height="72px" />
        <Skeleton.Rect height="120px" delay={80} />
        <Skeleton.Rect height="120px" delay={160} />
        <Skeleton.Rect height="120px" delay={240} />
      </Layout>
    )
  }

  return (
    <Layout title={title}>
      <div className="space-y-3">
        <CollapsiblePanel title={t('homebrew.editor.sections.identity')} defaultOpen>
          <IdentitySection
            name={name}
            description={description}
            nameError={nameError}
            nameInputRef={nameInputRef}
            onChange={(n, d) => {
              setName(n)
              setDescription(d)
              if (nameError && n.trim()) setNameError(undefined)
            }}
          />
        </CollapsiblePanel>

        <CollapsiblePanel title={t('homebrew.editor.sections.subject')} defaultOpen>
          <SubjectSection
            subject={dsl.subject}
            onChange={(subject) => setDsl((prev) => ({ ...prev, subject }))}
          />
        </CollapsiblePanel>

        <CollapsiblePanel title={t('homebrew.editor.sections.properties')} defaultOpen>
          <PropertiesSection
            properties={dsl.properties ?? []}
            onChange={(properties) => setDsl((prev) => ({ ...prev, properties }))}
          />
        </CollapsiblePanel>

        <CollapsiblePanel title={t('homebrew.editor.sections.tables')} defaultOpen={false}>
          <TablesSection
            tables={dsl.tables ?? []}
            properties={dsl.properties ?? []}
            onChange={(tables) => setDsl((prev) => ({ ...prev, tables }))}
          />
        </CollapsiblePanel>

        <CollapsiblePanel title={t('homebrew.editor.sections.passive_modifiers')} defaultOpen>
          <PassiveModifiersSection
            mods={dsl.passive_modifiers ?? []}
            onChange={(mods) => setDsl((prev) => ({ ...prev, passive_modifiers: mods }))}
          />
        </CollapsiblePanel>

        <CollapsiblePanel title={t('homebrew.editor.sections.triggers')} defaultOpen>
          <TriggersSection
            triggers={dsl.triggers}
            tables={dsl.tables ?? []}
            onChange={(triggers) => setDsl((prev) => ({ ...prev, triggers }))}
          />
        </CollapsiblePanel>

        <div className="flex gap-2 pt-2">
          <Button
            variant="secondary"
            fullWidth
            onClick={handleCancel}
            disabled={isSaving}
          >
            {t('common.cancel')}
          </Button>
          <Button
            variant="primary"
            fullWidth
            onClick={handleSave}
            loading={isSaving}
            haptic="success"
          >
            {t('common.save')}
          </Button>
        </div>
      </div>
    </Layout>
  )
}
