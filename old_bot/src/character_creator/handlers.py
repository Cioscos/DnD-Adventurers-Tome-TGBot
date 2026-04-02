from telegram.ext import ConversationHandler, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from . import *
from .abilities import character_abilities_query_handler, character_ability_new_query_handler, \
    character_abilities_menu_query_handler, character_ability_visualization_query_handler, \
    character_ability_edit_handler, character_ability_delete_query_handler, character_ability_insert_query_handler, \
    character_ability_features_query_handler, character_ability_text_handler
from .armor_class import armor_class_main_menu_callback, armor_class_text_callback, edit_ac_callback, \
    edit_magic_armor_callback, edit_shield_ac_callback
from .bag import character_bag_query_handler, character_bag_new_object_query_handler, \
    character_bag_edit_object_query_handler, character_bag_currencies_menu_query_handler, \
    character_bag_currency_select_query_handler, character_bag_currency_edit_quantity_query_handler, \
    character_bag_currency_convert_function_query_handler, character_bag_item_insert, character_bag_item_edit_handler, \
    character_bag_item_delete_one_handler, character_bag_item_add_one_handler, character_bag_item_delete_all_handler, \
    character_bag_ask_item_overwrite_quantity_query_handler, character_ask_item_overwrite_quantity, \
    character_bag_currency_edit_quantity_text_handler, character_currency_convert_menu_query_handler, \
    character_currency_convert_quantity_handler
from .character_creator_general import character_creator_start_handler, character_creation_handler, \
    character_name_handler, character_race_handler, character_gender_handler, character_class_handler, \
    character_hit_points_handler, character_deleting_query_handler, character_creation_stop, \
    character_selection_query_handler, character_deleting_answer_query_handler, character_creator_stop_submenu, \
    character_generic_main_menu_query_handler
from .damage_healing import character_damage_query_handler, character_healing_query_handler, \
    character_damage_registration_handler, character_healing_value_check_or_registration_handler, \
    character_over_healing_registration_query_handler
from .dice import dice_handler, dice_actions_query_handler
from .feature_points import character_feature_point_query_handler, character_feature_points_edit_query_handler
from .hit_points import character_hit_points_query_handler, character_hit_points_registration_handler
from .level import character_change_level_query_handler, character_level_change_class_choice_handler
from .maps import character_creation_maps_query_handler, character_creation_new_maps_query_handler, \
    character_creation_show_maps_query_handler, character_creator_add_map_query_handler, \
    character_creation_maps_delete_all_query_handler, character_creator_delete_single_map_query_handler, \
    character_creation_ask_maps_file, character_creation_store_map_file, character_creation_store_map_photo, \
    character_creation_add_maps_done_command, character_creation_maps_done_command
from .multiclassing import character_multiclassing_query_handler, character_multiclassing_add_class_query_handler, \
    character_multiclassing_add_class_answer_handler, character_multiclassing_remove_class_query_handler, \
    character_multiclassing_remove_class_answer_query_handler, character_multiclassing_reassign_levels_query_handler
from .notes import character_creator_notes_query_handler, character_creator_new_note_query_handler, \
    character_creator_open_note_query_handler, character_creator_edit_note_query_handler, \
    character_creator_delete_note_query_handler, character_creator_notes_back_query_handler, \
    character_creator_insert_note_text, character_creator_insert_voice_message, character_creator_save_voice_note
from .pattern_verifiers import verify_selected_currency_callback_data, \
    verify_character_currency_converter_callback_data, verify_selected_map_callback_data
from .rest import character_long_rest_warning_query_handler, character_short_rest_warning_query_handler, \
    character_long_rest_query_handler, character_short_rest_query_handler
from .settings import character_creator_settings, character_creator_settings_callback_handler
from .spell_slots import character_spells_slots_query_handler, character_spells_slots_mode_answer_query_handler, \
    character_spells_slots_add_query_handler, character_spells_slots_remove_query_handler, \
    character_spells_slot_use_slot_query_handler, character_spells_slot_use_reset_query_handler, \
    character_spells_slot_change_mode_query_handler, character_spell_slot_add_answer_query_handler, \
    character_spell_slot_remove_answer_query_handler
from .spells import character_spells_query_handler, character_spells_by_level_query_handler, \
    character_spells_menu_query_handler, character_spell_visualization_query_handler, character_spell_edit_handler, \
    character_spell_delete_query_handler, character_spell_use_query_handler, character_spell_new_query_handler, \
    character_spell_learn_handler

character_creator_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(character_creator_start_handler, pattern=r"^character_manager$"),
        CommandHandler('character', character_creator_start_handler)
    ],
    states={
        CHARACTER_CREATION: [CommandHandler('newCharacter', character_creation_handler)],
        NAME_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, character_name_handler)],
        RACE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, character_race_handler)],
        GENDER_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, character_gender_handler)],
        CLASS_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, character_class_handler)],
        HIT_POINTS_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, character_hit_points_handler)],
        FUNCTION_SELECTION: [
            CallbackQueryHandler(character_change_level_query_handler, pattern=r"^level_(up|down)$"),
            CallbackQueryHandler(character_level_change_class_choice_handler,
                                 pattern=fr"^{LEVEL_UP_CALLBACK_DATA}\|.*$|^{LEVEL_DOWN_CALLBACK_DATA}\|.*$"),
            CallbackQueryHandler(character_bag_query_handler, pattern=fr"^{BAG_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_spells_query_handler, pattern=fr"^{SPELLS_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_abilities_query_handler, pattern=fr"^{ABILITIES_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_spells_slots_query_handler,
                                 pattern=fr"^{SPELLS_SLOT_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_feature_point_query_handler,
                                 pattern=fr"^{FEATURE_POINTS_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_multiclassing_query_handler,
                                 pattern=fr"^{MULTICLASSING_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_deleting_query_handler,
                                 pattern=fr"^{DELETE_CHARACTER_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_damage_query_handler,
                                 pattern=fr"^{DAMAGE_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_healing_query_handler,
                                 pattern=fr"^{HEALING_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_hit_points_query_handler,
                                 pattern=fr"^{HIT_POINTS_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_long_rest_warning_query_handler,
                                 pattern=fr"^{LONG_REST_WARNING_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_short_rest_warning_query_handler,
                                 pattern=fr"^{SHORT_REST_WARNING_CALLBACK_DATA}$"),
            CallbackQueryHandler(dice_handler,
                                 pattern=fr"^{ROLL_DICE_MENU_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_creator_settings, pattern=fr"^{SETTINGS_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_creator_notes_query_handler, pattern=fr"^{NOTES_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_creation_maps_query_handler, pattern=fr"^{MAPS_CALLBACK_DATA}$"),
            CallbackQueryHandler(armor_class_main_menu_callback, pattern=fr"^{ARMOR_CLASS_CALLBACK_DATA}$"),
            CommandHandler('stop', character_creation_stop)
        ],
        DAMAGE_REGISTRATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_damage_registration_handler)
        ],
        HEALING_REGISTRATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_healing_value_check_or_registration_handler)
        ],
        OVER_HEALING_CONFIRMATION: [
            CallbackQueryHandler(character_over_healing_registration_query_handler,
                                 pattern=r'^[yn]$')
        ],
        HIT_POINTS_REGISTRATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_hit_points_registration_handler)
        ],
        ARMOR_CLASS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, armor_class_text_callback),
            CallbackQueryHandler(edit_ac_callback, pattern=fr"^{ARMOR_CLASS_CALLBACK_DATA}\|ac$"),
            CallbackQueryHandler(edit_shield_ac_callback, pattern=fr"^{ARMOR_CLASS_CALLBACK_DATA}\|shield$"),
            CallbackQueryHandler(edit_magic_armor_callback, pattern=fr"^{ARMOR_CLASS_CALLBACK_DATA}\|magic_armor$")
        ],
        LONG_REST: [
            CallbackQueryHandler(character_long_rest_query_handler,
                                 pattern=fr"^{LONG_REST_CALLBACK_DATA}$")
        ],
        SHORT_REST: [
            CallbackQueryHandler(character_short_rest_query_handler,
                                 pattern=fr"^{SHORT_REST_CALLBACK_DATA}$")
        ],
        CHARACTER_SELECTION: [
            CallbackQueryHandler(character_selection_query_handler),
            CommandHandler('newCharacter', character_creation_handler)
        ],
        CHARACTER_DELETION: [
            CallbackQueryHandler(character_deleting_answer_query_handler,
                                 pattern=fr"^{AFFERMATIVE_CHARACTER_DELETION_CALLBACK_DATA}|{NEGATIVE_CHARACTER_DELETION_CALLBACK_DATA}$")
        ],
        BAG_MANAGEMENT: [
            CallbackQueryHandler(character_bag_new_object_query_handler,
                                 pattern=fr"^{BAG_ITEM_INSERTION_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_bag_edit_object_query_handler,
                                 pattern=fr"^{BAG_ITEM_EDIT_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_bag_currencies_menu_query_handler,
                                 pattern=fr"^{BAG_MANAGE_CURRENCY_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_bag_currency_select_query_handler,
                                 pattern=fr"^{BAG_MANAGE_SINGLE_CURRENCY_CALLBACK_DATA}\|.+$"),
            CallbackQueryHandler(character_bag_currency_edit_quantity_query_handler,
                                 pattern=verify_selected_currency_callback_data),
            CallbackQueryHandler(character_bag_currency_convert_function_query_handler,
                                 pattern=fr"^{BAG_MANAGE_CURRENCY_CONVERT_FUNCTION_CALLBACK_DATA}$")
        ],
        BAG_ITEM_INSERTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_bag_item_insert)
        ],
        BAG_ITEM_EDIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_bag_item_edit_handler),
            CallbackQueryHandler(character_bag_item_delete_one_handler,
                                 pattern=fr"^{BAG_ITEM_EDIT_CALLBACK_DATA}\|-"),
            CallbackQueryHandler(character_bag_item_add_one_handler,
                                 pattern=fr"^{BAG_ITEM_EDIT_CALLBACK_DATA}\|\+"),
            CallbackQueryHandler(character_bag_item_delete_all_handler,
                                 pattern=fr"^{BAG_ITEM_EDIT_CALLBACK_DATA}\|all"),
            CallbackQueryHandler(character_bag_ask_item_overwrite_quantity_query_handler,
                                 pattern=fr"^{BAG_ITEM_EDIT_CALLBACK_DATA}\|overwrite$")
        ],
        BAG_ITEM_OVERWRITE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_ask_item_overwrite_quantity)
        ],
        BAG_CURRENCY_INSERT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_bag_currency_edit_quantity_text_handler)
        ],
        BAG_CURRENCY_FUNCTIONS: [
            CallbackQueryHandler(character_currency_convert_menu_query_handler,
                                 pattern=verify_character_currency_converter_callback_data)
        ],
        BAG_CURRENCY_CONVERT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_currency_convert_quantity_handler)
        ],
        FEATURE_POINTS_EDIT: [
            CallbackQueryHandler(character_feature_points_edit_query_handler,
                                 pattern=r"^(strength|dexterity|constitution|intelligence|wisdom|charisma)\|[+-]$")
        ],
        ABILITIES_MENU: [
            CallbackQueryHandler(character_ability_new_query_handler,
                                 pattern=fr"^{SPELL_LEARN_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_abilities_menu_query_handler,
                                 pattern=fr"^(ability_name\|.+|prev_page|next_page)$")
        ],
        ABILITY_VISUALIZATION: [
            CallbackQueryHandler(character_ability_visualization_query_handler,
                                 pattern=fr"{ABILITY_EDIT_CALLBACK_DATA}|{ABILITY_DELETE_CALLBACK_DATA}|"
                                         fr"{ABILITY_ACTIVE_CALLBACK_DATA}|{ABILITY_USE_CALLBACK_DATA}"
                                         fr"|{ABILITY_BACK_MENU_CALLBACK_DATA}")
        ],
        ABILITY_ACTIONS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_ability_edit_handler),
            CallbackQueryHandler(character_ability_delete_query_handler,
                                 pattern=r'^[yn]$')
        ],
        ABILITY_LEARN: [
            CallbackQueryHandler(character_ability_insert_query_handler,
                                 pattern=fr"^{ABILITY_INSERT_CALLBACK_DATA}$"),
            CallbackQueryHandler(
                character_ability_features_query_handler,
                pattern=fr"^({ABILITY_IS_PASSIVE_CALLBACK_DATA}\|\d+|{ABILITY_RESTORATION_TYPE_CALLBACK_DATA}\|(short|long))$"
            ),
            CallbackQueryHandler(character_ability_new_query_handler,
                                 pattern=fr"^{ABILITY_LEARN_CALLBACK_DATA}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_ability_text_handler)
        ],
        SPELL_LEVEL_MENU: [
            CallbackQueryHandler(character_spells_by_level_query_handler,
                                 pattern=fr"^{SPELL_USAGE_BACK_MENU_CALLBACK_DATA}|{SPELL_LEARN_CALLBACK_DATA}|spell_of_level\|\d+$")
        ],
        SPELLS_MENU: [
            CallbackQueryHandler(character_spells_menu_query_handler,
                                 pattern=fr"^({SPELL_USAGE_BACK_MENU_CALLBACK_DATA}|spell_name\|.+|prev_page|next_page|{SPELL_LEARN_CALLBACK_DATA})$")
        ],
        SPELL_VISUALIZATION: [
            CallbackQueryHandler(character_spell_visualization_query_handler,
                                 pattern=fr"{SPELL_EDIT_CALLBACK_DATA}|{SPELL_DELETE_CALLBACK_DATA}|"
                                         fr"{SPELL_BACK_MENU_CALLBACK_DATA}|{SPELL_USE_CALLBACK_DATA}")
        ],
        SPELL_ACTIONS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_spell_edit_handler),
            CallbackQueryHandler(character_spell_delete_query_handler,
                                 pattern=r'^[yn]$'),
            CallbackQueryHandler(character_spell_use_query_handler,
                                 pattern=fr"^{SPELL_USAGE_BACK_MENU_CALLBACK_DATA}|{SPELL_SLOT_SELECTED_CALLBACK_DATA}\|\d+$")
        ],
        SPELL_LEARN: [
            CallbackQueryHandler(character_spell_new_query_handler,
                                 pattern=fr"^{SPELL_LEARN_CALLBACK_DATA}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_spell_learn_handler)
        ],
        MULTICLASSING_ACTIONS: [
            CallbackQueryHandler(character_multiclassing_add_class_query_handler,
                                 pattern=fr"^{MULTICLASSING_ADD_CALLBACK_DATA}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_multiclassing_add_class_answer_handler),
            CallbackQueryHandler(character_multiclassing_remove_class_query_handler,
                                 pattern=fr"^{MULTICLASSING_REMOVE_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_multiclassing_remove_class_answer_query_handler,
                                 pattern=r"^remove\|.+$"),
            CallbackQueryHandler(character_multiclassing_reassign_levels_query_handler,
                                 pattern=r"^assign_levels\|.+\|\d+$")
        ],
        SPELLS_SLOTS_MANAGEMENT: [
            CallbackQueryHandler(character_spells_slots_mode_answer_query_handler,
                                 pattern=r"^spells_slot_(auto|manual)$"),
            CallbackQueryHandler(character_spells_slots_add_query_handler,
                                 pattern=fr"^{SPELLS_SLOTS_INSERT_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_spells_slots_remove_query_handler,
                                 pattern=fr"^{SPELLS_SLOTS_REMOVE_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_spells_slot_use_slot_query_handler,
                                 pattern=fr"^{SPELL_SLOT_SELECTED_CALLBACK_DATA}\|\d+$"),
            CallbackQueryHandler(character_spells_slot_use_reset_query_handler,
                                 pattern=fr"^{SPELLS_SLOTS_RESET_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_spells_slot_change_mode_query_handler,
                                 pattern=fr"^{SPELLS_SLOTS_CHANGE_CALLBACK_DATA}$")
        ],
        SPELL_SLOT_ADDING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_spell_slot_add_answer_query_handler)
        ],
        SPELL_SLOT_REMOVING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_spell_slot_remove_answer_query_handler)
        ],
        DICE_ACTION: [
            CallbackQueryHandler(dice_actions_query_handler,
                                 pattern=fr"^(d\d+\|[+-]|{ROLL_DICE_CALLBACK_DATA}|{ROLL_DICE_DELETE_HISTORY_CALLBACK_DATA})$")
        ],
        NOTES_MANAGEMENT: [
            CallbackQueryHandler(character_creator_new_note_query_handler,
                                 pattern=fr"^{INSERT_NEW_NOTE_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_creator_open_note_query_handler,
                                 pattern=fr"^{OPEN_NOTE_CALLBACK_DATA}\|.+$"),
            CallbackQueryHandler(character_creator_edit_note_query_handler,
                                 pattern=fr"^{EDIT_NOTE_CALLBACK_DATA}\|.+$"),
            CallbackQueryHandler(character_creator_delete_note_query_handler,
                                 pattern=fr"^{DELETE_NOTE_CALLBACK_DATA}\|.+$"),
            CallbackQueryHandler(character_creator_notes_back_query_handler,
                                 pattern=fr"^{BACK_BUTTON_CALLBACK_DATA}$")
        ],
        NOTE_ADD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_creator_insert_note_text),
            MessageHandler(filters.VOICE, character_creator_insert_voice_message)
        ],
        VOICE_NOTE_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_creator_save_voice_note)
        ],
        MAPS_MANAGEMENT: [
            CallbackQueryHandler(character_creation_new_maps_query_handler,
                                 pattern=fr"^{INSERT_NEW_MAPS_CALLBACK_DATA}$"),
            CallbackQueryHandler(character_creation_show_maps_query_handler,
                                 pattern=verify_selected_map_callback_data),
            CallbackQueryHandler(character_creator_add_map_query_handler,
                                 pattern=fr"^{ADD_NEW_MAP_CALLBACK_DATA}\|.+$"),
            CallbackQueryHandler(character_creation_maps_delete_all_query_handler,
                                 pattern=fr"^{DELETE_ALL_ZONE_MAPMS_CALLBACK_DATA}\|.+$"),
            CallbackQueryHandler(character_creator_delete_single_map_query_handler,
                                 pattern=fr"^{DELETE_SINGLE_MAP_CALLBACK_DATA}\|.+$")
        ],
        MAPS_ZONE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, character_creation_ask_maps_file)
        ],
        ADD_MAPS_FILES: [
            MessageHandler(filters.Document.IMAGE & ~filters.PHOTO & ~filters.TEXT,
                           character_creation_store_map_file),
            MessageHandler(filters.PHOTO & ~filters.TEXT, character_creation_store_map_photo),
            CommandHandler('done', character_creation_add_maps_done_command)
        ],
        MAPS_FILES: [
            MessageHandler(filters.Document.IMAGE & ~filters.PHOTO & ~filters.TEXT,
                           character_creation_store_map_file),
            MessageHandler(filters.PHOTO & ~filters.TEXT, character_creation_store_map_photo),
            CommandHandler('done', character_creation_maps_done_command)
        ],
        SETTINGS_MENU_STATE: [
            CallbackQueryHandler(character_creator_settings_callback_handler, pattern=r'^setting\|.+$')
        ]
    },
    fallbacks=[
        CommandHandler("stop", character_creator_stop_submenu),
        CallbackQueryHandler(character_generic_main_menu_query_handler)
    ],
    name='character_creator_handler_v24',
    persistent=True
)
