import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { BookOpen } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import SpeciesChoices from '@/components/character/SpeciesChoices'
import { featByKey } from '@/lib/feats'
import { uiLang } from '@/lib/lang'
import { loadCatalog, localized, type Lang } from '@/lib/srd/catalog'
import { speciesChoicesMissing, type Species2024Entry } from '@/lib/species'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

type T = (k: string, o?: Record<string, unknown>) => string

const ERRORS = ['species_edition', 'species_unknown', 'species_options_invalid']

/** Un codice di `changes` (`codice` o `codice:argomento`) in una riga leggibile. */
function changeLine(code: string, t: T, lang: Lang): string {
  const i = code.indexOf(':')
  const name = i < 0 ? code : code.slice(0, i)
  const arg = i < 0 ? '' : code.slice(i + 1)
  const key = `character.species.changes.${name}`
  if (name === 'traits_archived') return t(key, { count: Number(arg) })
  if (name.startsWith('skill_')) return t(key, { skill: t(`character.skills.${arg}`) })
  if (name.startsWith('feat_')) return t(key, { feat: featByKey(arg)?.name[lang] ?? arg })
  return t(key, { name: arg, defaultValue: code })
}

function errorText(err: unknown, t: T): string {
  const code = err instanceof ApiError && err.status === 422 ? String(err.detail) : ''
  return t(`character.species.errors.${ERRORS.includes(code) ? code : 'generic'}`)
}

/** Opzioni salvate senza le chiavi del server (`_granted_skill`...): il PUT le rifiuterebbe. */
const playerOptions = (o: CharacterFull['species_options']): Record<string, string> =>
  Object.fromEntries(Object.entries(o ?? {}).filter(([k]) => !k.startsWith('_')).map(([k, v]) => [k, String(v)]))

/** Scegli o cambia la specie 2024: picker, scelte, anteprima dei cambiamenti; scrive solo alla conferma. */
export default function SpeciesSheet2024({ char, open, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = uiLang(i18n.language)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [entry, setEntry] = useState<Species2024Entry | null>(null)
  const [options, setOptions] = useState<Record<string, string>>({})
  const [picking, setPicking] = useState(false)
  const [changes, setChanges] = useState<string[] | null>(null)
  const [featToComplete, setFeatToComplete] = useState<string | null>(null)

  // All'apertura (non a ogni aggiornamento della scheda, o il rimando al talento sparirebbe). Cambia specie: si riparte da quella salvata.
  useEffect(() => {
    if (!open) return
    setChanges(null)
    setFeatToComplete(null)
    preview.reset()
    apply.reset()
    setOptions(playerOptions(char.species_options))
    setEntry(null)
    if (char.species_key) {
      void loadCatalog('species-2024').then((all) => setEntry(all.find((e) => e.key === char.species_key) ?? null))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const preview = useMutation({
    mutationFn: () => api.species.preview(char.id, entry!.key, options),
    onSuccess: (r) => setChanges(r.changes),
    onError: () => haptic.error(),
  })
  const apply = useMutation({
    mutationFn: () => api.species.apply(char.id, entry!.key, options),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      const feat = options.origin_feat
      const row = feat ? updated.abilities?.find((a) => a.feature_key === `feat.${feat}` && a.feat_status === 'incomplete') : undefined
      if (row) setFeatToComplete(row.name)
      else onClose()
    },
    onError: () => haptic.error(),
  })

  // Ogni modifica invalida l'anteprima: si conferma solo ciò che si è visto.
  const edit = (next: Species2024Entry | null, opts: Record<string, string>) => {
    setEntry(next)
    setOptions(opts)
    setChanges(null)
    preview.reset()
    apply.reset()
  }

  // Le abilità già competenti, tranne quella data dalla specie attuale (si può tenere o cambiare).
  const takenSkills = Object.entries(char.skills ?? {})
    .filter(([k, v]) => v && k !== char.species_options?._granted_skill).map(([k]) => k)
  const missing = entry ? speciesChoicesMissing(entry, options).length > 0 : true
  const error = preview.error ?? apply.error

  return (
    <>
      <Sheet open={open} onClose={onClose} title={t('character.species.title')}>
        <div className="p-5 space-y-4">
          {featToComplete ? (
            <>
              <p className="font-body text-sm text-dnd-text">{t('character.species.complete_feat', { name: featToComplete })}</p>
              <Button variant="primary" fullWidth onClick={() => navigate(`/char/${char.id}/abilities`)}>
                {t('character.species.go_abilities')}
              </Button>
              <Button variant="ghost" fullWidth onClick={onClose}>{t('common.close')}</Button>
            </>
          ) : (
            <>
              <Button variant="secondary" fullWidth icon={<BookOpen size={16} />} onClick={() => setPicking(true)}>
                {entry ? localized(entry.name, lang).text : t('character.species.pick')}
              </Button>
              {entry && <SpeciesChoices species={entry} value={options} onChange={(o) => edit(entry, o)} takenSkills={takenSkills} />}

              {changes && (
                <div className="rounded-xl border border-dnd-border bg-dnd-surface p-3 space-y-1.5">
                  <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.species.preview_title')}</p>
                  {changes.length === 0 ? (
                    <p className="text-sm font-body text-dnd-text-muted">{t('character.species.no_changes')}</p>
                  ) : (
                    <ul className="space-y-1 text-sm font-body text-dnd-text">
                      {changes.map((c) => (
                        <li key={c} className={c.startsWith('trait_removed:') ? 'pl-4 text-dnd-text-muted' : ''}>
                          {changeLine(c, t, lang)}
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="text-xs font-body italic text-dnd-text-faint">{t('character.species.confirm_hint')}</p>
                </div>
              )}

              {error && <p className="text-sm font-body text-dnd-crimson-bright">{errorText(error, t)}</p>}

              {changes ? (
                <Button variant="primary" fullWidth loading={apply.isPending} onClick={() => apply.mutate()}>
                  {t('character.species.confirm')}
                </Button>
              ) : (
                <Button variant="primary" fullWidth disabled={missing} loading={preview.isPending} onClick={() => preview.mutate()}>
                  {t('character.species.preview')}
                </Button>
              )}
            </>
          )}
        </div>
      </Sheet>
      {picking && (
        <CatalogPicker
          kind="species-2024"
          onClose={() => setPicking(false)}
          onPick={(e) => { edit(e, {}); setPicking(false) }}
        />
      )}
    </>
  )
}
