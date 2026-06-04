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
  GiFist, GiKnapsack,
} from 'react-icons/gi'
import type { ComponentType, SVGAttributes } from 'react'
import SectionDivider from '@/components/ui/SectionDivider'
import Reveal from '@/components/ui/Reveal'
import { haptic } from '@/auth/telegram'
import { spring, stagger } from '@/styles/motion'

type IconCmp = ComponentType<SVGAttributes<SVGElement> & { size?: number | string }>

type MenuItem = {
  key: string
  icon: IconCmp
  path: string
  tone?: 'gold' | 'crimson' | 'arcane' | 'cobalt' | 'emerald' | 'amber'
}

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
      { key: 'actions', icon: GiFist,          path: 'actions', tone: 'crimson' },
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
      { key: 'conditions', icon: CircleDot,       path: 'conditions', tone: 'crimson' },
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
    case 'crimson': return 'text-[var(--dnd-crimson-bright)]'
    case 'arcane': return 'text-dnd-arcane-bright'
    case 'cobalt': return 'text-[var(--dnd-cobalt-bright)]'
    case 'emerald': return 'text-[var(--dnd-emerald-bright)]'
    case 'amber': return 'text-[var(--dnd-amber)]'
    case 'gold':
    default: return 'text-dnd-gold-bright'
  }
}

interface Props {
  charId: number
}

export default function MenuScreen({ charId }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  return (
    <div className="p-4 space-y-4 pb-safe">
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
              {section.items.map((item) => {
                const Icon = item.icon
                return (
                  <Reveal.Item key={item.key}>
                    <m.button
                      onClick={() => {
                        haptic.light()
                        navigate(`/char/${charId}/${item.path}`)
                      }}
                      className="w-full flex flex-col items-center gap-1.5 px-2 py-3 rounded-2xl
                                 bg-dnd-surface border border-dnd-border
                                 hover:border-dnd-gold/60 hover:shadow-halo-gold
                                 transition-[box-shadow,border-color] duration-200"
                      whileTap={{ scale: 0.93 }}
                    >
                      <Icon size={22} strokeWidth={2} className={toneIconClass(item.tone)} />
                      <span className="text-[11px] text-dnd-text-muted font-body text-center leading-tight">
                        {t(`character.menu.${item.key}`)}
                      </span>
                    </m.button>
                  </Reveal.Item>
                )
              })}
            </Reveal.Stagger>
          </m.div>
        )
      })}
    </div>
  )
}
