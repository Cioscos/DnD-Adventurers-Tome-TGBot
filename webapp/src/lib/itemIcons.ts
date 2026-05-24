import type { IconType } from 'react-icons'
import {
  GiCrossedSwords,
  GiBreastplate,
  GiCheckedShield,
  GiPotionBall,
  GiWrench,
  GiCutDiamond,
  GiKnapsack,
  GiScrollUnfurled,
  GiSwapBag,
} from 'react-icons/gi'

const ICONS: Record<string, IconType> = {
  weapon: GiCrossedSwords,
  armor: GiBreastplate,
  shield: GiCheckedShield,
  consumable: GiPotionBall,
  tool: GiWrench,
  accessory: GiCutDiamond,
  gear: GiKnapsack,
  potion: GiPotionBall,
  scroll: GiScrollUnfurled,
  generic: GiSwapBag,
}

export function getItemTypeIcon(type: string | undefined | null): IconType {
  if (!type) return GiSwapBag
  return ICONS[type] ?? GiSwapBag
}
