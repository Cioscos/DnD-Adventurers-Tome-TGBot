import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, CheckCircle2, Link2, MinusCircle } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import type { DdbImportResult, DdbReportEntry } from '@/types'

const ERROR_CODES = ['invalid_link', 'ddb_private', 'ddb_not_found', 'ddb_unreachable', 'ddb_invalid', 'edition_required']

function errorCode(e: unknown): string | null {
  if (!(e instanceof ApiError)) return null
  const code = (e.detail as { code?: unknown } | null)?.code
  return typeof code === 'string' && ERROR_CODES.includes(code) ? code : null
}

export default function DdbImportSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [url, setUrl] = useState('')
  const [result, setResult] = useState<DdbImportResult | null>(null)

  const mutation = useMutation({
    mutationFn: ({ link, edition }: { link: string; edition?: '2014' | '2024' }) =>
      api.characters.importDdb(link, edition),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['characters'] })
      haptic.success()
      setResult(res)
    },
    onError: (e) => {
      if (errorCode(e) !== 'edition_required') haptic.error()
    },
  })

  const close = () => {
    if (mutation.isPending) return
    setUrl('')
    setResult(null)
    mutation.reset()
    onClose()
  }

  const code = mutation.isError ? errorCode(mutation.error) : null
  // Classi di edizioni diverse: la scelta non è un errore del link, si chiede sotto il campo.
  const needsEdition = code === 'edition_required'
  const error = mutation.isError && !needsEdition
    ? (code ? t(`ddb_import.errors.${code}`) : t('character.select.import_failed'))
    : undefined

  const label = (e: DdbReportEntry) =>
    [t(`ddb_import.sections.${e.section}`, { defaultValue: e.section }), e.name].filter(Boolean).join(': ')
  const reason = (e: DdbReportEntry) =>
    t(`ddb_import.reasons.${e.reason.replace(/^ddb\.reason\./, '')}`, { defaultValue: e.reason })

  return (
    <Sheet open={open} onClose={close} title={t(result ? 'ddb_import.summary_title' : 'ddb_import.title')}>
      {!result ? (
        <form
          className="px-5 py-5 space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (url.trim()) mutation.mutate({ link: url.trim() })
          }}
        >
          <ol className="list-decimal pl-5 space-y-1.5 font-body text-sm text-dnd-text">
            <li>{t('ddb_import.step_public')}</li>
            <li>{t('ddb_import.step_link')}</li>
          </ol>
          <p className="font-body text-xs text-dnd-text-muted">{t('ddb_import.private_after')}</p>
          <Input
            label={t('ddb_import.link_label')}
            inputMode="url"
            value={url}
            onChange={(v) => {
              setUrl(v)
              if (mutation.isError) mutation.reset()
            }}
            placeholder={t('ddb_import.placeholder')}
            error={error}
            disabled={mutation.isPending}
          />
          {needsEdition ? (
            <div className="space-y-2" role="group" aria-label={t('ddb_import.edition_title')}>
              <p className="font-cinzel uppercase tracking-wider text-xs text-dnd-text-muted">
                {t('ddb_import.edition_title')}
              </p>
              <p className="font-body text-sm text-dnd-text">{t('ddb_import.edition_body')}</p>
              <div className="grid grid-cols-2 gap-2">
                {(['2014', '2024'] as const).map((ed) => (
                  <Button
                    key={ed}
                    variant="secondary"
                    loading={mutation.isPending && mutation.variables?.edition === ed}
                    disabled={mutation.isPending}
                    onClick={() => mutation.mutate({ link: url.trim(), edition: ed })}
                  >
                    {t(`ddb_import.edition_${ed}`)}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <Button
              type="submit"
              fullWidth
              icon={<Link2 size={16} />}
              loading={mutation.isPending}
              disabled={!url.trim()}
            >
              {t('ddb_import.submit')}
            </Button>
          )}
        </form>
      ) : (
        <div className="px-5 py-5 space-y-4">
          <div className="grid grid-cols-3 gap-2 text-center">
            {([
              ['imported', result.report.imported.length, CheckCircle2, 'text-dnd-emerald-bright'],
              ['approximated', result.report.approximated.length, AlertTriangle, 'text-dnd-amber'],
              ['skipped', result.report.skipped.length, MinusCircle, 'text-dnd-text-muted'],
            ] as const).map(([key, count, Icon, color]) => (
              <div key={key} className="rounded-lg bg-dnd-surface-raised py-2.5 px-1">
                <Icon size={16} className={`mx-auto ${color}`} />
                <div className="font-mono tabular-nums text-lg text-dnd-text mt-1">{count}</div>
                <div className="font-cinzel uppercase tracking-wider text-[0.7rem] text-dnd-text-muted">
                  {t(`ddb_import.${key}`)}
                </div>
              </div>
            ))}
          </div>
          {(['approximated', 'skipped'] as const).map((key) =>
            result.report[key].length > 0 && (
              <section key={key}>
                <h3 className="font-cinzel uppercase tracking-wider text-xs text-dnd-text-muted mb-1.5">
                  {t(`ddb_import.${key}`)}
                </h3>
                <ul className="space-y-1.5">
                  {result.report[key].map((e, i) => (
                    <li key={i} className="font-body text-sm leading-snug">
                      <span className="text-dnd-text">{label(e)}</span>
                      <span className="text-dnd-text-muted">: {reason(e)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ),
          )}
          <Button
            fullWidth
            onClick={() => {
              const id = result.character.id
              close()
              navigate(`/char/${id}`)
            }}
          >
            {t('ddb_import.open')}
          </Button>
        </div>
      )}
    </Sheet>
  )
}
