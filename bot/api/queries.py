"""GraphQL query constants for the D&D 5e API.

All queries target https://www.dnd5eapi.co/graphql/2014.
List queries accept ``skip`` and ``limit`` variables for pagination.
Detail queries accept an ``index`` variable (the item's URL-friendly slug).
"""

# ---------------------------------------------------------------------------
# List queries — used to populate paginated inline-keyboard item lists.
# Each returns ``index`` and ``name`` (the minimum needed for buttons).
# ---------------------------------------------------------------------------

SPELLS_LIST = """
query SpellsList($skip: Int, $limit: Int) {
  spells(skip: $skip, limit: $limit) {
    index
    name
    level
  }
}
"""

MONSTERS_LIST = """
query MonstersList($skip: Int, $limit: Int) {
  monsters(skip: $skip, limit: $limit) {
    index
    name
    type
    challenge_rating
  }
}
"""

CLASSES_LIST = """
query ClassesList {
  classes {
    index
    name
    hit_die
  }
}
"""

RACES_LIST = """
query RacesList {
  races {
    index
    name
    size
  }
}
"""

EQUIPMENT_LIST = """
query EquipmentList($skip: Int, $limit: Int) {
  equipments(skip: $skip, limit: $limit) {
    index
    name
  }
}
"""

CONDITIONS_LIST = """
query ConditionsList {
  conditions {
    index
    name
  }
}
"""

MAGIC_ITEMS_LIST = """
query MagicItemsList($skip: Int, $limit: Int) {
  magicItems(skip: $skip, limit: $limit) {
    index
    name
  }
}
"""

FEATS_LIST = """
query FeatsList {
  feats {
    index
    name
  }
}
"""

RULES_LIST = """
query RulesList {
  rules {
    index
    name
  }
}
"""

BACKGROUNDS_LIST = """
query BackgroundsList {
  backgrounds {
    index
    name
  }
}
"""

WEAPON_PROPERTIES_LIST = """
query WeaponPropertiesList {
  weaponProperties {
    index
    name
  }
}
"""

# ---------------------------------------------------------------------------
# Detail queries — used to display full information about a single item.
# ---------------------------------------------------------------------------

SPELL_DETAIL = """
query SpellDetail($index: String!) {
  spell(index: $index) {
    index
    name
    level
    school { name }
    casting_time
    range
    duration
    concentration
    ritual
    components
    material
    desc
    higher_level
    damage {
      damage_type { name }
      damage_at_slot_level { level value }
    }
    area_of_effect { type size }
    dc { dc_type { name } dc_success }
    classes { name }
    subclasses { name }
  }
}
"""

MONSTER_DETAIL = """
query MonsterDetail($index: String!) {
  monster(index: $index) {
    index
    name
    size
    type
    subtype
    alignment
    hit_points
    hit_dice
    hit_points_roll
    speed { walk swim fly burrow climb }
    armor_class {
      ... on ArmorClassDex { type value desc }
      ... on ArmorClassNatural { type value desc }
      ... on ArmorClassArmor { type value desc }
      ... on ArmorClassSpell { type value desc }
      ... on ArmorClassCondition { type value desc }
    }
    strength
    dexterity
    constitution
    intelligence
    wisdom
    charisma
    challenge_rating
    xp
    languages
    senses { passive_perception blindsight darkvision tremorsense truesight }
    damage_vulnerabilities
    damage_resistances
    damage_immunities
    condition_immunities { name }
    special_abilities { name desc }
    actions { name desc attack_bonus damage { ... on Damage { damage_type { name } damage_dice } } }
    legendary_actions { name desc }
    reactions { name desc }
  }
}
"""

CLASS_DETAIL = """
query ClassDetail($index: String!) {
  class(index: $index) {
    index
    name
    hit_die
    proficiencies { name }
    saving_throws { name }
    subclasses { name }
    spellcasting {
      level
      info { name desc }
      spellcasting_ability { name }
    }
  }
}
"""

RACE_DETAIL = """
query RaceDetail($index: String!) {
  race(index: $index) {
    index
    name
    speed
    size
    size_description
    alignment
    age
    languages { name }
    language_desc
    traits { name }
    subraces { name }
    ability_bonuses { bonus ability_score { name } }
  }
}
"""

EQUIPMENT_DETAIL = """
query EquipmentDetail($index: String!) {
  equipment(index: $index) {
    ... on Gear { index name equipment_category { name } cost { quantity unit } weight desc }
    ... on Weapon { index name equipment_category { name } cost { quantity unit } weight desc }
    ... on Armor { index name equipment_category { name } cost { quantity unit } weight desc }
    ... on Tool { index name equipment_category { name } cost { quantity unit } weight desc }
    ... on Pack { index name equipment_category { name } cost { quantity unit } weight desc }
    ... on Ammunition { index name equipment_category { name } cost { quantity unit } weight desc }
    ... on Vehicle { index name equipment_category { name } cost { quantity unit } weight desc }
  }
}
"""

CONDITION_DETAIL = """
query ConditionDetail($index: String!) {
  condition(index: $index) {
    index
    name
    desc
  }
}
"""

MAGIC_ITEM_DETAIL = """
query MagicItemDetail($index: String!) {
  magicItem(index: $index) {
    index
    name
    equipment_category { name }
    desc
    rarity { name }
  }
}
"""

FEAT_DETAIL = """
query FeatDetail($index: String!) {
  feat(index: $index) {
    index
    name
    desc
    prerequisites { ability_score { name } minimum_score }
  }
}
"""

RULE_DETAIL = """
query RuleDetail($index: String!) {
  rule(index: $index) {
    index
    name
    desc
  }
}
"""

BACKGROUND_DETAIL = """
query BackgroundDetail($index: String!) {
  background(index: $index) {
    index
    name
    starting_proficiencies { name }
    starting_equipment { equipment { name } quantity }
    feature { name desc }
  }
}
"""

WEAPON_PROPERTY_DETAIL = """
query WeaponPropertyDetail($index: String!) {
  weaponProperty(index: $index) {
    index
    name
    desc
  }
}
"""
