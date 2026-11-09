import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Input from '@/components/ui/Input'
import SelectSheet from '@/components/ui/SelectSheet'

const OTHER = '__other__'

interface Props {
  edition: string
  /** Nome o chiave della classe; senza catalogo (classe custom) resta il testo libero. */
  className: string | null
  value: string
  onChange: (text: string) => void
  zClassName?: string
}

/** Sottoclasse: catalogo dell'edizione + «Altro (testo libero)». Un testo non riconosciuto resta visibile. */
export default function SubclassSelect({ edition, className, value, onChange, zClassName }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('en') ? 'en' : 'it'
  const [otherPicked, setOtherPicked] = useState(false)
  const { data: catalog = [] } = useQuery({
    queryKey: ['rules', 'subclasses', edition, className],
    queryFn: () => api.rules.subclasses(edition, className as string),
    enabled: className !== null,
    staleTime: Infinity,
  })

  const nameOf = (s: (typeof catalog)[number]) => s.name[lang] ?? s.name.it
  const norm = (x: string) => x.trim().toLowerCase()
  const hit = catalog.find((s) => Object.values(s.name).some((n) => norm(n) === norm(value)))
  const selected = hit ? hit.key : otherPicked || value.trim() ? OTHER : ''
  const placeholder = t('character.multiclass.subclass')

  if (catalog.length === 0) return <Input value={value} onChange={onChange} placeholder={placeholder} />
  return (
    <div className="space-y-2">
      <SelectSheet
        title={placeholder}
        options={[
          ...catalog.map((s) => ({ value: s.key, label: nameOf(s) })),
          { value: OTHER, label: t('character.multiclass.subclass_other') },
        ]}
        value={selected}
        onChange={(k) => {
          const picked = catalog.find((s) => s.key === k)
          setOtherPicked(!picked)
          onChange(picked ? nameOf(picked) : '') // «Altro» svuota: il testo libero parte pulito
        }}
        placeholder={placeholder}
        zClassName={zClassName}
      />
      {selected === OTHER && (
        <>
          <Input value={value} onChange={onChange} placeholder={placeholder} />
          <p className="text-xs text-dnd-text-muted font-body">{t('character.multiclass.subclass_other_hint')}</p>
        </>
      )}
    </div>
  )
}
