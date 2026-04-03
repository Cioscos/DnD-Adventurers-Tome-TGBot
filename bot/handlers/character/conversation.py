"""Character management ConversationHandler — wires all feature handlers.

This module assembles the top-level ``character_conversation_handler`` that
drives the entire character management flow.  It uses PTB's
``arbitrary_callback_data`` feature; all inline button payloads are
:class:`~bot.models.character_state.CharAction` dataclass instances.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.handlers.character import (
    CHAR_ABILITIES_MENU,
    CHAR_ABILITY_LEARN_DESC,
    CHAR_ABILITY_LEARN_NAME,
    CHAR_ABILITY_LEARN_USES,
    CHAR_AC_MENU,
    CHAR_AC_SET_BASE,
    CHAR_AC_SET_MAGIC,
    CHAR_AC_SET_SHIELD,
    CHAR_BAG_ADD_NAME,
    CHAR_BAG_ADD_QTY,
    CHAR_BAG_ADD_WEIGHT,
    CHAR_BAG_EDIT,
    CHAR_BAG_MENU,
    CHAR_CLASS_SUBCLASS_INPUT,
    CHAR_CONC_SAVE,
    CHAR_CURRENCY_CONVERT,
    CHAR_CURRENCY_EDIT,
    CHAR_CURRENCY_MENU,
    CHAR_DELETE_CONFIRM,
    CHAR_DICE_MENU,
    CHAR_HP_DAMAGE,
    CHAR_HP_HEAL,
    CHAR_HP_MENU,
    CHAR_HP_SET,
    CHAR_MAP_ADD_FILE,
    CHAR_MAP_NEW_ZONE,
    CHAR_MAPS_MENU,
    CHAR_MENU,
    CHAR_MULTICLASS_ADD,
    CHAR_MULTICLASS_ADD_LEVELS,
    CHAR_MULTICLASS_MENU,
    CHAR_NEW_NAME,
    CHAR_NOTE_EDIT,
    CHAR_NOTE_NEW_BODY,
    CHAR_NOTE_NEW_TITLE,
    CHAR_NOTES_MENU,
    CHAR_SELECT,
    CHAR_SETTINGS_MENU,
    CHAR_SPELL_EDIT,
    CHAR_SPELL_LEARN,
    CHAR_SPELL_SEARCH,
    CHAR_SPELL_SLOTS_MENU,
    CHAR_SPELL_SLOT_ADD,
    CHAR_SPELL_SLOT_REMOVE,
    CHAR_SPELLS_MENU,
    CHAR_STATS_MENU,
    CHAR_STATS_SET,
    CHAR_VOICE_NOTE_TITLE,
    STOPPING,
)
from bot.models.character_state import CharAction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Master callback dispatcher
# ---------------------------------------------------------------------------

async def character_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Route any CharAction callback to the appropriate feature handler."""
    from bot.handlers.character.abilities import (
        ask_learn_ability, forget_ability, show_abilities_menu,
        show_ability_detail, toggle_ability, use_ability,
    )
    from bot.handlers.character.armor_class import ask_ac_input, show_ac_menu
    from bot.handlers.character.bag import (
        ask_add_item, modify_item_quantity, remove_all_item,
        show_bag_menu, show_item_detail,
    )
    from bot.handlers.character.currency import (
        ask_convert_amount, show_convert_source, show_convert_target,
        show_currency_edit, show_currency_menu,
    )
    from bot.handlers.character.dice import (
        clear_dice_history, roll_dice, show_dice_count_picker, show_dice_menu,
    )
    from bot.handlers.character.hit_points import ask_hp_input, handle_rest, show_hp_menu
    from bot.handlers.character.maps import (
        ask_add_file, ask_new_zone, delete_map_file, delete_zone,
        send_map_file, show_maps_menu, show_zone,
    )
    from bot.handlers.character.menu import show_character_menu
    from bot.handlers.character.multiclass import (
        apply_level_change, ask_add_class, ask_custom_class, change_level,
        handle_guided_class_selected, remove_class, show_guided_class_list,
        show_multiclass_menu, show_remove_class, skip_subclass,
    )
    from bot.handlers.character.notes import (
        ask_edit_note, ask_new_note_title, ask_voice_note_title,
        delete_note, show_note, show_notes_menu,
    )
    from bot.handlers.character.selection import (
        handle_delete_confirm, show_character_selection, show_delete_confirm,
    )
    from bot.handlers.character.settings import show_settings_menu, toggle_spell_management, toggle_party_active
    from bot.handlers.character.spell_slots import (
        ask_add_slot, remove_slot_level, reset_all_slots,
        restore_slot, show_slot_detail, show_spell_slots_menu, use_slot,
    )
    from bot.handlers.character.spells import (
        activate_concentration, ask_concentration_save_damage,
        ask_spell_learn, ask_spell_edit_field, ask_spell_search,
        drop_concentration, finalize_spell_learn, forget_spell,
        show_spell_detail, show_spell_edit_menu, show_spell_search_results,
        show_spells_menu, show_use_spell_level_picker,
        toggle_pin_spell, use_spell_at_level,
    )
    from bot.handlers.character.stats import ask_stat_input, show_stats_menu

    query = update.callback_query
    if query is None:
        return CHAR_MENU

    data: CharAction = query.data
    if not isinstance(data, CharAction):
        return CHAR_MENU

    action = data.action
    cid = data.char_id
    sub = data.sub

    # ─── Character selection ───
    if action == "char_select":
        return await show_character_selection(update, context)
    if action == "char_new":
        from bot.keyboards.character import build_cancel_keyboard
        await query.answer()
        await query.edit_message_text(
            "✍️ Inserisci il *nome* del nuovo personaggio:",
            reply_markup=build_cancel_keyboard(0, "char_select"),
            parse_mode="MarkdownV2",
        )
        return CHAR_NEW_NAME
    if action == "char_delete":
        if sub == "confirm":
            return await handle_delete_confirm(update, context, cid)
        return await show_delete_confirm(update, context, cid)

    # ─── Main menu ───
    if action == "char_menu":
        return await show_character_menu(update, context, char_id=cid)

    # ─── HP / Combat ───
    if action == "char_hp":
        if sub in ("damage", "heal", "set_max", "set_current"):
            return await ask_hp_input(update, context, cid, sub)
        return await show_hp_menu(update, context, cid)
    if action == "char_rest":
        if sub == "long":
            from bot.keyboards.character import build_rest_confirm_keyboard
            from bot.utils.formatting import _esc
            await query.answer()
            await query.edit_message_text(
                "🌙 Vuoi fare un *riposo lungo*? HP e slot saranno ripristinati\\.",
                reply_markup=build_rest_confirm_keyboard(cid, "long"),
                parse_mode="MarkdownV2",
            )
            return CHAR_HP_MENU
        if sub == "short":
            from bot.keyboards.character import build_rest_confirm_keyboard
            await query.answer()
            await query.edit_message_text(
                "⏸️ Vuoi fare un *riposo breve*?",
                reply_markup=build_rest_confirm_keyboard(cid, "short"),
                parse_mode="MarkdownV2",
            )
            return CHAR_HP_MENU
        if sub in ("long_confirm", "short_confirm"):
            rest_type = sub.split("_")[0]
            return await handle_rest(update, context, cid, rest_type)
        # show rest picker
        from bot.keyboards.character import build_rest_keyboard
        await query.answer()
        await query.edit_message_text(
            "😴 *Scegli il tipo di riposo:*",
            reply_markup=build_rest_keyboard(cid),
            parse_mode="MarkdownV2",
        )
        return CHAR_HP_MENU

    # ─── Armor class ───
    if action == "char_ac":
        if sub in ("set_base", "set_shield", "set_magic"):
            return await ask_ac_input(update, context, cid, sub)
        return await show_ac_menu(update, context, cid)

    # ─── Ability scores ───
    if action == "char_stats":
        if sub:
            return await ask_stat_input(update, context, cid, sub)
        return await show_stats_menu(update, context, cid)

    # ─── Level / class ───
    if action == "char_level":
        if sub in ("up", "down") and not data.extra:
            return await change_level(update, context, cid, sub)
        if sub in ("up", "down") and data.extra:
            return await apply_level_change(update, context, cid, data.extra, sub)
        from bot.keyboards.character import build_level_keyboard
        await query.answer()
        await query.edit_message_text(
            "⚔️ *Gestione Livello*",
            reply_markup=build_level_keyboard(cid),
            parse_mode="MarkdownV2",
        )
        return CHAR_MULTICLASS_MENU

    # ─── Spells ───
    if action == "char_spells":
        if sub == "learn":
            return await ask_spell_learn(update, context, cid)
        if sub == "search":
            return await ask_spell_search(update, context, cid)
        if sub == "search_show" or (not sub and data.extra == "search_show"):
            return await show_spell_search_results(update, context, cid)
        if sub == "learn_conc_yes":
            return await finalize_spell_learn(update, context, is_concentration=True)
        if sub == "learn_conc_no":
            return await finalize_spell_learn(update, context, is_concentration=False)
        if sub == "detail":
            back_page = int(data.back[4]) if len(data.back) > 4 else 0
            back_extra = data.back[5] if len(data.back) > 5 else ""
            return await show_spell_detail(update, context, cid, data.item_id, back_page, back_extra)
        if sub == "forget":
            return await forget_spell(update, context, cid, data.item_id)
        if sub == "use":
            return await show_use_spell_level_picker(update, context, cid, data.item_id)
        if sub == "use_slot":
            try:
                slot_level = int(data.extra)
            except (ValueError, AttributeError):
                slot_level = 1
            return await use_spell_at_level(update, context, cid, data.item_id, slot_level)
        if sub == "activate_conc":
            return await activate_concentration(update, context, cid, data.item_id)
        if sub == "drop_conc":
            return await drop_concentration(update, context, cid)
        if sub == "conc_save":
            return await ask_concentration_save_damage(update, context, cid)
        if sub == "pin":
            return await toggle_pin_spell(update, context, cid, data.item_id)
        if sub == "edit_menu":
            return await show_spell_edit_menu(update, context, cid, data.item_id)
        if sub and sub.startswith("edit_"):
            field = sub[5:]  # strip "edit_" prefix
            return await ask_spell_edit_field(update, context, cid, data.item_id, field)
        level_filter: int | None = int(data.extra) if data.extra and data.extra.lstrip("-").isdigit() else None
        return await show_spells_menu(update, context, cid, data.page, level_filter)

    # ─── Spell slots ───
    if action == "char_slots":
        if sub == "add":
            return await ask_add_slot(update, context, cid)
        if sub == "slot_detail":
            return await show_slot_detail(update, context, cid, data.item_id)
        if sub == "use":
            return await use_slot(update, context, cid, data.item_id)
        if sub == "restore":
            return await restore_slot(update, context, cid, data.item_id)
        if sub == "reset_all":
            return await reset_all_slots(update, context, cid)
        if sub == "remove":
            return await remove_slot_level(update, context, cid, data.item_id)
        return await show_spell_slots_menu(update, context, cid)

    # ─── Bag ───
    if action == "char_bag":
        if sub == "add":
            return await ask_add_item(update, context, cid)
        if sub == "item_detail":
            back_page = int(data.back[4]) if len(data.back) > 4 else 0
            return await show_item_detail(update, context, cid, data.item_id, back_page)
        if sub == "qty_add":
            return await modify_item_quantity(update, context, cid, data.item_id, +1)
        if sub == "qty_rem":
            return await modify_item_quantity(update, context, cid, data.item_id, -1)
        if sub == "remove_all":
            return await remove_all_item(update, context, cid, data.item_id)
        return await show_bag_menu(update, context, cid, data.page)

    # ─── Currency ───
    if action == "char_currency":
        if sub == "convert":
            return await show_convert_source(update, context, cid)
        if sub == "conv_source":
            return await show_convert_target(update, context, cid, data.extra)
        if sub == "conv_target":
            parts = data.extra.split("|", 1)
            src, tgt = parts[0], parts[1] if len(parts) > 1 else parts[0]
            return await ask_convert_amount(update, context, cid, src, tgt)
        if sub in ("add", "remove"):
            return await show_currency_edit(update, context, cid, data.extra, sub)
        if sub == "edit":
            # Show currency editor for the given currency type
            from bot.keyboards.character import build_currency_edit_keyboard
            from bot.utils.formatting import CURRENCY_LABELS
            key = data.extra
            label, emoji = CURRENCY_LABELS.get(key, (key, "💰"))
            await query.answer()
            await query.edit_message_text(
                f"{emoji} *{label}*\n\nScegli un'operazione:",
                reply_markup=build_currency_edit_keyboard(cid, key),
                parse_mode="MarkdownV2",
            )
            return CHAR_CURRENCY_MENU
        return await show_currency_menu(update, context, cid)

    # ─── Abilities ───
    if action == "char_abilities":
        if sub == "learn":
            return await ask_learn_ability(update, context, cid)
        if sub == "detail":
            back_page = int(data.back[4]) if len(data.back) > 4 else 0
            return await show_ability_detail(update, context, cid, data.item_id, back_page)
        if sub == "use":
            return await use_ability(update, context, cid, data.item_id)
        if sub == "toggle":
            return await toggle_ability(update, context, cid, data.item_id)
        if sub == "forget":
            return await forget_ability(update, context, cid, data.item_id)
        return await show_abilities_menu(update, context, cid, data.page)

    # ─── Multiclass ───
    if action == "char_multiclass":
        if sub == "add":
            return await ask_add_class(update, context, cid)
        if sub == "guided":
            return await show_guided_class_list(update, context, cid)
        if sub == "custom":
            return await ask_custom_class(update, context, cid)
        if sub == "select_guided":
            return await handle_guided_class_selected(update, context, cid, data.extra)
        if sub == "skip_subclass":
            return await skip_subclass(update, context, cid)
        if sub == "remove":
            return await show_remove_class(update, context, cid)
        if sub == "remove_confirm":
            return await remove_class(update, context, cid, data.extra)
        return await show_multiclass_menu(update, context, cid)

    # ─── Class Resources ───
    if action == "char_class_res":
        from bot.handlers.character.class_resources import (
            show_class_resources_menu, use_class_resource,
            restore_one_class_resource, restore_all_class_resources,
        )
        try:
            class_id = int(data.extra)
        except (ValueError, TypeError):
            return CHAR_MULTICLASS_MENU
        if sub == "menu":
            return await show_class_resources_menu(update, context, cid, class_id)
        if sub == "use":
            return await use_class_resource(update, context, cid, class_id, data.item_id)
        if sub == "restore_one":
            return await restore_one_class_resource(update, context, cid, class_id, data.item_id)
        if sub == "restore_all":
            return await restore_all_class_resources(update, context, cid, class_id)
        if sub == "noop":
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MULTICLASS_MENU
        return await show_class_resources_menu(update, context, cid, class_id)

    # ─── Dice ───
    if action == "char_dice":
        if sub == "clear_history":
            return await clear_dice_history(update, context, cid)
        if sub == "roll":
            parts = data.extra.split("|", 1)
            count, die = int(parts[0]), parts[1]
            return await roll_dice(update, context, cid, count, die)
        if sub and sub.startswith("d"):
            return await show_dice_count_picker(update, context, cid, sub)
        return await show_dice_menu(update, context, cid)

    # ─── Notes ───
    if action == "char_notes":
        if sub == "new":
            return await ask_new_note_title(update, context, cid)
        if sub == "new_voice":
            return await ask_voice_note_title(update, context, cid)
        if sub == "open":
            back_page = int(data.back[4]) if len(data.back) > 4 else 0
            return await show_note(update, context, cid, data.extra, back_page)
        if sub == "edit":
            return await ask_edit_note(update, context, cid, data.extra)
        if sub == "delete":
            return await delete_note(update, context, cid, data.extra)
        return await show_notes_menu(update, context, cid, data.page)

    # ─── Maps ───
    if action == "char_maps":
        if sub == "new_zone":
            return await ask_new_zone(update, context, cid)
        if sub == "zone":
            back_page = int(data.back[4]) if len(data.back) > 4 else 0
            return await show_zone(update, context, cid, data.extra, back_page)
        if sub == "add_file":
            return await ask_add_file(update, context, cid, data.extra)
        if sub == "view_file":
            return await send_map_file(update, context, cid, data.item_id)
        if sub == "delete_file":
            return await delete_map_file(update, context, cid, data.item_id, data.extra)
        if sub == "delete_zone":
            return await delete_zone(update, context, cid, data.extra)
        return await show_maps_menu(update, context, cid, data.page)

    # ─── Settings ───
    if action == "char_settings":
        if sub == "toggle_spell_mgmt":
            return await toggle_spell_management(update, context, cid)
        return await show_settings_menu(update, context, cid)

    # ─── Party active toggle ───
    if action == "char_party_active":
        return await toggle_party_active(update, context, cid)

    return CHAR_MENU


def _is_char_action(data) -> bool:
    return isinstance(data, CharAction)


# ---------------------------------------------------------------------------
# /stop command handler
# ---------------------------------------------------------------------------

async def stop_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the current input operation and return to the character menu."""
    from bot.handlers.character.menu import show_character_menu
    from bot.handlers.character.selection import show_character_selection

    # Clear all known pending-op keys left by text-input flows
    pending_keys = [k for k in list(context.user_data.keys()) if "pending" in k]
    for k in pending_keys:
        context.user_data.pop(k, None)

    char_id: int = context.user_data.get("active_char_id", 0)
    if not char_id:
        # Fallback: scan user_data values for a dict carrying char_id
        for v in context.user_data.values():
            if isinstance(v, dict) and v.get("char_id"):
                char_id = v["char_id"]
                break

    if update.message:
        await update.message.reply_text(
            "✋ Operazione annullata\\.", parse_mode="MarkdownV2"
        )

    if char_id:
        return await show_character_menu(update, context, char_id=char_id)
    return await show_character_selection(update, context)


# ---------------------------------------------------------------------------
# Build the ConversationHandler
# ---------------------------------------------------------------------------

def build_character_conversation_handler() -> ConversationHandler:
    """Assemble and return the character management ConversationHandler."""
    from bot.handlers.character.armor_class import handle_ac_text
    from bot.handlers.character.bag import handle_bag_text
    from bot.handlers.character.currency import handle_convert_text, handle_currency_text
    from bot.handlers.character.abilities import handle_ability_learn_text
    from bot.handlers.character.multiclass import handle_multiclass_add_text, handle_subclass_text
    from bot.handlers.character.hit_points import handle_hp_text
    from bot.handlers.character.maps import handle_map_file, handle_new_zone_text
    from bot.handlers.character.notes import (
        handle_edit_note_text,
        handle_note_body_text,
        handle_note_title_text,
        handle_voice_note,
    )
    from bot.handlers.character.selection import (
        handle_new_character_name,
        show_character_selection,
    )
    from bot.handlers.character.spell_slots import handle_slot_add_text
    from bot.handlers.character.spells import (
        handle_concentration_save_text, handle_spell_edit_text,
        handle_spell_learn_text, handle_spell_search_text,
    )
    from bot.handlers.character.stats import handle_stat_text

    # Generic CharAction handler (covers all inline-button actions)
    char_callback = CallbackQueryHandler(
        character_callback_handler,
        pattern=_is_char_action,
    )
    # Text message handlers (one per multi-step input flow)
    text_filter = filters.TEXT & ~filters.COMMAND
    photo_filter = filters.PHOTO
    doc_filter = filters.Document.ALL
    voice_filter = filters.VOICE

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                lambda u, c: show_character_selection(u, c),
                pattern=lambda d: isinstance(d, CharAction) and d.action == "char_entry",
            ),
            # Also accept a plain "char_select" callback (from the main menu)
            CallbackQueryHandler(
                lambda u, c: show_character_selection(u, c),
                pattern=lambda d: isinstance(d, CharAction) and d.action == "char_select",
            ),
        ],
        states={
            CHAR_SELECT: [char_callback],
            CHAR_NEW_NAME: [
                MessageHandler(text_filter, handle_new_character_name),
                char_callback,
            ],
            CHAR_MENU: [char_callback],
            CHAR_HP_MENU: [char_callback],
            CHAR_HP_SET: [
                MessageHandler(text_filter, handle_hp_text),
                char_callback,
            ],
            CHAR_HP_DAMAGE: [
                MessageHandler(text_filter, handle_hp_text),
                char_callback,
            ],
            CHAR_HP_HEAL: [
                MessageHandler(text_filter, handle_hp_text),
                char_callback,
            ],
            CHAR_AC_MENU: [char_callback],
            CHAR_AC_SET_BASE: [
                MessageHandler(text_filter, handle_ac_text),
                char_callback,
            ],
            CHAR_AC_SET_SHIELD: [
                MessageHandler(text_filter, handle_ac_text),
                char_callback,
            ],
            CHAR_AC_SET_MAGIC: [
                MessageHandler(text_filter, handle_ac_text),
                char_callback,
            ],
            CHAR_STATS_MENU: [char_callback],
            CHAR_STATS_SET: [
                MessageHandler(text_filter, handle_stat_text),
                char_callback,
            ],
            CHAR_SPELLS_MENU: [char_callback],
            CHAR_SPELL_LEARN: [
                MessageHandler(text_filter, handle_spell_learn_text),
                char_callback,
            ],
            CHAR_SPELL_SLOTS_MENU: [char_callback],
            CHAR_SPELL_SLOT_ADD: [
                MessageHandler(text_filter, handle_slot_add_text),
                char_callback,
            ],
            CHAR_SPELL_SLOT_REMOVE: [char_callback],
            CHAR_SPELL_EDIT: [
                MessageHandler(text_filter, handle_spell_edit_text),
                char_callback,
            ],
            CHAR_CONC_SAVE: [
                MessageHandler(text_filter, handle_concentration_save_text),
                char_callback,
            ],
            CHAR_SPELL_SEARCH: [
                MessageHandler(text_filter, handle_spell_search_text),
                char_callback,
            ],
            CHAR_BAG_MENU: [char_callback],
            CHAR_BAG_ADD_NAME: [
                MessageHandler(text_filter, handle_bag_text),
                char_callback,
            ],
            CHAR_BAG_ADD_WEIGHT: [
                MessageHandler(text_filter, handle_bag_text),
                char_callback,
            ],
            CHAR_BAG_ADD_QTY: [
                MessageHandler(text_filter, handle_bag_text),
                char_callback,
            ],
            CHAR_BAG_EDIT: [char_callback],
            CHAR_CURRENCY_MENU: [char_callback],
            CHAR_CURRENCY_EDIT: [
                MessageHandler(text_filter, handle_currency_text),
                char_callback,
            ],
            CHAR_CURRENCY_CONVERT: [
                MessageHandler(text_filter, handle_convert_text),
                char_callback,
            ],
            CHAR_ABILITIES_MENU: [char_callback],
            CHAR_ABILITY_LEARN_NAME: [
                MessageHandler(text_filter, handle_ability_learn_text),
                char_callback,
            ],
            CHAR_ABILITY_LEARN_DESC: [
                MessageHandler(text_filter, handle_ability_learn_text),
                char_callback,
            ],
            CHAR_ABILITY_LEARN_USES: [
                MessageHandler(text_filter, handle_ability_learn_text),
                char_callback,
            ],
            CHAR_MULTICLASS_MENU: [char_callback],
            CHAR_MULTICLASS_ADD: [
                MessageHandler(text_filter, handle_multiclass_add_text),
                char_callback,
            ],
            CHAR_MULTICLASS_ADD_LEVELS: [
                MessageHandler(text_filter, handle_multiclass_add_text),
                char_callback,
            ],
            CHAR_CLASS_SUBCLASS_INPUT: [
                MessageHandler(text_filter, handle_subclass_text),
                char_callback,
            ],
            CHAR_DICE_MENU: [char_callback],
            CHAR_NOTES_MENU: [char_callback],
            CHAR_NOTE_NEW_TITLE: [
                MessageHandler(text_filter, handle_note_title_text),
                char_callback,
            ],
            CHAR_NOTE_NEW_BODY: [
                MessageHandler(text_filter, handle_note_body_text),
                char_callback,
            ],
            CHAR_NOTE_EDIT: [
                MessageHandler(text_filter, handle_edit_note_text),
                char_callback,
            ],
            CHAR_VOICE_NOTE_TITLE: [
                MessageHandler(text_filter, handle_note_title_text),
                MessageHandler(voice_filter, handle_voice_note),
                char_callback,
            ],
            CHAR_MAPS_MENU: [char_callback],
            CHAR_MAP_NEW_ZONE: [
                MessageHandler(text_filter, handle_new_zone_text),
                char_callback,
            ],
            CHAR_MAP_ADD_FILE: [
                MessageHandler(photo_filter, handle_map_file),
                MessageHandler(doc_filter, handle_map_file),
                char_callback,
            ],
            CHAR_SETTINGS_MENU: [char_callback],
            CHAR_DELETE_CONFIRM: [char_callback],
        },
        fallbacks=[
            CommandHandler("start", lambda u, c: ConversationHandler.END),
            CommandHandler("stop", stop_command_handler),
        ],
        allow_reentry=True,
        name="character_conversation",
        persistent=False,
    )
