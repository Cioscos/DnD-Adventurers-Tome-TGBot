"""Character management ConversationHandler and state constants."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Conversation states
# ---------------------------------------------------------------------------
(
    CHAR_SELECT,
    CHAR_NEW_NAME,
    CHAR_MENU,
    CHAR_HP_MENU,
    CHAR_HP_SET,
    CHAR_HP_DAMAGE,
    CHAR_HP_HEAL,
    CHAR_AC_MENU,
    CHAR_AC_SET_BASE,
    CHAR_AC_SET_SHIELD,
    CHAR_AC_SET_MAGIC,
    CHAR_STATS_MENU,
    CHAR_STATS_SET,
    CHAR_SPELLS_MENU,
    CHAR_SPELL_LEARN,
    CHAR_SPELL_SLOTS_MENU,
    CHAR_SPELL_SLOT_ADD,
    CHAR_SPELL_SLOT_REMOVE,
    CHAR_BAG_MENU,
    CHAR_BAG_ADD_NAME,
    CHAR_BAG_ADD_WEIGHT,
    CHAR_BAG_ADD_QTY,
    CHAR_BAG_EDIT,
    CHAR_BAG_ADD_INLINE,
    CHAR_BAG_ADD_DAMAGE_DICE,
    CHAR_BAG_ADD_EFFECT,
    CHAR_BAG_ADD_AC_VALUE,
    CHAR_BAG_ADD_STR_REQ,
    CHAR_BAG_ADD_TOOL_TYPE,
    CHAR_CURRENCY_MENU,
    CHAR_CURRENCY_EDIT,
    CHAR_CURRENCY_CONVERT,
    CHAR_ABILITIES_MENU,
    CHAR_ABILITY_LEARN_NAME,
    CHAR_ABILITY_LEARN_DESC,
    CHAR_ABILITY_LEARN_USES,
    CHAR_MULTICLASS_MENU,
    CHAR_MULTICLASS_ADD,
    CHAR_MULTICLASS_ADD_LEVELS,
    CHAR_DICE_MENU,
    CHAR_NOTES_MENU,
    CHAR_NOTE_NEW_TITLE,
    CHAR_NOTE_NEW_BODY,
    CHAR_NOTE_EDIT,
    CHAR_VOICE_NOTE_TITLE,
    CHAR_MAPS_MENU,
    CHAR_MAP_NEW_ZONE,
    CHAR_MAP_ADD_FILE,
    CHAR_SETTINGS_MENU,
    CHAR_DELETE_CONFIRM,
    # Spell enhancement states
    CHAR_SPELL_EDIT,
    CHAR_CONC_SAVE,
    # Spell search
    CHAR_SPELL_SEARCH,
    # Class subclass input
    CHAR_CLASS_SUBCLASS_INPUT,
    # Conditions
    CHAR_CONDITIONS_MENU,
    # History
    CHAR_HISTORY_MENU,
    # Skills
    CHAR_SKILLS_MENU,
    # Heroic Inspiration
    CHAR_INSPIRATION_MENU,
    # Identity (race / gender)
    CHAR_RACE_INPUT,
    CHAR_GENDER_INPUT,
    # Saving throws
    CHAR_SAVING_THROWS_MENU,
    # Experience points
    CHAR_XP_MENU,
    CHAR_XP_ADD,
    # Death saving throws
    CHAR_DEATH_SAVES_MENU,
    # Temporary hit points
    CHAR_HP_TEMP_HP,
    # Short rest hit dice
    CHAR_HP_HIT_DICE,
    # Movement speed
    CHAR_SPEED_INPUT,
    # Extended identity: background / personality / languages / proficiencies
    CHAR_BACKGROUND_INPUT,
    CHAR_PERSONALITY_INPUT,
    CHAR_LANGUAGE_ADD,
    CHAR_PROFICIENCY_ADD,
    # Hit Die per class
    CHAR_HIT_DIE_INPUT,
    # Rename character
    CHAR_NAME_INPUT,
) = range(73)

STOPPING = 99
