CHARACTER_CREATOR_VERSION = "3.3.0"

# states definition
(CHARACTER_CREATION,
 CHARACTER_SELECTION,
 NAME_SELECTION,
 RACE_SELECTION,
 GENDER_SELECTION,
 CLASS_SELECTION,
 HIT_POINTS_SELECTION,
 FUNCTION_SELECTION,
 BAG_MANAGEMENT,
 BAG_CURRENCY_INSERT,
 CHARACTER_DELETION,
 BAG_ITEM_INSERTION,
 BAG_ITEM_EDIT,
 BAG_ITEM_OVERWRITE,
 BAG_CURRENCY_FUNCTIONS,
 BAG_CURRENCY_CONVERT,
 FEATURE_POINTS_EDIT,
 ABILITIES_MENU,
 ABILITY_VISUALIZATION,
 ABILITY_ACTIONS,
 ABILITY_LEARN,
 SPELLS_MENU,
 SPELL_LEVEL_MENU,
 SPELL_VISUALIZATION,
 SPELL_ACTIONS,
 SPELL_LEARN,
 MULTICLASSING_ACTIONS,
 SPELLS_SLOTS_MANAGEMENT,
 SPELL_SLOT_ADDING,
 SPELL_SLOT_REMOVING,
 DAMAGE_REGISTRATION,
 HEALING_REGISTRATION,
 OVER_HEALING_CONFIRMATION,
 HIT_POINTS_REGISTRATION,
 LONG_REST,
 SHORT_REST,
 DICE_ACTION,
 NOTES_MANAGEMENT,
 NOTE_ADD,
 VOICE_NOTE_TITLE,
 MAPS_MANAGEMENT,
 MAPS_ZONE,
 MAPS_FILES,
 ADD_MAPS_FILES,
 SETTINGS_MENU_STATE,
 ARMOR_CLASS) = map(int, range(14, 60))

STOPPING = 99

# bot data keys
BOT_DATA_CHAT_IDS = 'bot_data_chat_ids'

# user_data keys
# we use the user_data because this function is for private use only
CHARACTERS_CREATOR_KEY = 'characters_creator'
CHARACTERS_KEY = 'characters'
TEMP_CHARACTER_KEY = 'temp_character'
CURRENT_CHARACTER_KEY = 'current_character'
CURRENT_ITEM_KEY = 'current_item'
CURRENT_INLINE_PAGE_INDEX_KEY = 'current_page_index'
INLINE_PAGES_KEY = 'inline_pages'
CURRENT_ABILITY_KEY = 'current_ability'
ABILITY_FEATURES_KEY = 'ability_features_keyboard'
TEMP_ABILITY_KEY = 'temp_ability'
TEMP_HEALING_KEY = 'temp_healing'
CURRENT_SPELL_KEY = 'current_spell'
LAST_MENU_MESSAGES = 'last_menu_message'
# Keys to store the data allowing a rollback in the case user use /stop command before ending the multiclass deleting
PENDING_REASSIGNMENT = 'pending_reassignment'
REMOVED_CLASS_LEVEL = 'removed_class_level'
REMAINING_CLASSES = 'remaining_classes'
# spell slots
SPELL_SLOTS = 'spell_slots'
DICE = 'dice'
DICE_MESSAGES = 'dice_messages'
ACTIVE_CONV = 'active_conv'
# keys for notes
TEMP_VOICE_MESSAGE_PATH = 'temp_voice_message_path'
# keys for maps
TEMP_ZONE_NAME = 'temp_zone_name'
TEMP_MAPS_PATHS = 'temp_maps_paths'
ADD_OR_INSERT_MAPS = 'add_or_insert_maps'
# keys for settings
USER_SETTINGS_KEY = 'user_settings'
SPELL_MANAGEMENT_KEY = 'spell_management'
# bag / currency
TEMP_CURRENCY_KEY = 'temp_currency'
CURRENCY_CONVERTER = 'currency_converter'
SELECTED_SOURCE_CURRENCY = 'selected_source_currency'
SELECTED_TARGET_CURRENCY = 'selected_target_currency'
# armor class
AC_KIND_KEY = 'ac_kind'

# character callback keys
BACK_BUTTON_CALLBACK_DATA = "back_button"
BAG_CALLBACK_DATA = 'bag'
SPELLS_CALLBACK_DATA = 'spells'
ABILITIES_CALLBACK_DATA = 'abilities'
FEATURE_POINTS_CALLBACK_DATA = 'feature_points'
SPELLS_SLOT_CALLBACK_DATA = 'spells_slot'
MULTICLASSING_CALLBACK_DATA = 'multiclass'
DELETE_CHARACTER_CALLBACK_DATA = 'delete_character'
AFFERMATIVE_CHARACTER_DELETION_CALLBACK_DATA = 'yes_delete_character'
NEGATIVE_CHARACTER_DELETION_CALLBACK_DATA = 'no_delete_character'
BAG_ITEM_INSERTION_CALLBACK_DATA = "bag_insert_item"
BAG_ITEM_EDIT_CALLBACK_DATA = "bag_edit_item"
BAG_MANAGE_CURRENCY_CALLBACK_DATA = "bag_manage_currency"
BAG_MANAGE_SINGLE_CURRENCY_CALLBACK_DATA = "bag_manage_single_currency"
BAG_MANAGE_CURRENCY_CONVERT_FUNCTION_CALLBACK_DATA = "bag_manage_currency_convert_function"
SELECT_SOURCE_CALLBACK_DATA = 'select_source'
SELECT_TARGET_CALLBACK_DATA = 'select_target'
CONVERT_CURRENCY_CALLBACK_DATA = 'convert'
ABILITY_LEARN_CALLBACK_DATA = "ability_learn"
ABILITY_EDIT_CALLBACK_DATA = "ability_edit"
ABILITY_DELETE_CALLBACK_DATA = "ability_delete"
ABILITY_USE_CALLBACK_DATA = "ability_use"
ABILITY_ACTIVE_CALLBACK_DATA = 'ability_active'
ABILITY_BACK_MENU_CALLBACK_DATA = "ability_back_menu"
ABILITY_IS_PASSIVE_CALLBACK_DATA = "ability_is_passive"
ABILITY_RESTORATION_TYPE_CALLBACK_DATA = "ability_restoration_type"
ABILITY_INSERT_CALLBACK_DATA = "ability_insert"
SPELL_LEARN_CALLBACK_DATA = "spells_learn"
SPELL_EDIT_CALLBACK_DATA = "spell_edit"
SPELL_USE_CALLBACK_DATA = "spell_use"
SPELL_DELETE_CALLBACK_DATA = "spell_delete"
SPELL_BACK_MENU_CALLBACK_DATA = "spell_back_menu"
SPELL_USAGE_BACK_MENU_CALLBACK_DATA = "spell_usage_back_menu"
LEVEL_UP_CALLBACK_DATA = "level_up"
LEVEL_DOWN_CALLBACK_DATA = "level_down"
DAMAGE_CALLBACK_DATA = "damage"
HEALING_CALLBACK_DATA = "healing"
HIT_POINTS_CALLBACK_DATA = "hit_points"
MULTICLASSING_ADD_CALLBACK_DATA = "add_multiclass"
MULTICLASSING_REMOVE_CALLBACK_DATA = "remove_multiclass"
SPELL_SLOTS_AUTO_CALLBACK_DATA = "spells_slot_auto"
SPELL_SLOTS_MANUAL_CALLBACK_DATA = "spells_slot_manual"
SPELLS_SLOTS_CHANGE_CALLBACK_DATA = "spells_slot_change"
SPELLS_SLOTS_RESET_CALLBACK_DATA = "spells_slot_reset"
SPELLS_SLOTS_REMOVE_CALLBACK_DATA = "spells_slot_remove"
SPELLS_SLOTS_INSERT_CALLBACK_DATA = "spells_slot_insert"
SPELL_SLOT_SELECTED_CALLBACK_DATA = "spell_slot_selected"
SPELL_SLOT_LEVEL_SELECTED_CALLBACK_DATA = "spell_slot_level"
LONG_REST_WARNING_CALLBACK_DATA = "long_rest_warning"
LONG_REST_CALLBACK_DATA = "long_rest"
SHORT_REST_WARNING_CALLBACK_DATA = "short_rest_warning"
SHORT_REST_CALLBACK_DATA = "short_rest"
ROLL_DICE_MENU_CALLBACK_DATA = "roll_dice_menu"
ROLL_DICE_CALLBACK_DATA = "roll_dice"
ROLL_DICE_DELETE_HISTORY_CALLBACK_DATA = "roll_dice_history_delete"
NOTES_CALLBACK_DATA = "notes"
INSERT_NEW_NOTE_CALLBACK_DATA = "insert_new_note"
OPEN_NOTE_CALLBACK_DATA = "open_note"
EDIT_NOTE_CALLBACK_DATA = "edit_note"
DELETE_NOTE_CALLBACK_DATA = "delete_note"
MAPS_CALLBACK_DATA = "maps"
SHOW_MAPS_CALLBACK_DATA = "show_maps"
INSERT_NEW_MAPS_CALLBACK_DATA = "insert_new_maps"
DELETE_SINGLE_MAP_CALLBACK_DATA = "delete_single_map"
ADD_NEW_MAP_CALLBACK_DATA = "add_new_map"
DELETE_ALL_ZONE_MAPMS_CALLBACK_DATA = "delete_all_zone_mapms"
SETTINGS_CALLBACK_DATA = "settings"
ARMOR_CLASS_CALLBACK_DATA = 'armor_class'

# Setting related callback
SETTING_SPELL_MANAGEMENT_CALLBACK_DATA = 'setting_spell_management'
# Spells management
SPELL_MANAGEMENT_PAGINATE_BY_LEVEL = 'paginate_by_level'
SPELL_MANAGEMENT_SELECT_LEVEL_DIRECTLY = 'select_level_directly'

# Path to the files directory
FILES_DIR_PATH = 'files/'
