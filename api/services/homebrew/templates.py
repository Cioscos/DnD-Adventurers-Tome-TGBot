"""Hardcoded homebrew rule templates. Installed via POST /templates/{id}/install."""
from __future__ import annotations

from typing import Optional


_WEAR_EFFECTS_PER_QUALITY = {
    "X": [
        {"action": "set_property", "target": "subject",
         "key": "damage_state", "value": "distrutta"},
        {"action": "unequip", "target": "subject"},
        {"action": "notify", "severity": "error",
         "message": "💥 $subject.name distrutta!"},
        {"action": "add_history", "description": "$subject.name distrutta (Qualità & Usura)"},
    ],
    "D": [
        {"action": "if",
         "cond": {"path": "$subject.damage_state", "op": "eq", "value": "danneggiata"},
         "then": [
             {"action": "set_property", "target": "subject",
              "key": "damage_state", "value": "distrutta"},
             {"action": "unequip", "target": "subject"},
             {"action": "notify", "severity": "error",
              "message": "💥 $subject.name distrutta (era già danneggiata)!"},
         ],
         "else": [
             {"action": "set_property", "target": "subject",
              "key": "damage_state", "value": "danneggiata"},
             {"action": "notify", "severity": "warning",
              "message": "⚠️ $subject.name danneggiata!"},
         ]},
        {"action": "add_history", "description": "$subject.name (Qualità & Usura): risultato D"},
    ],
    "S": [],
}


def _wear_effects() -> list[dict]:
    return [
        {"action": "roll_dice", "notation": "1d20", "store_as": "wear_roll"},
        {"action": "lookup_table", "table": "tabella_usura",
         "row": "$subject.quality", "col": "$wear_roll", "store_as": "wear_result"},
        {"action": "match", "value": "$wear_result", "cases": _WEAR_EFFECTS_PER_QUALITY},
    ]


_QUALITY_WEAR_DSL = {
    "version": 1,
    "subject": {"type": "item", "filter": {"item_types": ["weapon", "armor", "shield"]}},
    "properties": [
        {"key": "quality", "type": "enum",
         "values": ["pessima", "ordinaria", "buona", "straordinaria"],
         "default": "ordinaria",
         "label_i18n": {"it": "Qualità", "en": "Quality"},
         "value_labels_i18n": {
             "pessima":       {"it": "Pessima", "en": "Poor"},
             "ordinaria":     {"it": "Ordinaria", "en": "Common"},
             "buona":         {"it": "Buona", "en": "Good"},
             "straordinaria": {"it": "Straordinaria", "en": "Masterwork"},
         }},
        {"key": "damage_state", "type": "enum",
         "values": ["integra", "danneggiata", "distrutta"],
         "default": "integra",
         "label_i18n": {"it": "Stato", "en": "State"},
         "value_labels_i18n": {
             "integra":     {"it": "Integro",     "en": "Pristine"},
             "danneggiata": {"it": "Danneggiato", "en": "Damaged"},
             "distrutta":   {"it": "Distrutto",   "en": "Broken"},
         }},
    ],
    "tables": [{
        "id": "tabella_usura",
        "row_axis": "quality", "col_axis": "d20_result",
        "col_bins": [[1, 1], [2, 3], [4, 9], [10, 15], [16, 20]],
        "cells": {
            "pessima":       ["X", "X", "D", "D", "S"],
            "ordinaria":     ["X", "D", "D", "S", "S"],
            "buona":         ["D", "D", "S", "S", "S"],
            "straordinaria": ["D", "S", "S", "S", "S"],
        },
    }],
    "passive_modifiers": [],
    "triggers": [
        {"event": "attack_rolled",
         "filters": [
             {"path": "$event.is_fumble", "op": "eq", "value": True},
             {"path": "$subject", "op": "has_property", "value": "quality"},
             {"path": "$subject.is_equipped", "op": "eq", "value": True},
         ],
         "effects": _wear_effects()},
        {"event": "damage_taken",
         "filters": [
             {"path": "$event.was_critical_hit", "op": "eq", "value": True},
             {"path": "$subject", "op": "has_property", "value": "quality"},
             {"path": "$subject.is_equipped", "op": "eq", "value": True},
         ],
         "effects": _wear_effects()},
        {"event": "dropped_to_zero",
         "filters": [
             {"path": "$subject", "op": "has_property", "value": "quality"},
             {"path": "$subject.is_equipped", "op": "eq", "value": True},
         ],
         "effects": _wear_effects()},
    ],
}


_BLEEDING_DSL = {
    "version": 1,
    "subject": {"type": "character"},
    "properties": [],
    "tables": [],
    "passive_modifiers": [],
    "triggers": [
        {"event": "manual_trigger",
         "filters": [],
         "effects": [
             {"action": "apply_condition", "key": "custom:bleeding"},
             {"action": "notify", "severity": "warning",
              "message": "🩸 Sanguinamento applicato"},
             {"action": "add_history", "description": "Sanguinamento applicato"},
         ]},
        {"event": "turn_started",
         "filters": [
             {"path": "$character.conditions", "op": "has_property", "value": "custom:bleeding"},
         ],
         "effects": [
             {"action": "roll_dice", "notation": "1d4", "store_as": "blood"},
             {"action": "damage_character", "amount": "$blood"},
             {"action": "notify", "severity": "warning",
              "message": "🩸 Sanguinamento: subisci $blood danni"},
             {"action": "add_history", "description": "Sanguinamento: $blood danni"},
         ]},
    ],
}


_ENCHANTED_WEAPON_DSL = {
    "version": 1,
    "subject": {"type": "item", "filter": {"item_types": ["weapon"]}},
    "properties": [
        {"key": "enchanted", "type": "boolean", "default": False,
         "label_i18n": {"it": "Incantata", "en": "Enchanted"}},
    ],
    "tables": [],
    "passive_modifiers": [],
    "triggers": [
        {"event": "attack_rolled",
         "filters": [
             {"path": "$event.is_fumble", "op": "eq", "value": False},
             {"path": "$subject.enchanted", "op": "eq", "value": True},
         ],
         "effects": [
             {"action": "roll_dice", "notation": "1d6", "store_as": "fire"},
             {"action": "notify", "severity": "info",
              "message": "🔥 +$fire danni da fuoco!"},
             {"action": "add_history",
              "description": "Arma incantata: +$fire fuoco extra"},
         ]},
    ],
}


_LUCK_POINTS_DSL = {
    "version": 1,
    "subject": {"type": "character"},
    "properties": [],
    "tables": [],
    "passive_modifiers": [],
    "resources": [
        {"key": "luck_points", "name": "Punti Fortuna",
         "max": 3, "restoration_type": "long_rest"},
    ],
    "triggers": [
        {"event": "long_rest_taken", "filters": [],
         "effects": [
             {"action": "restore_resource", "key": "luck_points", "amount": "max"},
             {"action": "notify", "severity": "info",
              "message": "🌟 Punti Fortuna ripristinati"},
         ]},
        {"event": "manual_trigger",
         "filters": [],
         "effects": [
             {"action": "change_resource", "key": "luck_points", "delta": -1},
             {"action": "notify", "severity": "success",
              "message": "🌟 Punto Fortuna usato: rilancia il tiro"},
             {"action": "add_history", "description": "Punto Fortuna speso"},
         ]},
    ],
}


TEMPLATES = [
    {
        "id": "quality_wear",
        "name": "Qualità & Usura",
        "description": "House rule per armi e armature: possono danneggiarsi o rompersi al fumble (nat-1 attacco), al critico subito e quando porti a 0 PF.",
        "icon": "⚒️",
        "dsl": _QUALITY_WEAR_DSL,
    },
    {
        "id": "bleeding",
        "name": "Sanguinamento",
        "description": "Condizione: subisci 1d4 danni a ogni turno fino alla rimozione.",
        "icon": "🩸",
        "dsl": _BLEEDING_DSL,
    },
    {
        "id": "enchanted_weapon",
        "name": "Arma incantata +1d6",
        "description": "Le armi marcate 'incantate' infliggono +1d6 danni da fuoco aggiuntivi a ogni tiro per colpire (tranne il fumble).",
        "icon": "⚔️",
        "dsl": _ENCHANTED_WEAPON_DSL,
    },
    {
        "id": "luck_points",
        "name": "Punti Fortuna",
        "description": "Risorsa custom: 3 punti, recupera con riposo lungo. Usa un punto per ottenere un effetto narrativo positivo.",
        "icon": "🌟",
        "dsl": _LUCK_POINTS_DSL,
    },
    # Altri template arrivano in Phase 3
]


def get_template(template_id: str) -> Optional[dict]:
    return next((t for t in TEMPLATES if t["id"] == template_id), None)
