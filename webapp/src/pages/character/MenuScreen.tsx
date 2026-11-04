import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import {
  BarChart3, User, CircleDot,
} from 'lucide-react'
import {
  GiHeartPlus, GiCheckedShield, GiShieldEchoes, GiSparkles, GiCutDiamond,
  GiArcheryTarget, GiLightningTrio, GiTwoCoins,
  GiScrollUnfurled, GiPolarStar, GiPerspectiveDiceSixFacesRandom,
  GiQuillInk, GiTreasureMap, GiOpenBook, GiCauldron,
  GiFist, GiKnapsack, GiNightSleep, GiHourglass, GiPawPrint,
} from 'react-icons/gi'
import type { ComponentType, SVGAttributes } from 'react'
import Pressable from '@/components/ui/Pressable'
import PendingChoicesBadge from '@/components/character/PendingChoicesBadge'
import RestSheet from '@/components/character/RestSheet'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import { LEDGER_INDEX_ROW, LEDGER_TITLE } from '@/styles/ledger'
import type { CharacterFull } from '@/types'

type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>

type MenuItem = {
  key: string
  icon: IconCmp
} & ({ path: string } | { action: 'rest' })

type MenuSection = {
  labelKey: string
  items: MenuItem[]
}

const MENU_SECTIONS: MenuSection[] = [
  {
    labelKey: 'character.menu.sections.combat',
    items: [
      { key: 'hp',      icon: GiHeartPlus,     path: 'hp' },
      { key: 'ac',      icon: GiCheckedShield, path: 'ac' },
      { key: 'saves',   icon: GiShieldEchoes,  path: 'saves' },
      { key: 'turn',    icon: GiHourglass,     path: 'turn' },
      { key: 'actions', icon: GiFist,          path: 'actions' },
      { key: 'conditions', icon: CircleDot,     path: 'conditions' },
      { key: 'rest',    icon: GiNightSleep,    action: 'rest' },
    ],
  },
  {
    labelKey: 'character.menu.sections.magic',
    items: [
      { key: 'spells', icon: GiSparkles,  path: 'spells' },
      { key: 'slots',  icon: GiCutDiamond, path: 'slots' },
    ],
  },
  {
    labelKey: 'character.menu.sections.skills',
    items: [
      { key: 'stats',     icon: BarChart3,        path: 'stats' },
      { key: 'skills',    icon: GiArcheryTarget,  path: 'skills' },
      { key: 'abilities', icon: GiLightningTrio,  path: 'abilities' },
    ],
  },
  {
    labelKey: 'character.menu.sections.equipment',
    items: [
      { key: 'inventory', icon: GiKnapsack,      path: 'inventory' },
      { key: 'currency',  icon: GiTwoCoins,      path: 'currency' },
    ],
  },
  {
    labelKey: 'character.menu.sections.character',
    items: [
      { key: 'identity',   icon: User,            path: 'identity' },
      { key: 'class',      icon: GiScrollUnfurled, path: 'class' },
      { key: 'xp',         icon: GiPolarStar,     path: 'xp' },
      { key: 'extras',     icon: GiPawPrint,      path: 'extras' },
    ],
  },
  {
    labelKey: 'character.menu.sections.tools',
    items: [
      { key: 'dice',     icon: GiPerspectiveDiceSixFacesRandom, path: 'dice' },
      { key: 'notes',    icon: GiQuillInk,                      path: 'notes' },
      { key: 'maps',     icon: GiTreasureMap,                   path: 'maps' },
      { key: 'history',  icon: GiOpenBook,                      path: 'history' },
      { key: 'homebrew', icon: GiCauldron,                    path: 'homebrew' },
    ],
  },
]

interface Props {
  char: CharacterFull
}

export default function MenuScreen({ char }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [restOpen, setRestOpen] = useState(false)

  return (
    <div className="p-4 space-y-5 pb-safe">
      <PendingChoicesBadge char={char} />
      {MENU_SECTIONS.map((section, sIdx) => (
        <m.div
          key={section.labelKey}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring.drift, delay: 0.05 + sIdx * 0.06 }}
        >
          <h2 className={`px-1 pb-1.5 ${LEDGER_TITLE}`}>
            {t(section.labelKey)}
          </h2>
          {/* Indice del codice: righe a filetto a due colonne, non tessere. */}
          <ul className="grid grid-cols-2 gap-x-4 border-t border-dnd-border">
            {section.items
              .filter((item) => !('action' in item) || !char.is_dead)
              .map((item) => {
                const Icon = item.icon
                return (
                  <li key={item.key} className="min-w-0 border-b border-dnd-border/60">
                    <Pressable
                      onClick={() => {
                        haptic.light()
                        if ('action' in item) setRestOpen(true)
                        else navigate(`/char/${char.id}/${item.path}`)
                      }}
                      className={`${LEDGER_INDEX_ROW} text-dnd-text hover:text-dnd-gold-bright transition-colors`}
                      whileTap={{ scale: 0.97 }}
                    >
                      <Icon size={20} strokeWidth={2} aria-hidden className="shrink-0 text-dnd-gold" />
                      <span className="min-w-0 break-words font-body text-sm leading-tight">
                        {t(`character.menu.${item.key}`)}
                      </span>
                    </Pressable>
                  </li>
                )
              })}
          </ul>
        </m.div>
      ))}
      <RestSheet char={char} open={restOpen} onClose={() => setRestOpen(false)} />
    </div>
  )
}
