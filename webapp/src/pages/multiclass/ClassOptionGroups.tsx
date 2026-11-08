import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { classLabel } from '@/lib/classLabel'
import { Replace } from 'lucide-react'
import { api } from '@/api/client'
import Button from '@/components/ui/Button'
import { ReplaceOptionSheet } from '@/components/rules/ClassOptionSheet'
import { LEDGER_LABEL } from '@/styles/ledger'
import type { CharacterClass, CharacterFull } from '@/types'

/** Le opzioni scelte di ogni gruppo sostituibile della classe (manovre, armi di Padronanza...), con il pulsante per cambiarne
 *  una. Il catalogo decide quali gruppi si possono sostituire e quali si elencano soltanto (nemici e terreni del Ranger): gli
 *  altri non compaiono (R20). */
export default function ClassOptionGroups({ char, cls }: { char: CharacterFull; cls: CharacterClass }) {
  const groups = Object.entries(cls.options ?? {}).filter(([, keys]) => keys.length > 0).map(([group]) => group)
  return <>{groups.map((group) => <Group key={group} char={char} cls={cls} group={group} />)}</>
}

function Group({ char, cls, group }: { char: CharacterFull; cls: CharacterClass; group: string }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const [open, setOpen] = useState(false)
  const state = useQuery({
    queryKey: ['class-options', char.id, cls.id, group],
    queryFn: () => api.choices.classOptions(char.id, cls.id, group),
    retry: false,  // un gruppo che il catalogo non conosce risponde 404: non è sostituibile e basta
  })
  if (!state.data?.replaceable && !state.data?.listed) return null
  return (
    <div data-testid={`option-group-${group}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-dnd-border/60 py-2 pl-1">
      <div className="min-w-0 flex-1">
        <p className={LEDGER_LABEL}>
          {t(`character.level_choice.groups.${group}`, { defaultValue: group })} · {classLabel(t, cls.class_name)}
        </p>
        <p className="text-sm font-body text-dnd-text">{state.data.chosen.map((o) => o.name[lang]).join(', ')}</p>
      </div>
      {state.data.replaceable && (
        <>
          <Button size="sm" variant="secondary" icon={<Replace size={14} />} onClick={() => setOpen(true)}>
            {t('character.level_choice.replace_title')}
          </Button>
          <ReplaceOptionSheet char={char} classId={cls.id} group={group} open={open} onClose={() => setOpen(false)} />
        </>
      )}
    </div>
  )
}
