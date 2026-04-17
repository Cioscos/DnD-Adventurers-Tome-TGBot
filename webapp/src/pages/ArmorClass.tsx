import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { Save } from 'lucide-react'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { ShieldEmblem } from '@/components/ui/Ornament'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { useReducedMotion } from '@/hooks/useReducedMotion'

export default function ArmorClass() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const reduceMotion = useReducedMotion()

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
    <Layout title={t('character.ac.title')} backTo={`/char/${charId}`} group="combat" page="ac">
      {/* Hero AC */}
      <Surface variant="tome" ornamented className="relative overflow-hidden">
        <div className="flex flex-col items-center py-4">
          <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim mb-2">
            {t('character.ac.total')}
          </p>

          <div className="relative flex items-center justify-center">
            <m.div
              animate={reduceMotion ? {} : { rotate: [-2, 2, -1, 1, 0] }}
              transition={reduceMotion ? undefined : { duration: 6, repeat: Infinity, ease: 'easeInOut' }}
              className="drop-shadow-[0_8px_24px_var(--dnd-gold-glow)]"
            >
              <ShieldEmblem size={200} />
            </m.div>
            <m.span
              key={char.ac}
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: [0.6, 1.15, 1], opacity: 1 }}
              transition={spring.elastic}
              className="absolute font-display font-black text-dnd-gold-bright leading-none"
              style={{
                fontSize: '4rem',
                textShadow: '0 2px 8px var(--dnd-gold-glow), 0 0 2px rgba(0,0,0,0.6)',
              }}
            >
              {char.ac}
            </m.span>
          </div>

          <p className="text-sm text-dnd-text-muted font-mono mt-3">
            {char.base_armor_class} + {char.shield_armor_class} + {char.magic_armor}
          </p>
          <p className="text-[10px] text-dnd-text-faint font-cinzel uppercase tracking-wider mt-0.5">
            base · shield · magic
          </p>
        </div>
      </Surface>

      {/* Component editors */}
      {fields.map((f, idx) => (
        <m.div
          key={f.key}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring.drift, delay: 0.1 + idx * 0.05 }}
        >
          <Surface variant="elevated">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-cinzel text-xs uppercase tracking-widest text-dnd-gold-dim">{f.label}</p>
                <p className="text-3xl font-display font-black text-dnd-gold-bright mt-0.5">{f.cur}</p>
              </div>
              <Input
                type="number"
                min={0}
                value={f.val}
                onChange={f.set}
                placeholder={String(f.cur)}
                inputMode="numeric"
                className="w-28 [&_input]:text-xl [&_input]:font-display [&_input]:font-bold [&_input]:text-center"
              />
            </div>
          </Surface>
        </m.div>
      ))}

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending || (base === '' && shield === '' && magic === '')}
        loading={mutation.isPending}
        icon={<Save size={18} />}
        haptic="success"
      >
        {t('common.save')}
      </Button>
    </Layout>
  )
}
