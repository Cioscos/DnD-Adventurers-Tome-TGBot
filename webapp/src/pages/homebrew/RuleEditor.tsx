import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronDown } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/Skeleton'
import type { RuleDSL } from '@/lib/homebrew/types'
import IdentitySection from './sections/IdentitySection'
import SubjectSection from './sections/SubjectSection'
import PropertiesSection from './sections/PropertiesSection'
import TablesSection from './sections/TablesSection'
import PassiveModifiersSection from './sections/PassiveModifiersSection'
import TriggersSection from './sections/TriggersSection'

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

  const { data: rule, isLoading } = useQuery({
    queryKey: ['homebrew-rule', charId, ruleId],
    queryFn: () => api.homebrew.getRule(charId, Number(ruleId)),
    enabled: !isNew,
  })

  const [dsl, setDsl] = useState<RuleDSL>(emptyDsl)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

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

  // Reset hydration flag when navigating between rules
  useEffect(() => {
    hasHydratedRef.current = false
  }, [ruleId])

  const handleSave = () => {
    // Task 4.12 will wire create/update mutation + validation here.
    // eslint-disable-next-line no-console
    console.log('[RuleEditor] save (placeholder)', { isNew, charId, name, description, dsl })
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
            onChange={(n, d) => {
              setName(n)
              setDescription(d)
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

        <Button variant="primary" fullWidth onClick={handleSave} haptic="success">
          {t('common.save')}
        </Button>
      </div>
    </Layout>
  )
}
