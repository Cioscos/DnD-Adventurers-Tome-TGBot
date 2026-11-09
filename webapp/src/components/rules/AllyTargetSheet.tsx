import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'

type Label = { it: string; en: string }
/** Togliere condizioni (Task 48): lo stesso foglio sceglie anche cosa togliere e a quante creature. `count` null: l'incantesimo toglie tutto ciò che ammette. */
export type Removal = {
  conditions: { key: string; label: Label }[]
  untracked: { key: string; label: Label }[]
  count: number | null
  maxTargets: number
  onConfirm: (r: { targets: (number | string)[]; conditions?: string[] }) => void
}
export type Ally = { id: number; name: string; /** Dado che ha già: darne un altro lo sostituisce. */ die?: number | null }
type Props = {
  /** Il privilegio che apre il foglio: il titolo è il suo nome. */
  title: string
  /** Il privilegio dà un dado (Ispirazione Bardica): la domanda parla di dado e chi ne ha già uno lo sostituisce. */
  die?: boolean
  allies: Ally[]
  /** Più creature insieme (Mantello di Ispirazione): si spuntano fino a `max` e si conferma con `onPickMany`. */
  max?: number
  onPickMany?: (allyIds: number[]) => void
  pending?: boolean
  removal?: Removal
  /** `null`: un'altra creatura (PNG o personaggio non seduto): si usa senza bersaglio, solo esito e durata. */
  onPick: (allyId: number | null) => void
  onClose: () => void
}

/** A chi va un dado o un effetto che aiuta un alleato: i personaggi seduti alla stessa serata (Ispirazione Bardica).
 *  Chi ha già un dado lo perde se ne arriva un altro: prima si conferma. */
export default function AllyTargetSheet({ title, die = false, allies, max = 1, onPickMany, pending = false, removal, onPick, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const [who, setWho] = useState<(number | string)[]>([])
  const [what, setWhat] = useState<string[]>([])
  const [replacing, setReplacing] = useState<Ally | null>(null)
  const [chosen, setChosen] = useState<number[]>([])
  const many = max > 1 && !!onPickMany
  const toggle = (id: number) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length < max ? [...c, id] : c))
  if (removal) {
    const options = [...removal.conditions, ...removal.untracked]
    const toggleWho = (id: number | string) => setWho((w) => (w.includes(id) ? w.filter((x) => x !== id) : removal.maxTargets === 1 ? [id] : w.length < removal.maxTargets ? [...w, id] : w))
    const toggleWhat = (k: string) => setWhat((w) => (w.includes(k) ? w.filter((x) => x !== k) : removal.count === 1 ? [k] : w.length < (removal.count ?? 0) ? [...w, k] : w))
    const ready = who.length > 0 && (removal.count === null || what.length > 0)
    return (
      <Sheet open onClose={onClose} title={title} zClassName="z-[60]">
        <div className="flex flex-col gap-2 px-4 pb-4">
          {removal.count !== null && (
            <>
              <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{t('character.turn.removal_what', { n: removal.count })}</p>
              <div className="flex flex-wrap gap-2">
                {options.map((o) => (
                  <Button key={o.key} size="sm" variant={what.includes(o.key) ? 'primary' : 'secondary'} className="break-words" disabled={pending} onClick={() => toggleWhat(o.key)}>
                    {o.label[lang]}
                  </Button>
                ))}
              </div>
            </>
          )}
          <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{removal.maxTargets > 1 ? t('character.turn.ally_pick_many', { n: removal.maxTargets }) : t('character.turn.removal_who')}</p>
          <Button variant={who.includes('self') ? 'primary' : 'secondary'} className="justify-start text-left" disabled={pending} onClick={() => toggleWho('self')}>{t('character.turn.removal_self')}</Button>
          {allies.map((a) => (
            <Button key={a.id} variant={who.includes(a.id) ? 'primary' : 'secondary'} className="justify-start break-words text-left" disabled={pending} onClick={() => toggleWho(a.id)}>{a.name}</Button>
          ))}
          <Button variant={who.includes('other') ? 'primary' : 'ghost'} className="justify-start break-words text-left" disabled={pending} onClick={() => toggleWho('other')}>{t('character.turn.ally_other')}</Button>
          <Button variant="primary" disabled={pending || !ready} onClick={() => removal.onConfirm({ targets: who, ...(removal.count === null ? {} : { conditions: what }) })}>
            {t('character.turn.removal_confirm')}
          </Button>
        </div>
      </Sheet>
    )
  }
  return (
    <Sheet open onClose={onClose} title={title} zClassName="z-[60]">
      <div className="flex flex-col gap-2 px-4 pb-4">
        {replacing ? (
          <>
            <p className="text-sm font-body text-dnd-text">{t('character.turn.ally_has_die', { die: replacing.die, name: replacing.name })}</p>
            <Button variant="primary" disabled={pending} onClick={() => onPick(replacing.id)}>
              {t('character.turn.ally_replace')}
            </Button>
            <Button variant="secondary" disabled={pending} onClick={() => setReplacing(null)}>
              {t('character.turn.ally_back')}
            </Button>
          </>
        ) : (
          <>
            <p className="text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">{many ? t('character.turn.ally_pick_many', { n: max }) : t(die ? 'character.turn.ally_pick' : 'character.turn.ally_pick_effect')}</p>
            {allies.map((a) => (
              <Button key={a.id} variant={many && chosen.includes(a.id) ? 'primary' : 'secondary'} className="justify-start break-words text-left" disabled={pending}
                onClick={() => (many ? toggle(a.id) : die && a.die ? setReplacing(a) : onPick(a.id))}>
                {a.name}
                {die && a.die ? <span className="ml-2 text-xs font-normal text-dnd-text-muted">d{a.die}</span> : null}
              </Button>
            ))}
            {many && (
              <Button variant="primary" disabled={pending || chosen.length === 0} onClick={() => onPickMany?.(chosen)}>
                {t('character.turn.ally_confirm', { n: chosen.length })}
              </Button>
            )}
            <Button variant="ghost" className="justify-start break-words text-left" disabled={pending} onClick={() => onPick(null)}>
              {t('character.turn.ally_other')}
            </Button>
          </>
        )}
      </div>
    </Sheet>
  )
}
