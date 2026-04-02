CATEGORY_TO_QUERY_MAP = {
    'monsters': """query Monster($index: String) {
  monster(index: $index) {
    name
    alignment
    challenge_rating
    charisma
    constitution
    damage_immunities
    damage_resistances
    damage_vulnerabilities
    desc
    dexterity
    hit_dice
    hit_points
    hit_points_roll
    image
    index
    intelligence
    languages
    proficiency_bonus
    size
    speed {
      burrow
      climb
      fly
      hover
      swim
      walk
    }
    strength
    subtype
    type
    wisdom
    xp
    actions {
      name
      desc
      dc {
        type {
          name
          full_name
          desc
          skills {
            name
            desc
          }
        }
        value
        success
      }
      damage {
        type
        dc {
          type {
            name
            full_name
            desc
          }
          value
          success
        }
        damage_type {
          name
          desc
        }
        damage_dice
        choose
      }
      attacks {
        name
        dc {
          type {
            name
            full_name
            desc
          }
          value
          success
        }
      }
      attack_bonus
      options {
        type
        choose
      }
      multiattack_type
      actions {
        type
        action_name
        count
      }
      usage {
        dice
        min_value
        rest_types
        times
        type
      }
      action_options {
        choose
        type
        from {
          option_set_type
          options {
            ... on ActionOption {
              action_name
              count
              option_type
              type
            }
            ... on MultipleActionOption {
              items {
                action_name
                count
                option_type
                type
              }
              option_type
            }
          }
        }
      }
    }
    armor_class {
      value
      desc
      condition {
        name
        desc
      }
      armor {
        name
        desc
        armor_class {
          max_bonus
          dex_bonus
          base
        }
        stealth_disadvantage
        str_minimum
        weight
        armor_category {
          name
        }
      }
      spell {
        name
      }
    }
    condition_immunities {
      name
      desc
    }
    legendary_actions {
      name
      desc
      dc {
        value
        success
        type {
          name
          full_name
          desc
          skills {
            name
            desc
            ability_score {
              full_name
              desc
              name
            }
          }
        }
      }
      damage {
        damage_type {
          name
          desc
        }
        damage_dice
      }
    }
    special_abilities {
      name
      desc
      usage {
        dice
        min_value
        times
        rest_types
        type
      }
      dc {
        value
        success
        type {
          full_name
          desc
        }
      }
      damage {
        damage_dice
        damage_type {
          name
          desc
        }
      }
    }
    reactions {
      name
      desc
      dc {
        success
        value
        type {
          full_name
          desc
        }
      }
    }
    senses {
      blindsight
      darkvision
      passive_perception
      tremorsense
      truesight
    }
    proficiencies {
      value
      proficiency {
        name
      }
    }
    forms {
      name
      type
      alignment
      image
    }
  }
}""",
    "proficiencies": """query Proficiency($index: String) {
  proficiency(index: $index) {
    name
    classes {
      name
    }
    races {
      name
      ... on Race {
        subraces {
          name
        }
      }
    }
    reference {
      ... on EquipmentCategory {
        name
      }
      ... on Skill {
        name
      }
      ... on AbilityScore {
        name
      }
      ... on Tool {
        name
      }
      ... on Armor {
        name
      }
      ... on Weapon {
        name
      }
      ... on Vehicle {
        name
      }
      ... on Gear {
        name
      }
      ... on Pack {
        name
      }
      ... on Ammunition {
        name
      }
    }
    type
  }
}""",
    "races": """query Race($index: String) {
  race(index: $index) {
    name
    size_description
    speed
    alignment
    age
    language_desc
    languages {
      name
      typical_speakers
    }
    ability_bonuses {
      bonus
      ability_score {
        full_name
        skills {
          name
        }
      }
    }
    starting_proficiencies {
      name
    }
    starting_proficiency_options {
      choose
      desc
    }
    traits {
      name
      desc
    }
    subraces {
      name
      desc
      ability_bonuses {
        bonus
        ability_score {
          full_name
        }
      }
      racial_traits {
        name
        desc
      }
      starting_proficiencies {
        name
      }
    }
  }
}""",
    "rule-sections": """query RuleSection($index: String) {
  ruleSection(index: $index) {
    name
    desc
  }
}""",
    "rules": """query Rule($index: String) {
  rule(index: $index) {
    name
    desc
    subsections {
      name
      desc
    }
  }
}""",
    "skills": """query Skill($index: String) {
  skill(index: $index) {
    name
    desc
    ability_score {
      full_name
      desc
    }
  }
}""",
    "spells": """query Spell($index: String) {
  spell(index: $index) {
    name
    desc
    components
    concentration
    damage {
      damage_at_character_level {
        level
        damage
      }
      damage_at_slot_level {
        level
        damage
      }
      damage_type {
        name
      }
    }
    casting_time
    area_of_effect {
      size
      type
    }
    ritual
    duration
    attack_type
    dc {
      desc
      success
      type {
        full_name
      }
    }
    heal_at_slot_level {
      level
      healing
    }
    higher_level
    level
    range
    school {
      name
    }
    classes {
      name
    }
    subclasses {
      name
      class {
        name
      }
    }
    material
  }
}""",
    "weapon-properties": """query WeaponProperty($index: String) {
  weaponProperty(index: $index) {
    name
    desc
  }
}""",
    "languages": """query Language($index: String) {
  language(index: $index) {
    name
    desc
    script
    type
    typical_speakers
  }
}""",
    "classes": """query Class($index: String) {
  class(index: $index) {
    index
    name
    hit_die
    saving_throws {
      full_name
    }
    proficiencies {
      name
    }
    proficiency_choices {
      desc
    }
    starting_equipment {
      equipment {
        name
        }
      }
    starting_equipment_options {
      desc
    }
    multi_classing {
      prerequisites {
        minimum_score
        ability_score {
          full_name
        }
      }
      proficiencies {
        name
      }
      proficiency_choices {
        desc
      }
    }
    subclasses {
      name
      desc
      subclass_flavor
    }
    spellcasting {
      level
      spellcasting_ability {
        full_name
      }
      info {
        name
        desc
      }
    }
  }
}"""
}
