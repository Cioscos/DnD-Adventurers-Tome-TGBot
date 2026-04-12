import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

export default function ArmorClass() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [base, setBase] = useState('')
  const [shield, setShield] = useState('')
  const [magic, setMagic] = useState('')

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const mutation = useMutation({
    mutationFn: () =>
      api.characters.updateAC(charId, {
        base: base !== '' ? Number(base) : undefined,
        shield: shield !== '' ? Number(shield) : undefined,
        magic: magic !== '' ? Number(magic) : undefined,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setBase('')
      setShield('')
      setMagic('')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const fields = [
    { key: 'base',   label: t('character.ac.base'),   val: base,   set: setBase,   cur: char.base_armor_class },
    { key: 'shield', label: t('character.ac.shield'), val: shield, set: setShield, cur: char.shield_armor_class },
    { key: 'magic',  label: t('character.ac.magic'),  val: magic,  set: setMagic,  cur: char.magic_armor },
  ]

  return (
    <Layout title={t('character.ac.title')} backTo={`/char/${charId}`}>
      <Card>
        <div className="text-center">
          <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">{t('character.ac.total')}</p>
          <p className="text-6xl font-bold">🛡️ {char.ac}</p>
          <p className="text-sm text-[var(--tg-theme-hint-color)] mt-2">
            {char.base_armor_class} + {char.shield_armor_class} + {char.magic_armor}
          </p>
        </div>
      </Card>

      {fields.map((f) => (
        <Card key={f.key}>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{f.label}</p>
              <p className="text-2xl font-bold mt-1">{f.cur}</p>
            </div>
            <input
              type="number"
              min="0"
              value={f.val}
              onChange={(e) => f.set(e.target.value)}
              placeholder={String(f.cur)}
              className="w-24 bg-white/10 rounded-xl px-3 py-2 text-xl font-bold text-center
                         outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
          </div>
        </Card>
      ))}

      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending || (base === '' && shield === '' && magic === '')}
        className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                   text-[var(--tg-theme-button-text-color)] font-semibold
                   disabled:opacity-40 active:opacity-80"
      >
        {mutation.isPending ? '...' : t('common.save')}
      </button>
    </Layout>
  )
}
