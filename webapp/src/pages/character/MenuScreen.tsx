import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import {
  BarChart3, User, CircleDot,
} from 'lucide-react'
import {
  GiHeartPlus, GiCheckedShield, GiShieldEchoes, GiSparkles, GiCutDiamond,
  GiArcheryTarget, GiLightningTrio, GiCrossedSwords, GiTwoCoins,
  GiScrollUnfurled, GiPolarStar, GiPerspectiveDiceSixFacesRandom,
  GiQuillInk, GiTreasureMap, GiOpenBook, GiPotionBall, GiCauldron,
  GiFist, GiKnapsack, GiNightSleep, GiHourglass, GiPawPrint,
} from 'react-icons/gi'
import type { ComponentType, SVGAttributes } from 'react'
import SectionDivider from '@/components/ui/SectionDivider'
import Reveal from '@/components/ui/Reveal'
import Pressable from '@/components/ui/Pressable'
import PendingChoicesBadge from '@/components/character/PendingChoicesBadge'
import RestSheet from '@/components/character/RestSheet'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'
import type { CharacterFull } from '@/types'

type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>

type MenuItem = {
  key: string
  icon: IconCmp
  tone?: 'gold' | 'crimson' | 'arcane' | 'cobalt' | 'emerald' | 'amber'
} & ({ path: string } | { action: 'rest' })

type MenuSection = {
  labelKey: string
  icon: IconCmp
  items: MenuItem[]
}

const MENU_SECTIONS: MenuSection[] = [
  {
    labelKey: 'character.menu.sections.combat',
    icon: GiCrossedSwords,
    items: [
      { key: 'hp',      icon: GiHeartPlus,     path: 'hp',      tone: 'crimson' },
      { key: 'ac',      icon: GiCheckedShield, path: 'ac',      tone: 'gold' },
      { key: 'saves',   icon: GiShieldEchoes,  path: 'saves',   tone: 'cobalt' },
      { key: 'turn',    icon: GiHourglass,     path: 'turn',    tone: 'amber' },
      { key: 'actions', icon: GiFist,          path: 'actions', tone: 'crimson' },
      { key: 'conditions', icon: CircleDot,     path: 'conditions', tone: 'crimson' },
      { key: 'rest',    icon: GiNightSleep,    action: 'rest',    tone: 'amber' },
    ],
  },
  {
    labelKey: 'character.menu.sections.magic',
    icon: GiSparkles,
    items: [
      { key: 'spells', icon: GiSparkles,  path: 'spells', tone: 'arcane' },
      { key: 'slots',  icon: GiCutDiamond, path: 'slots',  tone: 'arcane' },
    ],
  },
  {
    labelKey: 'character.menu.sections.skills',
    icon: GiArcheryTarget,
    items: [
      { key: 'stats',     icon: BarChart3,        path: 'stats',     tone: 'gold' },
      { key: 'skills',    icon: GiArcheryTarget,  path: 'skills',    tone: 'cobalt' },
      { key: 'abilities', icon: GiLightningTrio,  path: 'abilities', tone: 'amber' },
    ],
  },
  {
    labelKey: 'character.menu.sections.equipment',
    icon: GiTwoCoins,
    items: [
      { key: 'inventory', icon: GiKnapsack,      path: 'inventory', tone: 'gold' },
      { key: 'currency',  icon: GiTwoCoins,      path: 'currency',  tone: 'amber' },
    ],
  },
  {
    labelKey: 'character.menu.sections.character',
    icon: User,
    items: [
      { key: 'identity',   icon: User,            path: 'identity',   tone: 'gold' },
      { key: 'class',      icon: GiScrollUnfurled, path: 'class',     tone: 'gold' },
      { key: 'xp',         icon: GiPolarStar,     path: 'xp',         tone: 'amber' },
      { key: 'extras',     icon: GiPawPrint,      path: 'extras',     tone: 'emerald' },
    ],
  },
  {
    labelKey: 'character.menu.sections.tools',
    icon: GiPotionBall,
    items: [
      { key: 'dice',     icon: GiPerspectiveDiceSixFacesRandom, path: 'dice',     tone: 'gold' },
      { key: 'notes',    icon: GiQuillInk,                      path: 'notes',    tone: 'emerald' },
      { key: 'maps',     icon: GiTreasureMap,                   path: 'maps',     tone: 'cobalt' },
      { key: 'history',  icon: GiOpenBook,                      path: 'history',  tone: 'amber' },
      { key: 'homebrew', icon: GiCauldron,                    path: 'homebrew', tone: 'arcane' },
    ],
  },
]

function toneIconClass(tone?: MenuItem['tone']): string {
  switch (tone) {
    case 'crimson': return 'text-dnd-crimson-bright'
    case 'arcane': return 'text-dnd-arcane-bright'
    case 'cobalt': return 'text-dnd-cobalt-bright'
    case 'emerald': return 'text-dnd-emerald-bright'
    case 'amber': return 'text-dnd-amber'
    case 'gold':
    default: return 'text-dnd-gold-bright'
  }
}

interface Props {
  char: CharacterFull
}

export default function MenuScreen({ char }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [restOpen, setRestOpen] = useState(false)

  return (
    <div className="p-4 space-y-4 pb-safe">
      <PendingChoicesBadge char={char} />
      {MENU_SECTIONS.map((section, sIdx) => {
        const SectionIcon = section.icon
        return (
          <m.div
            key={section.labelKey}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...spring.drift, delay: 0.05 + sIdx * 0.06 }}
          >
            <SectionDivider icon={<SectionIcon size={11} />} align="center">
              {t(section.labelKey)}
            </SectionDivider>
            <Reveal.Stagger stagger={stagger.listTight} delay={0} className="grid grid-cols-3 gap-2">
              {section.items
                .filter((item) => !('action' in item) || !char.is_dead)
                .map((item) => {
                const Icon = item.icon
                return (
                  <Reveal.Item key={item.key}>
                    <Pressable
                      onClick={() => {
                        haptic.light()
                        if ('action' in item) setRestOpen(true)
                        else navigate(`/char/${char.id}/${item.path}`)
                      }}
                      className="w-full flex flex-col items-center gap-1.5 px-2 py-3 rounded-2xl
                                 bg-dnd-surface border border-dnd-border
                                 hover:border-dnd-gold/60 hover:shadow-halo-gold
                                 transition-[box-shadow,border-color] duration-200"
                      whileTap={{ scale: 0.93 }}
                    >
                      <Icon size={22} strokeWidth={2} className={toneIconClass(item.tone)} />
                      <span className="text-xs text-dnd-text-muted font-body text-center leading-tight">
                        {t(`character.menu.${item.key}`)}
                      </span>
                    </Pressable>
                  </Reveal.Item>
                )
              })}
            </Reveal.Stagger>
          </m.div>
        )
      })}
      <RestSheet char={char} open={restOpen} onClose={() => setRestOpen(false)} />
    </div>
  )
}
