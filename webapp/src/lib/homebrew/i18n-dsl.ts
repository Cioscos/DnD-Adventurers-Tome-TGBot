/**
 * Plain-language labels for the homebrew DSL.
 *
 * `eventLabel()` converts a trigger event (plus its filters) into the
 * human-readable string shown in the editor and rule cards.
 * `actionLabel()` does the same for a single effect.
 *
 * The labels are tuned for the Italian/English audience of the Mini App;
 * keys outside `it` fall back to `en`, and unknown actions/events fall
 * back to the raw discriminator string.
 */

import type { Effect, EventType, Filter } from "./types"

export type Locale = "it" | "en"

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

type AttackVariant = "fumble" | "critical" | "default"
type DamageVariant = "was_crit_hit" | "default"

const attackVariant = (filters: Filter[]): AttackVariant => {
  for (const f of filters) {
    if (f.op !== "eq") continue
    if (f.path === "$event.is_fumble" && f.value === true) return "fumble"
    if (f.path === "$event.is_critical" && f.value === true) return "critical"
  }
  return "default"
}

const damageVariant = (filters: Filter[]): DamageVariant => {
  for (const f of filters) {
    if (
      f.op === "eq" &&
      f.path === "$event.was_critical_hit" &&
      f.value === true
    ) {
      return "was_crit_hit"
    }
  }
  return "default"
}

const EVENT_LABELS_IT: Record<EventType, string> = {
  attack_rolled: "🎲 Quando faccio un tiro per colpire",
  damage_taken: "💢 Quando subisco danno",
  dropped_to_zero: "☠️ Quando vengo portato a 0 PF in un colpo",
  hp_healed: "❤️ Quando vengo curato",
  long_rest_taken: "🌙 Quando faccio un riposo lungo",
  short_rest_taken: "☕ Quando faccio un riposo breve",
  spell_cast: "✨ Quando lancio un incantesimo",
  ability_used: "🌀 Quando uso un'abilità speciale",
  item_equipped: "🎽 Quando equipaggio un oggetto",
  item_unequipped: "🧺 Quando rimuovo un oggetto",
  level_up: "⭐ Quando salgo di livello",
  resource_changed: "🔄 Quando una risorsa cambia",
  resource_depleted: "🪫 Quando una risorsa è esaurita",
  turn_started: "🕐 All'inizio del mio turno",
  manual_trigger: "🖐️ Quando attivo manualmente la regola",
}

const EVENT_LABELS_EN: Record<EventType, string> = {
  attack_rolled: "🎲 When I make an attack roll",
  damage_taken: "💢 When I take damage",
  dropped_to_zero: "☠️ When I'm dropped to 0 HP in one hit",
  hp_healed: "❤️ When I get healed",
  long_rest_taken: "🌙 When I take a long rest",
  short_rest_taken: "☕ When I take a short rest",
  spell_cast: "✨ When I cast a spell",
  ability_used: "🌀 When I use a special ability",
  item_equipped: "🎽 When I equip an item",
  item_unequipped: "🧺 When I unequip an item",
  level_up: "⭐ When I level up",
  resource_changed: "🔄 When a resource changes",
  resource_depleted: "🪫 When a resource is depleted",
  turn_started: "🕐 At the start of my turn",
  manual_trigger: "🖐️ When I manually trigger the rule",
}

export function eventLabel(
  event: EventType,
  filters: Filter[],
  locale: Locale,
): string {
  const isIt = locale === "it"

  if (event === "attack_rolled") {
    const variant = attackVariant(filters)
    if (variant === "fumble") {
      return isIt
        ? "🎲 Quando tiro 1 (fallimento critico) attaccando"
        : "🎲 When I roll a 1 (critical miss) on attack"
    }
    if (variant === "critical") {
      return isIt
        ? "✨ Quando tiro 20 (critico) attaccando"
        : "✨ When I roll a 20 (critical) on attack"
    }
  }

  if (event === "damage_taken") {
    const variant = damageVariant(filters)
    if (variant === "was_crit_hit") {
      return isIt
        ? "💥 Quando subisco un colpo critico"
        : "💥 When I take a critical hit"
    }
  }

  const table = isIt ? EVENT_LABELS_IT : EVENT_LABELS_EN
  return table[event] ?? String(event)
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

const subjectWord = (target: "subject" | "character", locale: Locale): string => {
  if (locale === "it") {
    return target === "subject" ? "questo oggetto" : "il personaggio"
  }
  return target === "subject" ? "this item" : "the character"
}

const signOf = (delta: number | string): string => {
  return typeof delta === "number" && delta >= 0 ? "+" : ""
}

export function actionLabel(effect: Effect, locale: Locale): string {
  const isIt = locale === "it"

  switch (effect.action) {
    case "roll_dice":
      return isIt
        ? `🎲 Tira ${effect.notation}, chiamiamolo "${effect.store_as}"`
        : `🎲 Roll ${effect.notation}, call it "${effect.store_as}"`

    case "lookup_table":
      return isIt
        ? `📊 Guarda nella tabella "${effect.table}", riga "${effect.row}" colonna "${effect.col}", chiamiamolo "${effect.store_as}"`
        : `📊 Look up table "${effect.table}", row "${effect.row}" column "${effect.col}", call it "${effect.store_as}"`

    case "match":
      return isIt
        ? `🔀 In base al risultato di "${effect.value}"...`
        : `🔀 Based on the result of "${effect.value}"...`

    case "if":
      return isIt
        ? "🤔 Se la condizione è vera..."
        : "🤔 If the condition is true..."

    case "set_property":
      return isIt
        ? `📝 Imposta "${effect.key}" di ${subjectWord(effect.target, "it")} a "${String(effect.value)}"`
        : `📝 Set "${effect.key}" of ${subjectWord(effect.target, "en")} to "${String(effect.value)}"`

    case "inc_property":
      return isIt
        ? `➕ Incrementa "${effect.key}" di ${effect.delta}`
        : `➕ Increment "${effect.key}" by ${effect.delta}`

    case "unequip":
      return isIt ? "🧺 Rimuovi dall'equipaggiamento" : "🧺 Remove from equipment"

    case "damage_character":
      return isIt
        ? `💢 Subisci ${effect.amount} danni`
        : `💢 Take ${effect.amount} damage`

    case "heal_character":
      return isIt
        ? `❤️ Curati di ${effect.amount} PF`
        : `❤️ Heal ${effect.amount} HP`

    case "change_resource":
      return isIt
        ? `🔄 Modifica "${effect.key}" di ${effect.delta}`
        : `🔄 Change "${effect.key}" by ${effect.delta}`

    case "restore_resource":
      return isIt
        ? `♻️ Ripristina "${effect.key}" a ${effect.amount}`
        : `♻️ Restore "${effect.key}" to ${effect.amount}`

    case "apply_condition":
      return isIt
        ? `🔸 Applica condizione "${effect.key}"`
        : `🔸 Apply condition "${effect.key}"`

    case "remove_condition":
      return isIt
        ? `🔹 Rimuovi condizione "${effect.key}"`
        : `🔹 Remove condition "${effect.key}"`

    case "apply_modifier_once": {
      const sign = signOf(effect.delta)
      return isIt
        ? `⭐ ${effect.label} (${effect.target} ${sign}${effect.delta})`
        : `⭐ ${effect.label} (${effect.target} ${sign}${effect.delta})`
    }

    case "notify":
      return isIt
        ? `💬 Mostra messaggio: "${effect.message}"`
        : `💬 Show message: "${effect.message}"`

    case "add_history":
      return isIt
        ? `📜 Annota nello storico: "${effect.description}"`
        : `📜 Note in history: "${effect.description}"`

    default: {
      // Exhaustiveness check — every Effect variant must be handled above.
      const _exhaustive: never = effect
      return (_exhaustive as Effect).action
    }
  }
}
