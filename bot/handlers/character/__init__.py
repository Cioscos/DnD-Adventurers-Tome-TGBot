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
) = range(44)

STOPPING = 99
