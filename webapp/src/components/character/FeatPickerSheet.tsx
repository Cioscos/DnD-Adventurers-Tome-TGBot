import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import FeatChoiceList from '@/components/character/FeatChoiceList'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { featsFor } from '@/lib/feats'
import { uiLang } from '@/lib/lang'
import type { CharacterFull } from '@/types'

interface Props {
  char: CharacterFull
  open: boolean
  onClose: () => void
}

/** «Aggiungi talento»: un talento fuori dalle scelte di livello (talento d'Origine, dono del GM, privilegio che lo concede).
 *  Il talento vale per intero: anche il suo +1 alla caratteristica. */
export default function FeatPickerSheet({ char, open, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [featKey, setFeatKey] = useState('')
  const [ability, setAbility] = useState('')
  const edition = char.rules_edition === '2024' ? '2024' : '2014'
  const items = featsFor(char, edition, 'manual', uiLang(i18n.language))
  const feat = items.find((f) => f.key === featKey)
  const score = (name: string) => char.ability_scores.find((s) => s.name === name)?.value ?? 10

  const mutation = useMutation({
    mutationFn: () => api.feats.take(char.id, { feat_key: featKey, ability: feat?.abilities ? ability : null }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      setFeatKey('')
      onClose()
    },
    onError: () => haptic.error(),
  })

  return (
    <Sheet open={open} onClose={onClose} title={t('character.feats.add_title')}>
      <div className="p-5 space-y-3">
        <p className="text-xs font-body text-dnd-text-muted">{t('character.feats.add_hint')}</p>
        <FeatChoiceList
          items={items}
          value={featKey}
          onPick={setFeatKey}
          taken={new Set((char.abilities ?? []).map((a) => a.feature_key))}
          ability={ability}
          onAbility={setAbility}
          score={score}
        />
        {mutation.isError && (
          <p className="text-xs font-body text-dnd-crimson-bright">{t('character.level_choice.error')}</p>
        )}
        <Pressable
          onClick={() => mutation.mutate()}
          disabled={!featKey || (!!feat?.abilities && !ability)}
          pending={mutation.isPending}
          className="w-full min-h-[44px] rounded-xl bg-dnd-gold/15 border border-dnd-gold text-sm font-body text-dnd-gold-bright disabled:opacity-40"
        >
          {t('character.feats.add_confirm')}
        </Pressable>
      </div>
    </Sheet>
  )
}
